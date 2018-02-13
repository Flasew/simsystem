"""
simmodule.py
Interface and implementation of the sim modules to be connected to SIM900 device.
Author: Weiyang Wang <wew168@ucsd.edu>
"""

from simutil import *


class SIMModule(object):
    """
    Interface for a SIMModule object.
    """

    def __init__(self, frame, name, baudrate=9600):
        """
        Initialize a simmodule object. Must have a frame master in order to correctly function.
        :param frame: Frame of the module that is connected to
        :param name: name of this module, for convenient reference
        :param baudrate: baudrate of the module.
        """
        self.frame = frame
        self._name = name
        self._baudrate = baudrate
        self.connected = False

    @property
    def name(self):
        return self._name

    @property
    def baudrate(self):
        return self._baudrate

    def configure(self):
        """
        Should to be implemented by each instance in order to properly configure the device.
        :return: no return
        """
        pass

    # following methods are delegated to mainframe. Only works when module is connected, and will check.
    def send(self, message):
        """General purpose send

        Arguments:
            message {str} -- message to send
        """
        if self.connected:
            self.frame.send(message)
        else:
            eprint("Error: module {:s} is not connected, can't send command.".format(self.name))

    def recv(self):
        """General purpose receive

        Returns whatever is returned from the device, up to a LF.
        """
        if self.connected:
            return self.frame.recv()
        else:
            eprint("Error: module {:s} is not connected, can't receive message".format(self.name))

    def query(self, message):
        if self.connected:
            return self.frame.query(message)
        else:
            eprint("Error: module {:s} is not connected, can't query command".format(self.name))

    def release(self):
        """
        disconnect the direct connection from the module and return the control to mainframe.
        :return: No return
        """
        if not self.connected:
            eprint("Module {:s} is not connected to the main frame.".format(self.name))
        else:
            self.frame.pdisconnect()
            self.connected = False


