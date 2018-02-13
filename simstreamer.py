from __future__ import print_function
import multiprocessing
import sys
import time
import signal
import numpy as np
import ctypes
import copy
from sys import stderr
from datetime import datetime
from multiprocessing import Process, ProcessError, RLock, Manager
from multiprocessing.queues import SimpleQueue
from simframe import SIM900, SIM921


DEBUG = True

# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint(*args, **kwargs)

# def file_writer(filename, title_line, formatted_str, buf):
#     '''File writing worker function. Buffer is expected to be a queue or a
#     Simplequeue.
#     '''
#     with open(filename, 'w+') as f:

#         f.write(title_line)

#         while True:
#             data = buf.get()
#             if data is None:
#                 break
#             f.write(formatted_str % data)
#             dprint("DEBUG: file write: ", end='')
#             dprint(formatted_str % data, end='')

def mtime():
    return int(round(time.time() * 1000))

class SimStreamer(object):

    def __init__(self, sim900=None, sim921=None, 
                       fname900='/dev/stdout', fname921='/dev/stdout',
                       cmd900=[], cmd921=''):
        self.sim900 = sim900
        self.sim921 = sim921
        self.fname900 = fname900
        self.fname921 = fname921
        self.cmd900 = cmd900        #list of dictionary
        self.cmd921 = cmd921

        self.proc900 = None
        self.proc921 = None

        self.lock = RLock()
        self.latest921data = multiprocessing.Value(ctypes.c_double, 0)

        self.signaled = False

    def set_signal(self):
        """For signal (SIGINT, etc.) handling
        """
        self.signaled = True

    def add_cmd900(self, port, cmd):
        '''Add a command to the non-streaming command list.

        Arguments:
            port {int} -- port to stream from
            cmd {str} -- a command that the terminal device can understand 
        '''
        self.cmd900.append({'port': port, 'cmd': cmd})

    def sim900_proc(self):
        dprint('DEBUG: sim900 process started')
        with open(self.fname900, 'w+') as f:

            while not self.signaled:

                writecache = [mtime()]

                for req in self.cmd900:

                    self.sim900.pconnect(req['port'])
                    readout = self.sim900.query(req['cmd']).rstrip()
                    if len(readout) == 0:
                        readout = 'TIMEOUT'
                    writecache.append(readout)
                    self.sim900.pdisconnect()

                if self.proc921:
                    writecache.append("{:+.6E}".format(self.latest921data.value))

                for i in range(len(writecache)):
                    if i != len(writecache) - 1:
                        f.write(str(writecache[i]) + ', ')
                    else:
                        f.write(writecache[i])
                f.write('\n')

            time.sleep(self.sim900.tper / 1000.0)
        dprint('DEBUG: sim900 process exited')


    def sim921_proc(self):
        dprint('DEBUG: sim921 process started')
        self.sim921.send(self.cmd921)

        with open(self.fname921, 'w+') as f:

            while not self.signaled:

                readout = self.sim921.recv().rstrip()
                currtime = mtime()

                if len(readout) == 0:
                    readout = 'TIMEOUT'

                self.latest921data.value = float(readout)
                
                f.write(str(currtime))
                f.write(', ' + readout + '\n')

            self.sim921.send('SOUT')

        dprint('DEBUG: sim921 process exited')


    def start(self, run900=True, run921=True, block=True):
        '''Start streaming
        '''
        self.signaled = False
        if block:
            # signal handling.
            # stores the original signals
            original_sigint = signal.getsignal(signal.SIGINT)
            original_sighup = signal.getsignal(signal.SIGHUP)
            original_sigterm = signal.getsignal(signal.SIGTERM)

            # set the new signal handlers
            signal.signal(signal.SIGINT, lambda s, f: self.set_signal())
            signal.signal(signal.SIGHUP, lambda s, f: self.set_signal())
            signal.signal(signal.SIGTERM, lambda s, f: self.set_signal())

        if run921:
            self.proc921 = Process(target=self.sim921_proc)
            self.proc921.start()

        if run900:
            self.proc900 = Process(target=self.sim900_proc)
            self.proc900.start()

        
        
        if block:
            if run900:
                self.proc900.join()
            if run921:
                self.proc921.join()

            self.proc900 = None
            self.proc921 = None

            # restore the original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGHUP, original_sighup)
            signal.signal(signal.SIGTERM, original_sigterm)

    def stop(self):

        self.set_signal()

        if self.proc900:
            self.proc900.join()
        if self.proc921:
            self.proc921.join()

        self.proc900 = None
        self.proc921 = None


def main():

    cmd900 = [
        {'port': 4, 'cmd': 'TVAL? 0'},
        {'port': 5, 'cmd': 'TVAL? 0'},
        {'port': 6, 'cmd': 'TVAL? 0'}
    ]
    d = SimStreamer(SIM900('/dev/ttyUSB3'), SIM921('/dev/ttyUSB2'),
                    'test900.csv', 'test921.csv',
                    cmd900,'TVAL? 0')
    d.start()