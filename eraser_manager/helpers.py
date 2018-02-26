# coding=utf-8
import subprocess


def get_serialnumber(device_name):
    path_to_dev = '--name=/dev/%s' % device_name
    stdtext, errtext = subprocess.Popen(['udevadm', 'info', '--query=all', path_to_dev], stdout=subprocess.PIPE).communicate()
    for text in stdtext.decode().split("\n"):
        if 'ID_SERIAL=' in text:
            return text[text.find("=") + 1:].strip()

    return "No Serial"


def find_root():
    devices_out, devices_err = subprocess.Popen(['lsblk', '-no', "MOUNTPOINT"], stdout=subprocess.PIPE).communicate()
    for mount in devices_out.decode().split("\n"):
        if mount == "/":
            return mount

    raise Exception


def get_devices():
    """
    Get a dict with the sdX as keys and inside each one, another dict with the model name.
    :return: dict
    """
    menu_list = {}

    devices_out, devices_err = subprocess.Popen(['lsblk', '--nodeps', '-bno', "TYPE,NAME,SIZE,MODEL"], stdout=subprocess.PIPE).communicate()
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
