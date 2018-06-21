# eraser-server

Massively and securely erases hard-drives, internally using [eReuse.org](https://www.ereuse.org/) Workbench.


## Installing

To install all the requirements to contribute with the developing I follow the following steps:

First I setup my workspace dir:
```
~/Workspace
git clone git@github.com:eReuse/eraser-server.git
git clone git@github.com:eReuse/workbench.git
```

Then I setup my virtualenv to use with this project:

```
sudo apt install python3-pip
sudo python3 -m pip install virtualenv
python3 -m virtualenv venv
venv/bin/python -m pip install -e ../workbench/
```

## Deployment
Get [Python 3](https://www.python.org/download/releases/3.0/?).

Debian 9 instructions:
```bash
    sudo apt install -y git python-pip python-lxml smartmontools python-dateutil python-gnupg python-dmidecode lshw
    pip install git+https://github.com/ereuse/eraser.git --process-dependency-links
```

### How to use
1. Execute eraser: ``python eraser.py``
2. Plug any hard-drive you want to erase. The hard-drive will be erased automatically, without asking anything.
3. Everytime an erasure finishes, eraser creates a technical JSON report in the same folder where you
executed ``eraser.py``.
4. Upload each JSON file to DeviceHub. 

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](https://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/eReuse/eraser-server/tags). 

## Authors

* **Xavier** - *Initial work* - [bustawin](https://github.com/bustawin)
* **Adrià** - *Maintenance and developing work* - [adriass](https://github.com/adriass)

This project is a part of eReuse Workbench tools.  [[webpage](https://www.ereuse.org/)] [[github](https://www.ereuse.org/)]

## License

This project is licensed under the GNU Affero General Public License - see the [LICENSE.md](LICENSE.md) file for details