# coding=utf-8
import uuid
import subprocess

from ereuse_workbench import utils
from eraser_manager import helpers


class EraserManager:
    """
    Manage erase process.
    """

    def __init__(self):
        pass

    def erase_process(self):
        data = dict()

        data['_uuid'] = str(uuid.uuid4())

        data["serial"] = self.devices[device_name]["serial"]
        data["model"] = self.devices[device_name]["model"]
        data["erasure"] = {}
        data["erasure"]["@type"] = "EraseBasic"
        data["erasure"]["cleanWithZeros"] = zeros
        data["erasure"]["size"] = self.devices[device_name]["size"]
        data["erasure"]["steps"] = []

        total_steps = helpers.settings.getint('eraser', 'STEPS')
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
            p = subprocess.Popen(command, stderr=subprocess.PIPE, bufsize=1)
            line = None
            with p.stderr:
                for line in iter(p.stderr.readline, b''):
                    percentage_message = "{}".format(line.decode().replace("\n", "").split(" ")[-1])
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


class DeviceObserver(object):
    """
    Manager all information about devices being un/plugged.
    """
    callbacks = []

    def __init__(self, callback: object or None = None):
        self.devices = {}
        self.main_device = helpers.find_root()  # This is my device, don't delete it!!
        self.callbacks.append(callback)

    def append_callback(self, callback: object):
        """
        Append a callback to callbacks array.
        Callbacks are the functions to execute with the device found as argument.
        :param callback:
        """
        self.callbacks.append(callback)

    def run(self):
        """
        This will start to watch new devices un/plugged and will execute callbacks.
        :return:
        """
        while True:
            d = helpers.get_devices()
            print(d)

    def get_list(self):
        """ List all devices ready to print on terminal. """
        try:
            for device in self.devices:
                text = "- %s -" % self.devices[device]["message"] if "message" in self.devices[device].keys() else ""
                self.devices[device]["label"] = "{device}, {model} ({size} GB) {message}".format(
                    device=device,
                    model=self.devices[device]["model"],
                    size=round(utils.convert_capacity(self.devices[device]["size"], "bytes", "GB"), 2),
                    message=text)

            return self.devices
        except RuntimeError:
            return {}
