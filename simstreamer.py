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

    
    def kb_insert_fast_dev(self, key):
        """callback function to insert the fastdata streaming."""
        if key == keyboard.Key.f9:

            eprint("Toggle fast data: ON")
            self.signaled = False
            self.proc_fast_dev = Process(target=self.fast_dev_proc)
            self.proc_fast_dev.start()

    def fast_dev_proc(self):
        dprint('DEBUG: fast_dev process started')
        self.fast_dev.send(self.cmd_fast_dev)

        with open(self.fname_fast_dev, 'a+') as f, open(self.fname_fast_dev_raw, 'a+') as fr:

            while not self.signaled:

                readout = self.fast_dev.recv().rstrip()
                currtime = mtime()

                if len(readout) == 0:
                    readout = '-1'
                    interp = -1
                else:
                    interp = np.interp(float(readout),self.calMeasured,self.calTemp)

                self.latest_fast_data.value = float(interp)
                self.latest_fast_data_raw.value = float(readout)
                
                f.write(str(currtime))
                f.write(', ' + "{:+.6E}".format(interp) + '\n')
                fr.write(str(currtime))
                fr.write(', ' + readout + '\n')


            self.fast_dev.send('SOUT')

        dprint('DEBUG: fast_dev process exited')

    def stop(self):

        self.set_signal()

        if self.proc_fast_dev:
            self.proc_fast_dev.join()

        self.proc_fast_dev = None

    def start_kb_listener(self):

        if self.kb_listener:
            self.kb_listener.stop()

        self.keyboard_listener = keyboard.Listener(on_press=self.kb_insert_fast_dev)
        self.keyboard_listener.start()

    def stop_kb_listener(self):

        if self.kb_listener:
            self.kb_listener.stop()

        self.kb_listener = None
