# Repository status
[![Code Health](https://landscape.io/github/eReuse/eraser-server/master/landscape.svg?style=flat)](https://landscape.io/github/eReuse/eraser-server/master)

Repository health checked with: [landscape.io](https://landscape.io/github/pedrotgn/pyactor)

# eraser

Massively and securely erases hard-drives, internally using eReuse.org Workbench.

Installation
------------
Works only on Python 2.7.

Debian 9 instructions:
```bash
    sudo apt install -y git python-pip python-lxml smartmontools python-dateutil python-gnupg python-dmidecode lshw
    pip install git+https://github.com/ereuse/eraser.git --process-dependency-links
```

How to use
----------
1. Execute eraser: ``python eraser.py``
2. Plug any hard-drive you want to erase. The hard-drive will be erased automatically, without asking anything.
3. Everytime an erasure finishes, eraser creates a technical JSON report in the same folder where you
executed ``eraser.py``.
4. Upload each JSON file to DeviceHub. 
 
