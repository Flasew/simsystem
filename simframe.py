"""
simframe.py
Definition and implementation of frame-level SIM devices,
mainly for SIM900. Also supports direct connection to SIM921
device.
"""

from __future__ import print_function
from simutil import *
import serial
import time


class SIMFrame(object):
    """ 
    General interface for SIM devices that's directly connected via serial port
    """

    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE, timeout=0.5, rtscts=False, waittime=0.001):

        # Deal with the serial port
        self.ser = serial.Serial(port, baudrate=baudrate, parity=parity, stopbits=stopbits, timeout=timeout, rtscts=rtscts)

        if not self.ser.is_open:
            self.ser.open()
        
        # wait time in query commands between writing command and reading result
        self.waittime = waittime

    def __del__(self):
        # Reset the device on disconnect.
        self.send("*RST")
        if self.ser.is_open:
            self.ser.close()

    def configure(self):
        """
        Device configuration. Must be implemented for each subclass.
        :return: no return
        """
        raise NotImplemented

    def send(self, message):
        """General purpose send

        Arguments:
            message {str} -- message to send
        """
        message += '\n'
        dprint("send ", end='')
        dprint(message, end='')
        self.ser.write(message)

    def recv(self):
        """General purpose receive

        Returns whatever is returned from the device, up to a LF.
        """
        msg = self.ser.readline().rstrip()
        dprint("recv ", end='')
        dprint(msg)
        return msg

    def query(self, message):
        self.send(message)
        time.sleep(self.waittime)
        return self.recv()

    @staticmethod
    def mkcmd(command, port=None, str_block=None, literal=None, num=None):
        """make a command string.
        Arguments:
            command {str} -- 4-letter command string

        Keyword Arguments:
            port {number} -- port that this command should be route to. If set
                             to None, will only be send to mainframe (default: {None})
            num {number} -- num field of command (default: {None})
            literal {str} -- literal field.
            str_block {str} -- Multi-byte (string) block field of the command.
                               If uses the Quote-delimited strings, please also
                               include the outer quotes since ' and " can be confusing.
                               If the field has a literal token instead of a
                               string block, also put it here (of course without
                               the outer quotes.)
        """
        message = command

        if port:
            message += " " + str(port)
        if literal is not None:
            message += ("," if port else " ") + str(literal)
        if str_block is not None:
            message += ("," if port or literal else " ") + "'" + str(str_block) + "'"
        if num is not None:
            message += ("," if port or str_block or literal else " ") + str(num)

        return message


class SIM900(SIMFrame):

    def __init__(self, port, baudrate=115200, parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE, timeout=0.5, waittime=0.001):

        # Deal with the serial port
        super(SIM900, self).__init__(port, baudrate, parity, stopbits, timeout, False, waittime)
        self.configure()

        # maps each port to a device. Defaulted to none, need to use setter to set it.
        # use getter and setter to modify.
        self._modules = {key: None for key in range(1, 11)}

        # Which device that the main frame is currently on. 0 for not on anything.
        self.connected_to = 0

    def configure(self):
        """Set all termination to LF. This is forced throughout the program.
        """
        self.sendcmd("RPER", num=0)
        for i in range(1, 10):
            self.sendcmd("TERM", port=i, literal="LF")
            self.sendcmd("SNDT", port=i, str_block=SIM900.mkcmd("TERM", literal=0))

    def configure_module(self, port):
        """
        Configure a SIM module device according to communication parameters set on the device on port
        :param port: port of SIMModule object to be configured
        :return: no return
        """
        self.sendcmd("SNDT", port=port, str_block=SIM900.mkcmd("BAUD", num=self._modules[port].baudrate))
        self.sendcmd("BAUD", port=port, num=self._modules[port].baudrate)
        self.connect_module(port).configure()

    def connect_module(self, port):
        """
        Get the device connected at a port. The returned device will be connected directly via the "CONN" command.
        :param port: Port of the device that it is on.
        :return: a SIMModule object corresponding the the device.
        """
        if self.connected_to == port:
            eprint("Module {:s} on port {:d} is already connected.".format(self._modules[port].name, port))
            return self._modules[port]
        elif self.connected_to != port and self.connected_to != 0:
            eprint("Error: Already connected to another module.")
            return None
        if self._modules[port] is None:
            eprint("Error: No device is connected on port {:d}.".format(port))
            return None
        else:
            self.pconnect(port)
            dprint("Connected to port {:d}.".format(port))
            self._modules[port].connected = True
            return self._modules[port]

    def set_module(self, port, device, force_set=False):
        """
        Set the device on a port. If a device already exist on that port, unless force_set is specified, returns false.
        Device will be set according to the device parameter.
        :param port: port of the device to be set
        :param device: SIMModule object to be set
        :param force_set: if true, will ignore the current device on this port.
        :return: True on success, false otherwise
        """
        if not force_set:
            if self._modules[port] is not None:
                eprint("Error: Device {:s} already exist on port {:d}".format(self._modules[port].name, port))
                return False
        else:
            self._modules[port] = device
            self.configure_module(device)
            return True

    def sendcmd(self, command, port=None, str_block=None, literal=None, num=None):
        """Wrapper for mkcmd-send
        """
        message = SIM900.mkcmd(command, port, str_block, literal, num)
        self.send(message)

    def querycmd(self, command, port=None, str_block=None, literal=None, num=None):
        """Wrapper for mkcmd-query
        """
        message = SIM900.mkcmd(command, port, str_block, literal, num)
        return self.query(message)

    def pconnect(self, port):
        self.sendcmd('CONN', port, ESCSTR)
        self.connected_to = port

    def pdisconnect(self):
        """
        Disconnect from the currently connected port.
        :return: no return
        """
        self.send(ESCSTR)
        self.connected_to = 0

    def disconnect_reset(self):
        """
        Only use this one for force disconnect!
        :return: no return
        """
        self.send(ESCSTR)
        for mod in self._modules.values():
            if mod is not None:
                mod.connected = False
        self.connected_to = 0

    def get_full_idn(self):
        return self.query('*IDN?')


class SIM921(SIMFrame):
    """
    Directly connected, frame-level SIM921. This kind of connection indicates that SIM 921 is used for
    streaming fast data.
    """

    def __init__(self, port, timeout=0.5, waittime=0.001, tper=105):

        # Deal with the serial port
        super(SIM921, self).__init__(port, timeout=timeout, waittime=waittime , rtscts=True)
        self.tper = tper
        self.configure()

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

    def configure(self):
        self.send("TERM LF")
        self.send(SIM921.mkcmd("TPER", num=self.tper))

    @staticmethod
    def mkcmd(command, str_block=None, literal=None, num=None, port=0):
        """
        Delegate to the parent mkcmd method. port value simply ignored.
        """
        return SIMFrame.mkcmd(command, str_block=str_block,
                              literal=literal, num=num)






