import sys
import json
import uuid

from lxml import etree
from time import sleep
from Queue import Queue

from threading import Thread, Event, Lock
from subprocess import Popen, PIPE, check_output, CalledProcessError

from erwb import serializers
from erwb.conf import settings

from erwb.utils import InventoryJSONEncoder as InvEncoder, convert_capacity
from erwb.eraser import get_datetime

from supereraser.utils import HardDriveErased as HardDrive


def get_serialnumber(device_name):
    path_to_dev = '--name=/dev/%s' % device_name
    stdtext, errtext = Popen(['udevadm', 'info', '--query=all', path_to_dev], stdout=PIPE).communicate()
    for text in stdtext.decode().split("\n"):
        if 'ID_SERIAL=' in text:
            return text[text.find("=") + 1:].strip()

    return "No Serial"


def is_root_mount(device):
    devices_out, devices_err = Popen(['lsblk', "/dev/" + str(device),
                                      '-no', "MOUNTPOINT"],
                                     stdout=PIPE).communicate()
    for mount in devices_out.decode().split("\n"):
        if mount == "/":
            return True
    return False


def get_devices():
    """
    Get a dict with the sdX as keys and inside
    each one, another dict with the model name.
    :return: dict
    """
    menu_list = {}

    devices_out, devices_err = Popen(['lsblk', '--nodeps', '-bno',
                                      "TYPE,NAME,SIZE,MODEL"],
                                     stdout=PIPE).communicate()

    for device in devices_out.decode().split("\n"):
        if device != "":
            device_parsed = device.split(" ")
            while u'' in device_parsed:
                device_parsed.remove(u'')
            device_type = device_parsed[0]
            if device_type in ["usb", "ata", "disk"]:
                device_name = device_parsed[1]
                device_size = device_parsed[2]
                device_model = ' '.join(device_parsed[3:]).strip(" ")

                menu_list[device_name] = {
                    "model": device_model,
                    "size": int(device_size),
                    "serial": get_serialnumber(device_name)
                }

    return menu_list


class EraserProcess:
    def __init__(self):
        self.devices = {}

        self.lshw_xml = None
        self.lshw_permission = Lock()

        self.devices_objects = {}
        self.stop_event = Event()
        self.erase_queue = Queue()
        self.mountpoint_device = None

        observer_thread = Thread(target=self.devices_oberver, args=(self.add_device, self.rm_device))
        observer_thread.setDaemon(True)
        observer_thread.start()

        erase_manager = Thread(target=self._erase_manager)
        erase_manager.setDaemon(True)
        erase_manager.start()

    def devices_oberver(self, add_callback, rm_callback):
        while not self.stop_event.is_set():
            try:
                devices = get_devices()
                for device in devices.keys():
                    if device not in self.devices.keys():
                        add_callback(device, devices[device])
                try:
                    for device in self.devices.keys():
                        if device not in devices.keys():
                            print("Removing {}".format(device))
                            rm_callback(device)
                except RuntimeError:
                    pass
                sleep(0.5)
            except Exception as ex:
                pass

    def add_device(self, name, dictionary):
        self.devices[name] = dictionary
        self.devices[name]["message"] = "ready"
        # @TODO: Make a conditional depending on configuration.
        self.erase(name)

    def show_queue(self):
        return self.erase_queue.queue

    def rm_device(self, name):
        if hasattr(self, "event_%s" % name):
            event = getattr(self, "event_%s" % name)
            event.set()

        if name in self.devices:
            del self.devices[name]
        if name in self.erase_queue.queue:
            self.erase_queue.queue.remove(name)

    def device_is_root_mountpoint(self, device_name):
        if self.mountpoint_device is None:
            if is_root_mount(device_name):
                self.mountpoint_device = device_name
                return True
            else:
                return False
        else:
            return True if str(device_name) == str(self.mountpoint_device) else False

    def erase(self, device_name):
        if device_name in self.devices.keys():
            if not self.device_is_root_mountpoint(device_name):
                self.erase_queue.put(device_name)
                self.devices[device_name]["message"] = "queued"
            else:
                self.devices[device_name]["message"] = "OS device"

    def _erase_manager(self):
        while not self.stop_event.is_set():
            try:
                if self.erase_queue.queue:
                    device_name = self.erase_queue.get()
                    print(device_name)
                    sleep(0.5)

                    setattr(self, "event_%s" % device_name, Event())
                    self.devices[device_name]["event"] = getattr(self, "event_%s" % device_name)
                    self.devices[device_name]["event"].clear()

                    setattr(self, "thread_%s" % device_name, Thread(target=self._erase_process, args=(device_name,)))
                    self.devices[device_name]["thread"] = getattr(self, "thread_%s" % device_name)
                    self.devices[device_name]["thread"].setDaemon(True)
                    self.devices[device_name]["thread"].start()
            except Exception as ex:
                sys.stderr.write(ex)

    def _erase_process(self, device_name):
        try:
            self.prepare_device(device_name)
            stop_event = getattr(self, "event_%s" % device_name)
            data = serializers.export_to_devicehub_schema(self.devices_objects[device_name])

            mode = settings.get('eraser', 'MODE')
            zeros = settings.getboolean('eraser', 'ZEROS')
            self.devices[device_name]["mode"] = mode
            self.devices[device_name]["write_zeros"] = zeros

            data['_uuid'] = str(uuid.uuid4())

            data["serial"] = self.devices[device_name]["serial"]
            data["model"] = self.devices[device_name]["model"]
            data["erasure"] = {}
            data["erasure"]["@type"] = "EraseBasic"
            data["erasure"]["cleanWithZeros"] = zeros
            data["erasure"]["size"] = self.devices[device_name]["size"]
            data["erasure"]["steps"] = []

            total_steps = settings.getint('eraser', 'STEPS')

            if zeros:
                print_total_steps = total_steps + 1
            else:
                print_total_steps = total_steps

            self.devices[device_name]["total_steps"] = print_total_steps
            self.devices[device_name]["current_step"] = 0

            current_step = 0
            for current_step in range(1, total_steps + 1):
                self.devices[device_name]["current_step"] = current_step
                start_time = get_datetime()
                self.devices[device_name]["current_step_start"] = start_time
                if stop_event.is_set():
                    return
                try:
                    print_step = "{current}/{total}".format(current=current_step, total=print_total_steps)
                    result_random = self._do_random_step(device_name, print_step)
                except (KeyError, CalledProcessError) as ex:
                    self.rm_device(device_name)
                    return
                end_time = get_datetime()
                data["erasure"]["steps"].append(
                    {"@type": "Random",
                     "endingTime": start_time,
                     "startingTime": end_time,
                     "success": result_random}
                )

            if zeros:
                current_step += 1
                start_time = get_datetime()

                self.devices[device_name]["current_step"] = current_step
                self.devices[device_name]["current_step_start"] = start_time
                if stop_event.is_set():
                    return
                try:
                    print_step = "{current}/{total}".format(current=current_step, total=print_total_steps)
                    result_zeros = self._do_zero_step(device_name, print_step)
                except (KeyError, CalledProcessError) as ex:
                    self.devices[device_name]["message"] = "Error: {}".format(ex or "Unknown error.")
                    self.rm_device(device_name)
                    return
                end_time = get_datetime()
                data["erasure"]["steps"].append(
                    {"@type": "Zeros",
                     "endingTime": start_time,
                     "startingTime": end_time,
                     "success": result_zeros}
                )

            self.devices[device_name]["message"] = "successful erased"

            with open(device_name + ".json", "w") as outfile:
                json.dump(data, outfile, indent=4, sort_keys=True, cls=InvEncoder)
        except KeyError:
            return  # Because device is detached.

    def _do_random_step(self, device_name, print_step):
        command = ["shred", "-vn", "1", "/dev/%s" % str(device_name)]
        stop_event = getattr(self, "event_%s" % device_name)

        p = Popen(command, stderr=PIPE, bufsize=1)
        line = None
        with p.stderr:
            for line in iter(p.stderr.readline, b''):
                percentage_message = "{}".format(line.decode("utf-8").replace("\n", "").split(" ")[-1])
                percentage_message = "0%" if "%" not in percentage_message else percentage_message
                self.devices[device_name]["message"] = "Random step: {percentage} - Step: {step}".format(
                    percentage=percentage_message, step=print_step)
                if stop_event.is_set():
                    return

        p.wait()
        if p.returncode == 0:
            return True
        else:
            self.devices[device_name]["message"] = "Error: {}".format(line or "Unknown error.")

        return False

    def _do_zero_step(self, device_name, print_step):
        command = ["shred", "-vzn", "0", "/dev/%s" % str(device_name)]
        stop_event = getattr(self, "event_%s" % device_name)

        try:
            p = Popen(command, stderr=PIPE, bufsize=1)
            line = None
            with p.stderr:
                for line in iter(p.stderr.readline, b''):
                    percentage_message = "{}".format(line.decode("utf-8").replace("\n", "").split(" ")[-1])
                    percentage_message = "0%" if "%" not in percentage_message else percentage_message
                    self.devices[device_name]["message"] = "Zeros step: {percentage} - Step: {step}".format(
                        percentage=percentage_message, step=print_step)
                    if stop_event.is_set():
                        return
            p.wait()
            if p.returncode == 0:
                return True
            else:
                self.devices[device_name]["message"] = "Error: {}".format(line or "Unknown error.")
        except CalledProcessError as ex:
            self.devices[device_name]["message"] = "Error: {}".format(ex or "Unknown error.")

        return False

    def prepare_device(self, device_name):
        if device_name not in self.devices_objects:
            self.get_hardware_object(device_name)

    def write_harddrive_properties(self, device_name):
        self.devices_objects[device_name].size = "unknown"
        self.devices_objects[device_name].erasure = {}

    def get_hardware_object(self, device_name):
        with self.lshw_permission:
            self.lshw_xml = etree.fromstring(check_output(["lshw", "-xml"]))
            for item in HardDrive.retrieve(self.lshw_xml):
                if str(item.logical_name).endswith(device_name):
                    self.devices_objects[device_name] = item
                    self.devices_objects[device_name].type = "HardDrive"

    def get_list(self):
        """ List all devices ready to print on terminal. """
        devices = {}
        try:
            for device in self.devices:
                text = "- %s -" % self.devices[device]["message"] if "message" in self.devices[device].keys() else ""
                devices[device] = {
                    'model': self.devices[device]["model"],
                    'size': self.devices[device]["size"],
                    'serial': self.devices[device]["serial"],
                    'capacity': str(round(convert_capacity(self.devices[device]["size"], "bytes", "GB"), 2)) + "GB",
                }
                items = ["mode", "write_zeros", "current_step", "total_steps", "current_step_start"]
                for name in items:
                    if name in self.devices[device].keys():
                        devices[device][name] = self.devices[device][name]

            return devices
        except RuntimeError:
            return {}


if __name__ == '__main__':
    try:
        erasure = EraserProcess()
        while True:
            sleep(1)
            jaison = erasure.get_list()
            print "\n"*10 + json.dumps(jaison, indent=4, sort_keys=True)

    except KeyboardInterrupt:
        print("Exited")
