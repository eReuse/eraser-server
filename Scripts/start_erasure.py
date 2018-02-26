import os
import uuid

from eraser_manager.core import DeviceObserver


def print_arguments(*args, **kwargs):
    for arguments in [args, kwargs]:
        for arg in arguments:
            print(arg)


if __name__ == '__main__':
    em = DeviceObserver(callback=print_arguments)
    em.run()

