import json
from multiprocessing import Process
from pathlib import Path
from time import sleep
from uuid import uuid4

from ereuse_utils import DeviceHubJSONEncoder
from ereuse_workbench.computer import Computer, PrivateFields
from ereuse_workbench.eraser import EraseType, Eraser


class EraserServer:
    # noinspection PyPep8Naming
    def __init__(self, mode: EraseType, steps: int, zeros: bool) -> None:
        self.mode = mode
        self.steps = steps
        self.zeros = zeros
        self.old_serial_numbers = set()
        while True:
            hdds = Computer().hard_drives(get_removables=True)
            hdds = {hdd['serialNumber']: hdd for hdd in hdds if hdd is not None}
            serial_numbers = set(hdds.keys())
            new_sn = serial_numbers - self.old_serial_numbers
            for sn in new_sn:  # New plugged-in external hard-drives
                self.erase(hdds[sn])
            self.old_serial_numbers = serial_numbers
            sleep(2)

    def erase(self, hdd: dict):
        # in a new thread:
        EraserWorker(self.mode, self.steps, self.zeros, hdd).start()


class EraserWorker(Process):
    def __init__(self, mode: EraseType, steps: int, zeros: bool, hdd: dict):
        self.eraser = Eraser(mode, steps, zeros)
        self.folder = Path.home().joinpath('eraser-workbench')
        self.folder.mkdir(exist_ok=True)
        self.hdd = hdd
        self.logical_name = hdd[PrivateFields.logical_name]
        super().__init__()

    def run(self):
        from pprint import pprint
        print('To erase')
        pprint(self.hdd)
        self.hdd['erasure'] = self.eraser.erase(self.logical_name)
        print('Erased')
        pprint(self.hdd)
        self.to_json_file(self.hdd)
        # patch('localhost:8091/erasures/{}'.format(self.hdd['serial_number']), json=self.hdd)

    def to_json_file(self, hdd):
        snapshot = {
            '_uuid': str(uuid4()),
            'device': hdd
        }
        with self.folder.joinpath(hdd['serial_number'] + '.json').open('w') as f:
            json.dump(snapshot, f, indent=2, sort_keys=True, cls=DeviceHubJSONEncoder)
