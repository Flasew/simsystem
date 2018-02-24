from __future__ import print_function
import multiprocessing
import signal
import ctypes
from multiprocessing import Process, ProcessError, RLock, Manager
from simframe import SIM900, SIM921
from simutil import *
from pynput import keyboard


class SimStreamer(object):

    def __init__(self, slow_dev=None, fast_dev=None,
                 fname_slow_dev='/dev/stdout', fname_fast_dev='/dev/stdout',
                 cmd_slow_dev=[], cmd_fast_dev=''):
        self.slow_dev = slow_dev
        self.fast_dev = fast_dev
        self.fname_slow_dev = fname_slow_dev
        self.fname_fast_dev = fname_fast_dev
        self.cmd_slow_dev = cmd_slow_dev        #list of dictionary
        self.cmd_fast_dev = cmd_fast_dev

        self.proc_slow_dev = None
        self.proc_fast_dev = None

        self.lock = RLock()
        self.latest_fast_data = multiprocessing.Value(ctypes.c_double, 0)

        self.fast_dev_signaled = False
        self.slow_dev_signaled = False

        self.kb_listener = None

    def set_signal(self):
        """For signal (SIGINT, etc.) handling
        """
        self.fast_dev_signaled = True
        self.slow_dev_signaled = True

    def add_cmd_slow_dev(self, port, cmd):
        """Add a command to the non-streaming command list.

        Arguments:
            port {int} -- port to stream from
            cmd {str} -- a command that the terminal device can understand 
        """
        self.cmd_slow_dev.append({'port': port, 'cmd': cmd})

    def slow_dev_proc(self):
        dprint('DEBUG: slow_dev process started')
        with open(self.fname_slow_dev, 'w+') as f:

            while not self.signaled:

                writecache = [mtime()]

                for req in self.cmd_slow_dev:

                    self.slow_dev.pconnect(req['port'])
                    readout = self.slow_dev.query(req['cmd']).rstrip()
                    if len(readout) == 0:
                        readout = 'TIMEOUT'
                    writecache.append(readout)
                    self.slow_dev.pdisconnect()

                if self.proc_fast_dev:
                    writecache.append("{:+.6E}".format(self.latest_fast_data.value))
                else:
                    writecache.append("FASTDATA_NOT_ATTACHED")

                for i in range(len(writecache)):
                    if i != len(writecache) - 1:
                        f.write(str(writecache[i]) + ', ')
                    else:
                        f.write(writecache[i])
                f.write('\n')

            time.sleep(self.slow_dev.tper / 1000.0)
        dprint('DEBUG: slow_dev process exited')
        
    
    def kb_toggle_fast_dev(self, key):
        """callback function to toggle the fastdata streaming."""
        if key == keyboard.Key.f9:
            if self.proc_fast_dev:
                eprint("Toggle fast data: OFF")
                self.fast_dev_signaled = True
                self.proc_fast_dev.join()
                self.proc_fast_dev = None
            else:
                eprint("Toggle fast data: ON")
                self.fast_dev_signaled = False
                self.proc_slow_dev = Process(target=self.slow_dev_proc)
                self.proc_slow_dev.start()
                


    def fast_dev_proc(self):
        dprint('DEBUG: fast_dev process started')
        self.fast_dev.send(self.cmd_fast_dev)

        with open(self.fname_fast_dev, 'w+') as f:

            while not self.signaled:

                readout = self.fast_dev.recv().rstrip()
                currtime = mtime()

                if len(readout) == 0:
                    readout = 'TIMEOUT'

                self.latest_fast_data.value = float(readout)
                
                f.write(str(currtime))
                f.write(', ' + readout + '\n')

            self.fast_dev.send('SOUT')

        dprint('DEBUG: fast_dev process exited')

    def start(self, run_slow_dev=True, run_fast_dev=False, block=True):
        """Start streaming.
        Press f9 key to toggle fast data functionality
        """

        self.fast_dev_signaled = False
        self.slow_dev_signaled = False
        
        # setup kb listener
        
        keyboard_listener = keyboard.Listener(on_press=self.kb_toggle_fast_dev)
        keyboard_listener.start()
        
        # if block:
        # signal handling.
        # stores the original signals
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sighup = signal.getsignal(signal.SIGHUP)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        # set the new signal handlers
        signal.signal(signal.SIGINT, lambda s, f: self.set_signal())
        signal.signal(signal.SIGHUP, lambda s, f: self.set_signal())
        signal.signal(signal.SIGTERM, lambda s, f: self.set_signal())

        if run_fast_dev:
            self.proc_fast_dev = Process(target=self.fast_dev_proc)
            self.proc_fast_dev.start()

        if run_slow_dev:
            self.proc_slow_dev = Process(target=self.slow_dev_proc)
            self.proc_slow_dev.start()
        
        # if block:
        if run_slow_dev:
            self.proc_slow_dev.join()
        if run_fast_dev:
            self.proc_fast_dev.join()
            
        keyboard_listener.stop()

        self.proc_slow_dev = None
        self.proc_fast_dev = None

        # restore the original handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGHUP, original_sighup)
        signal.signal(signal.SIGTERM, original_sigterm)

    # def stop(self):
    #
    #     self.set_signal()
    #
    #     if self.proc_slow_dev:
    #         self.proc_slow_dev.join()
    #     if self.proc_fast_dev:
    #         self.proc_fast_dev.join()
    #
    #     self.proc_slow_dev = None
    #     self.proc_fast_dev = None

    def start_kb_listener(self):

        if self.kb_listener:
            self.kb_listener.stop()

        self.keyboard_listener = keyboard.Listener(on_press=self.kb_toggle_fast_dev)
        self.keyboard_listener.start()

    def stop_kb_listener(self):

        if self.kb_listener:
            self.kb_listener.stop()

        self.kb_listener = None

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