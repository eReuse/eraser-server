from ereuse_workbench.eraser import EraseType

from eraser_manager.eraser_server import EraserServer

if __name__ == '__main__':
    EraserServer(EraseType.EraseBasic, 1, False)
