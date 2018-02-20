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


class SIM921(SIMModule):
    """
    SIM921 class represents an sim921 module connected to the mainframe.
    """

    def setExcitationOnOff(self, state):
        self.send('EXON {0}'.format(state))

    def setExcitationRange(self, e_int):
        self.send('EXCI {0}'.format(e_int))

    def queryExcitation(self):
        return self.query('EXON?')

    def setResistanceRange(self, r_int):
        self.send('RANG {0}'.format(r_int))

    def setExcitationFreq(self, freq):
        self.send('FREQ {0}'.format(freq))

    def getExcitationFreq(self):
        return self.query('FREQ?')

    def setTimeConstant(self, tau):
        self.send('TCON {0}'.format(tau))

    def getTimeConstant(self):
        return self.query('TCON?')


class SIM922(SIMModule):
    """
    SIM922 class represents a sim922 module connected to the mainframe.
    """
    def getDiodeVoltages(self):
        volts = self.query('VOLT? 0,1')
        volts = volts.split(',')
        try:
            voltages = map(float, volts)
        except ValueError:
            voltages = [float('nan')]
        return voltages

    def getDiodeTemps(self):
        temps = self.query('TVAL? 0,1')
        temps = temps.split(',')
        try:
            temperatures = map(float, temps)
        except ValueError:
            temperatures = [float('nan')]
        return temperatures


class SIM925(SIMModule):
    """
    SIM925 class represents an SIM925 module connected to the main frame.
    """

    def SIM925switchMUX(self,channel):
        self.send('CHAN {0}'.format(channel))