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
        self.serial_numbers = set()
        while True:
            _, components = Computer().run()
            hdds = {c['serialNumber']: c for c in components if c['@type'] == 'HardDrive'}
            serial_numbers = {hdds.keys()}
            if serial_numbers != self.serial_numbers:
                # Change in hard-drives
                new_sn = serial_numbers - self.serial_numbers
                for sn in new_sn:
                    self.erase(hdds[sn])
            self.serial_numbers = serial_numbers
            sleep(2)

    def erase(self, hdd: dict):
        # in a new thread:
        EraserWorker(self.mode, self.steps, self.zeros, hdd).start()


class EraserWorker(Process):
    def __init__(self, mode: EraseType, steps: int, zeros: bool, hdd: dict):
        self.eraser = Eraser(mode, steps, zeros)
        self.folder = Path('~').joinpath('eraser-workbench')
        self.folder.mkdir(exist_ok=True)
        self.hdd = hdd
        self.logical_name = hdd[PrivateFields.logical_name]
        super().__init__()

    def run(self):
        self.hdd['erasure'] = self.eraser.erase(self.logical_name)
        # patch('localhost:8091/erasures/{}'.format(self.hdd['serial_number']), json=self.hdd)

    def to_json_file(self):
        snapshot = {
            '_uuid': str(uuid4()),
            'device': self.hdd
        }
        with self.folder.joinpath(self.hdd['serial_number'] + '.json').open('w') as f:
            json.dump(snapshot, f, indent=2, sort_keys=True, cls=DeviceHubJSONEncoder)
