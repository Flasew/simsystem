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


class SIM921(SIMFrame):
    """
    Directly connected, frame-level SIM921. This kind of connection indicates that SIM 921 is used for
    streaming fast data.
    """

    def __init__(self, port, timeout=0.5, waittime=0.001, tper=105):

        # Deal with the serial port
        super(SIM921, self).__init__(port, baudrate=9600, timeout=timeout, waittime=waittime , rtscts=True)
        self.tper = tper
        self.configure()

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

    def configure(self):
        self.send("TERM LF")
        self.send(SIM921.mkcmd("TPER", num=self.tper))

    def setExcitationOnOff(self, state):
        self.send('EXON {0}'.format(state))
        return self

    def setExcitationRange(self, e_int):
        self.send('EXCI {0}'.format(e_int))
        return self

    def queryExcitation(self):
        return self.query('EXON?')

    def setResistanceRange(self, r_int):
        self.send('RANG {0}'.format(r_int))
        return self

    def setExcitationFreq(self, freq):
        self.send('FREQ {0}'.format(freq))
        return self

    def getExcitationFreq(self):
        return self.query('FREQ?')

    def setTimeConstant(self, tau):
        self.send('TCON {0}'.format(tau))
        return self

    def getTimeConstant(self):
        return self.query('TCON?')

    @staticmethod
    def mkcmd(command, str_block=None, literal=None, num=None, port=0):
        """
        Delegate to the parent mkcmd method. port value simply ignored.
        """
        return SIMFrame.mkcmd(command, str_block=str_block,
                              literal=literal, num=num)






