'''simdev.py

A controller class for SRS SIM Devices 

Author: Weiyang Wang [wew168@ucsd.edu]
'''

from __future__ import print_function
import serial
import sys
import time
import numpy as np
from sys import stderr

DEBUG = True

# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint(*args, **kwargs)

def parse_retstr(msg, msg_start):
    '''Parse a response of #abbbccccc... format.
    Argument:
        msg {str} -- message to be parsed
        msg_start {int} -- index of the first useful letter in message
    '''
    try:
        return msg[msg_start:]
    except IndexError:
        return ''

def parse_portmsg(msg):
    if msg[0:3] == 'MSG':
        return int(msg[4:5]), msg[6:]
    elif len(msg) != 0:
        return 0, msg
    else:
        return -1, None

class SIMserial(object):
    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE,
                             stopbits=serial.STOPBITS_ONE, timeout=0.5,
                             rtscts=False, waittime=0.001, tper=1000):

        # Deal with the serial port
        self.ser = serial.Serial(port, baudrate=baudrate,
                                       parity=parity,
                                       stopbits=stopbits,
                                       timeout=timeout,
                                       rtscts=rtscts)

        if not self.ser.is_open:
            self.ser.open()

        self.waittime = waittime
        # time to wait between readings
        self.tper = tper

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

    def send(self, message):
        '''General purpose send

        Arguments:
            message {str} -- message to send
        '''
        message += '\n'
        dprint("DEBUG: send ", end='')
        dprint(message, end='')
        self.ser.write(message)

    def recv(self):
        '''General purpose receive

        Returns whatever is returned from the device, up to a LF.
        '''
        msg = self.ser.readline().rstrip()
        dprint("DEBUG: recv ", end='')
        dprint(msg)
        return msg

    def query(self, message):
        self.send(message)
        time.sleep(self.waittime)
        return self.recv()

    @staticmethod
    def makecmd(command, port=None, str_block=None, literal=None, num=None):
        '''make a command string.
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
        '''
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

class SIM900(SIMserial):

    ESCSTR = 'xyz'

    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE,
                             stopbits=serial.STOPBITS_ONE, timeout=0.5,
                             waittime=0.001, tper=1000):

        # Deal with the serial port
        super(SIM900, self).__init__(port, baudrate, parity, stopbits, timeout, waittime, tper)
        self.configure()


    def configure(self):
        '''Set all termination to LF, set the port for streaming to pass
        through mode.
        '''
        self.sendcmd("RPER", num=0)
        for i in range(1, 10):
            self.sendcmd("TERM", port=i, literal="LF")
            self.sendcmd("SNDT", port=i, str_block=SIM900.makecmd("TERM", literal=0))

    def sendcmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-send
        '''
        message = SIM900.makecmd(command, port, str_block, literal, num)
        self.send(message)

    def querycmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-query
        '''
        message = SIM900.makecmd(command, port, str_block, literal, num)
        return self.query(message)

    def pconnect(self, port):
        self.sendcmd('CONN', port, SIM900.ESCSTR)

    def pdisconnect(self):
        self.send(SIM900.ESCSTR)

class SIM921(SIMserial):

    def __init__(self, port, timeout=0.5, waittime=0.001, tper=105):

        # Deal with the serial port
        super(SIM921, self).__init__(port, timeout=timeout, waittime=waittime, tper=tper, rtscts=True)
        self.configure()

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

    def configure(self):
        self.send("TERM 0")
        self.send(SIM921.makecmd("TPER", num=self.tper))

    @staticmethod
    def makecmd(command, str_block=None, literal=None, num=None):
        return SIMserial.makecmd(command, str_block=str_block,
                literal=literal, num=num)






