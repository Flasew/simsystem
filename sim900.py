'''sim900.py 

A controller class for SRS SM900 Mainframe that allows streaming (w/SM921) and
slow data reading asynchronously. 

Author: Weiyang Wang [wew168@ucsd.edu]
'''

from __future__ import print_function
import serial
import multiprocessing
import sys
import time
import signal
import numpy as np
from sys import stderr
from datetime import datetime
from multiprocessing import Process, ProcessError, Lock


DEBUG = True

# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint(*args, **kwargs)

class SIM900:

    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE, 
                             stopbits=serial.STOPBITS_ONE, timeout=0.5,
                             waittime=0,
                             s_port=1, s_func=None, s_fname=None,
                             ns_func=None, ns_fname=None):
        '''SIM900 class constructor. Set the serial attributes, and configure the 
        stream/non-streaming ports.
        
        The streaming and non-streaming ports works in the following way:
        If there is a streaming port, only this port's output will be directly 
        passed to the host from SIM900. A dedicated streaming process will be 
        initialized. The streaming thread loops forever until receives a stop
        signal. During the loop. the process will acquire a lock which prevents
        other function from having the serial port. Whenever there is a non-streaming
        read request, which will be initialized as another process,
        it will block until the streaming releases the lock and 
        send the reading command. After the ns-function acquires the lock it will 
        send the query message, release the lock, wait for a few moments (to allow 
        stream to run if there's available data), re-acquire the lock, and try to
        read the data. 

        s_func is the streaming function. It should have a infinite loop and 
        should acquire the lock each time on entering the loop, release the lock
        each time leaving it.

        ns_func is the non-streaming function. It should acquire the lock before
        sending the query request, release the lock, wait for a short time, then
        re-acquire the lock to get the response.

        Notice that both s_func and ns_func will be feed to the Process constructor,
        thus they by themselves need to have no argument. Therefore any arguments
        need to be passed as lambda functions.
        
        Arguments:
            port {str} -- Serial port address under /dev/
        
        Keyword Arguments:
            baudrate {number} -- Serial port baudrate (default: {9600})
            parity {str} -- Serial port parity (default: {serial.PARITY_NONE})
            stopbits {number} -- S-port stop bit (default: {serial.STOPBITS_ONE})
            timeout {number} -- serial port timeout (default: {None})
            waittime {number} -- time to wait for a query command
            s_port {number} -- port to enable stream, for SIM921. If streaming 
                               is not used, set this value to -1(default: 1)
            s_func {function} -- Function for streaming process. If set to 
                                 None, will automatically use self.stream_sim921
                                 with the previous streaming port. (default: {None})
            s_fname {str} -- file to store streamed data. If none, a file with 
                            name "YYYYMMDDHHMMstream.csv" will be created
            ns_func {function} -- function run for non-streaming reading. If 
                                  there is no streaming, it might be better 
                                  to not use this functionality but just
                                  use the query commands (default: {None})
            ns_fname {str} -- file to store non-streamed data. If none, a file with 
                             name "YYYYMMDDHHMMnostream.csv" will be created
        '''

        # Deal with the serial port 
        self.ser = serial.Serial(port, baudrate=baudrate, 
                                       parity=parity, 
                                       stopbits=stopbits,
                                       timeout=timeout)

        if not self.ser.is_open:
            self.ser.open()
        
        self.waittime = waittime
        # Steaming part
        
        # lock that controls the async behavior
        self.lock = Lock()

        self.s_port = s_port
        self.s_func = s_func if s_func else \
                      (None if s_port == -1 else self.stream_sim921)
        self.s_fname = \
            "{:s}stream.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))\
            if s_fname is None else s_fname
        self.s_file = open(self.s_fname, 'w+')
        self.s_buf = []
        
        # Non-streaming part
        self.ns_func = ns_func if ns_func else self.non_stream
        self.ns_fname = \
            "{:s}nostream.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))\
            if ns_fname is None else ns_fname
        self.ns_file = open(self.ns_fname, 'w+')
        self.ns_buf = []

        self.configure()
        self.signaled = False

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()
        if not self.s_file.closed:
            self.s_file.close()
        if not self.ns_file.closed:
            self.ns_file.close()

    def set_signal(self):
        """For signal (SIGINT, etc.) handling
        """
        self.signaled = True

    def configure(self):
        '''Set all termination to LF, set the port for streaming to pass 
        through mode.
        '''
        for i in range(1, 10):
            self.sendcmd("TERM", port=i, literal="LF")
            self.sendcmd("SNDT", port=i, str_block=self.makecmd("TERM", literal=0))
        if self.s_port != -1:
            self.sendcmd("RPER", num=2 ** self.s_port)

    def send(self, message):
        '''General purpose send
        
        Arguments:
            message {str} -- message to send
        '''
        message += '\n'
        dprint("DEBUG: send ", end='')
        dprint(message)
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

    def makecmd(self, command, port=None, str_block=None, literal=None, num=None):
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

    def sendcmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-send
        '''
        message = self.makecmd(command, port, str_block, literal, num)
        self.send(message)

    def querycmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-query
        '''
        message = self.makecmd(command, port, str_block, literal, num)
        return self.query(message)

    def parse_getn(self, msg):
        '''Parse a response from getn'''
        try:
            msglen = int(msg[2:5].lstrip('0'))
            return msg[-msglen:].rstrip() 
        except ValueError:
            return ''

    def parse_pth(self, msg):
        return self.parse_getn(msg[5:].lstrip())
        
    def stream_sim921(self):
        '''Stream-reading working function for sim921 module.
        Stream function should handle file header.
        '''
        # start the stream 
        dprint("DEBUG: Streaming process started.")
        self.s_file.write("Time, tval\n")

        self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("TPER", num=100))
        self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("TVAL?", num=0))

        while not self.signaled:
            self.lock.acquire()
            tval = self.parse_pth(self.recv())
            currtime = int(round(time.time() * 1000))
            dprint("DEBUG: sfunc ", end='')
            dprint(tval, currtime)

            self.s_file.write("{:d}, {:s}\n".format(currtime, tval))

            dprint("DEBUG: s_file write ", end='')
            dprint("{:d}, {:s}\n".format(currtime, tval))

            #self.s_buf.append([currtime, tval])
            #print(self.s_buf)
            self.lock.release()
            time.sleep(0.01)

        self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("SOUT"))
        self.s_file.flush()
        dprint("DEBUG: Streaming process stopped.")

    def non_stream(self):
        '''Non-streaming reading worker function. Also handles buffer-clear 
        for the streaming thread.

        Lock the port, make all the query requests, release the lock, wait for a
        while, then re-acquire the lock and perform all the readings. 

        This method assumes 100ms is enough for a lock-read-unlock period for
        the streaming function.
        '''
        dprint("DEBUG: Non-streaming process started.")
        self.ns_file.write("Time, SN1, SN2, SN3\n")

        while not self.signaled:
            self.lock.acquire()
            
            # query whatever is wanted
            self.sendcmd("SNDT", 4, str_block="*IDN?")
            self.sendcmd("SNDT", 5, str_block="*IDN?")
            self.sendcmd("SNDT", 6, str_block="*IDN?")
            currtime = int(round(time.time() * 1000))
            self.lock.release()

            time.sleep(1)

            self.lock.acquire()
            # disable pass through
            self.sendcmd("RPER", num=0)

            sn4 = self.parse_getn(self.querycmd("GETN?", 4, num=128))
            sn5 = self.parse_getn(self.querycmd("GETN?", 5, num=128))
            sn6 = self.parse_getn(self.querycmd("GETN?", 6, num=128))

            self.sendcmd("RPER", num=2 ** self.s_port)

            # write to file
            # print(len(self.s_buf))
            # for i in range(len(self.s_buf)):
                
            # self.s_buf[:] = []

            self.lock.release()
            self.ns_file.write("{:d}, {:s}, {:s}, {:s}\n".format(currtime, sn4, sn5, sn6))

            dprint("DEBUG: ns_file write ", end='')
            dprint("{:d}, {:s}, {:s}, {:s}\n".format(currtime, sn4, sn5, sn6))

        self.ns_file.flush()
        dprint("DEBUG: Non-streaming process stopped.")


    def start(self):
        '''Start streaming
        '''
        # signal handling.
        self.signaled = False
        # stores the original signals
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sighup = signal.getsignal(signal.SIGHUP)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        # set the new signal handlers
        signal.signal(signal.SIGINT, lambda s, f: self.set_signal())
        signal.signal(signal.SIGHUP, lambda s, f: self.set_signal())
        signal.signal(signal.SIGTERM, lambda s, f: self.set_signal())

        s_process = Process(target = self.s_func)
        ns_process = Process(target = self.ns_func)

        s_process.start()
        ns_process.start()
        dprint("DEBUG: Both run called.")

        s_process.join()
        ns_process.join()

        # restore the original handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGHUP, original_sighup)
        signal.signal(signal.SIGTERM, original_sigterm)


    




























