import sys
import json
import uuid
import curses

from lxml import etree
from time import sleep
from Queue import Queue

from erwb.benchmark import benchmark_hdd
from logging import getLogger
from curses import wrapper, panel
from threading import Thread, Event, Lock
from subprocess import Popen, PIPE, check_output, CalledProcessError

from erwb import serializers
from erwb.conf import settings
from erwb.inventory import HardDrive

from erwb.utils import InventoryJSONEncoder as InvEncoder, convert_capacity
from erwb.eraser import get_datetime


def get_serialnumber(device_name):
    path_to_dev = '--name=/dev/%s' % device_name
    stdtext, errtext = Popen(['udevadm', 'info', '--query=all', path_to_dev], stdout=PIPE).communicate()
    for text in stdtext.decode().split("\n"):
        if 'ID_SERIAL=' in text:
            return text[text.find("=") + 1:].strip()

    return "No Serial"


def is_root_mount(device):
    devices_out, devices_err = Popen(['lsblk', "/dev/" + str(device), '-no', "MOUNTPOINT"], stdout=PIPE).communicate()
    for mount in devices_out.decode().split("\n"):
        if mount == "/":
            return True
    return False


def get_devices():
    """
    Get a dict with the sdX as keys and inside each one, another dict with the model name.
    :return: dict
    """
    menu_list = {}

    devices_out, devices_err = Popen(['lsblk', '--nodeps', '-bno', "TYPE,NAME,SIZE,MODEL"], stdout=PIPE).communicate()
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


def devices_oberver(dictionary):
    devices = get_devices()
    for device in devices.keys():
        if device in dictionary:
            pass


class EraserStart(object):
    def __init__(self):
        self.loger = getLogger("Eraser Server")
        self.stdscr = None

        wrapper(self.start)

    def init_screen(self):
        if self.stdscr:
            self.stdscr.clear()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
        else:
            self.loger.info("Cannot initialise when windows is hidden.")

    def start(self, stdscr):
        self.stdscr = stdscr
        self.init_screen()

        self.start_eraser_process()

    def start_eraser_process(self):
        curses.curs_set(0)

        main_menu = EraserMenu(self.stdscr)
        main_menu.display()


class EraserMenu(object):
    def __init__(self, stdscreen):
        self.process = EraserProcess()

        self.window = stdscreen.subwin(0, 0)
        self.window.nodelay(1)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

        self.old_device_list = None
        self.position = 0
        self.items = []

    def navigate(self, n):
        self.position = len(self.items)
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def item_start(self):
        pass

    def item_stop(self):
        return "exit"

    def display(self):
        self.panel.top()
        self.panel.show()
        self.window.refresh()
        curses.doupdate()

        while True:
            # self.items = [("Start", "start")]
            self.items = []
            devices = self.process.get_list()

            for device in devices:
                if "OS device" in devices[device]["message"]:
                    continue
                if "label" in devices[device]:
                    self.items.append((devices[device]["label"], device))

            self.items.append(("Exit", "exit"))

            self.window.clear()
            self.position = len(self.items) - 1
            self.window.addstr(20, 1, str(self.process.show_queue()), curses.A_NORMAL)

            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL

                msg = '%d. %s' % (index, item[0])
                self.window.addstr(2 + index, 5, msg, mode)

            key = self.window.getch()

            if key in [curses.KEY_ENTER, ord('\n')]:
                if self.position == len(self.items) - 1:
                    break
                else:
                    pass  # print(self.items[self.position][1])

            elif key == curses.KEY_UP:
                self.navigate(-1)

            elif key == curses.KEY_DOWN:
                self.navigate(1)

            elif key == curses.KEY_ENTER:
                if self.items[3] not in ["start", "exit"]:
                    pass

            curses.napms(5000)  # Sleep

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()


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
            devices = get_devices()
            for device in devices.keys():
                if device not in self.devices.keys():
                    add_callback(device, devices[device])
            try:
                for device in self.devices.keys():
                    if device not in devices.keys():
                        rm_callback(device)
            except RuntimeError:
                pass
            sleep(0.5)

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
                    sleep(0.1)

                    setattr(self, "event_%s" % device_name, Event())
                    self.devices[device_name]["event"] = getattr(self, "event_%s" % device_name)
                    self.devices[device_name]["event"].clear()

                    setattr(self, "thread_%s" % device_name, Thread(target=self._erase_process, args=(device_name, "")))
                    self.devices[device_name]["thread"] = getattr(self, "thread_%s" % device_name)
                    self.devices[device_name]["thread"].setDaemon(True)
                    self.devices[device_name]["thread"].start()
            except Exception as ex:
                sys.stderr.write(ex)

    def _erase_process(self, device_name, test):
        try:
            self.prepare_device(device_name)
            stop_event = getattr(self, "event_%s" % device_name)
            data = serializers.export_to_devicehub_schema(self.devices_objects[device_name])

            mode = settings.get('eraser', 'MODE')
            zeros = settings.getboolean('eraser', 'ZEROS')

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

            for current_step in range(1, total_steps + 1):
                start_time = get_datetime()
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
                start_time = get_datetime()
                if stop_event.is_set():
                    return
                try:
                    print_step = "{current}/{total}".format(current=current_step + 1, total=print_total_steps)
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
            for item in [hd for hd in HardDrive.retrieve(self.lshw_xml)]:
                if str(item.logical_name).endswith(device_name):
                    self.devices_objects[device_name] = item
                    self.devices_objects[device_name].type = "HardDrive"

    def get_list(self):
        """ List all devices ready to print on terminal. """
        try:
            for device in self.devices:
                text = "- %s -" % self.devices[device]["message"] if "message" in self.devices[device].keys() else ""
                self.devices[device]["label"] = "{device}, {model} ({size} GB) {message}".format(
                    device=device,
                    model=self.devices[device]["model"],
                    size=round(convert_capacity(self.devices[device]["size"], "bytes", "GB"), 2),
                    message=text)

            return self.devices
        except RuntimeError:
            return {}


if __name__ == '__main__':
    try:
        EraserStart()
        # d = EraserProcess()
        # while True:
        #     sleep(1)
        #     print("\n")
        #     print(d.get_list())

    except KeyboardInterrupt:
        print("Exited")
