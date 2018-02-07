from __future__ import print_function
import multiprocessing
import sys
import time
import signal
import numpy as np
from sys import stderr
from datetime import datetime
from multiprocessing import Process, ProcessError, Lock
from multiprocessing.queues import SimpleQueue
from simdev import SIM900, SIM921

DEBUG = True

# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint(*args, **kwargs)

def file_writer(filename, title_line, formatted_str, buf):
    '''File writing worker function. Buffer is expected to be a queue or a
    Simplequeue.
    '''
    with open(filename, 'w+') as f:

        f.write(title_line)

        while True:
            data = buf.get()
            if data is None:
                break
            f.write(formatted_str % data)
            dprint("DEBUG: file write: ", end='')
            dprint(formatted_str % data, end='')

class SimStreamer(object):

    def __init__(self, sim900=None, sim921=None, 
                       fname900=None, fname921=None,
                       cmd900=None, cmd921=None):
        self.sim900 = sim900
        self.sim921 = sim921
        self.fname900 = fname900
        self.fname921 = fname921
        self.cmd900 = cmd900
        self.cmd921 = cmd921

        self.signaled = False

    def set_signal(self):
        """For signal (SIGINT, etc.) handling
        """
        self.signaled = True

    def add_nonstream_cmd(self, port, cmd, msg_start, msglen):
        '''Add a command to the non-streaming command list. This should
        be a query command. Unlike the non-streaming one, this one can have
        multiple ports.
        THe commands are stored as port-list of command dictionary.
            {port: [command string, message start byte, message expected length]}

        Arguments:
            port {int} -- port to stream from
            cmd {str} -- a command that the terminal device can understand and
            turns it into the stream mode.
            msg_start {int} -- index of where the message will begin. A typical
                               message return from SIM devices has some fixed
                               number of meta-data bytes prefixed in front of 
                               the message (e.g. #2aaXXXX, the #2aa part is the 
                               prefix), and this number denotes the first position
                               of message byte.
            msglen {int} -- expected length of the message, for validity check.
        '''
        self.ns_commands[port] = [cmd, msg_start, msglen]

    def sim900_proc(self):
