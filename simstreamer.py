from __future__ import print_function
import multiprocessing
import signal
import ctypes
from multiprocessing import Process, ProcessError, RLock, Manager
from simframe import SIM921
from simutil import *
from pynput import keyboard
import numpy as np


class SimStreamer(object):

    def __init__(self, sim921=None,
                 fname921='/dev/stdout',
                 fname921raw=None,
                 interp_data = None,
                 cmd921=''):
        self.fast_dev = sim921
        self.fname_fast_dev = fname921
        self.fname_fast_dev_raw = fname921raw
        self.interp_data = interp_data
        self.interp_data = np.flipud(self.interp_data)
        self.calTemp = self.interp_data[:, 0]
        self.calMeasured = self.interp_data[:, 1]
        self.cmd_fast_dev = cmd921

        self.proc_fast_dev = None

        self.lock = RLock()
        self.latest_fast_data = multiprocessing.Value(ctypes.c_double, 0)
        self.latest_fast_data_raw = multiprocessing.Value(ctypes.c_double, 0)

        self.signaled = False

        self.kb_listener = None

    def set_signal(self):
        """For signal (SIGINT, etc.) handling
        """
        dprint("Setting Signal...")
        self.signaled = True


    def fast_dev_proc(self):
        dprint('DEBUG: fast_dev process started')
        self.fast_dev.send(self.cmd_fast_dev)

        with open(self.fname_fast_dev, 'a+') as f, open(self.fname_fast_dev_raw, 'a+') as fr:

            while not self.signaled:
                try:
                    readout = self.fast_dev.recv().rstrip()
                    currtime = mtime()

                    try:
                        if len(readout) == 0:
                            readout = '-1'
                            interp = -1
                        else:
                            interp = np.interp(float(readout),self.calMeasured,self.calTemp)

                    except:
                        readout = "nan"
                        interp = float("nan")

                    self.latest_fast_data.value = float(interp)
                    self.latest_fast_data_raw.value = float(readout)

                    f.write(str(currtime))
                    f.write(', ' + "{:+.6E}".format(interp) + '\n')
                    fr.write(str(currtime))
                    fr.write(', ' + readout + '\n')
                except KeyboardInterrupt:
                    break


            self.fast_dev.send('SOUT')


        dprint('DEBUG: fast_dev process exited')

    def start(self):
        '''Start streaming
        '''
        self.signaled = False

        # # signal handling.
        # # stores the original signals
        # original_sigint = signal.getsignal(signal.SIGINT)
        # original_sighup = signal.getsignal(signal.SIGHUP)
        # original_sigterm = signal.getsignal(signal.SIGTERM)
        #
        # # set the new signal handlers
        # signal.signal(signal.SIGINT, lambda s, f: self.set_signal())
        # signal.signal(signal.SIGHUP, lambda s, f: self.set_signal())
        # signal.signal(signal.SIGTERM, lambda s, f: self.set_signal())


        self.proc_fast_dev = Process(target=self.fast_dev_proc)
        self.proc_fast_dev.start()

        self.proc_fast_dev.join()

        self.proc_fast_dev = None

        #
        # # restore the original handlers
        # signal.signal(signal.SIGINT, original_sigint)
        # signal.signal(signal.SIGHUP, original_sighup)
        # signal.signal(signal.SIGTERM, original_sigterm)

    def stop(self):

        self.set_signal()

        if self.proc_fast_dev:
            self.proc_fast_dev.join()

        self.proc_fast_dev = None


