from erwb.inventory import HardDrive, get_xpath_text, utils


class HardDriveErased(HardDrive):
    COMPONENTS = []

    def __init__(self, node):
        self.serialNumber = get_xpath_text(node, 'serial')
        self.manufacturer = get_xpath_text(node, 'vendor')
        self.model = get_xpath_text(node, 'product')

        self.logical_name = get_xpath_text(node, 'logicalname')
        self.interface = utils.run(
            "udevadm info --query=all --name={0} | grep ID_BUS | cut -c 11-".format(self.logical_name))
        self.interface = self.interface or 'ata'

        # TODO implement method for USB disk
        if self.interface == "usb":
            self.size = "Unknown"

        else:
            # (S)ATA disk
            try:
                size = int(get_xpath_text(node, 'size'))
            except (TypeError, ValueError):
                self.size = None
            else:
                unit = 'bytes'  # node.xpath('size/@units')[0]
                self.size = utils.convert_capacity(size, unit, self.CAPACITY_UNITS)

        # TODO read config to know if we should run SMART
        # if self.logical_name and self.interface != "usb":
        #     self.test = self.run_smart(self.logical_name)
        # else:
        #     logger.error("Cannot execute SMART on device '%s'.", self.serialNumber)