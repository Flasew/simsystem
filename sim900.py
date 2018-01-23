'''sim900.py 

A controller class for SRS SM900 Mainframe that allows streaming (w/SM921) and
slow data reading asynchronously. 

Author: Weiyang Wang [wew168@ucsd.edu]
'''

from __future__ import print_function
import serial
import multiprocessing
from multiprocessing import Process, ProcessError, Lock
import sys
import time
import numpy as np

class SIM900:

    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE, 
                             stopbits=serial.STOPBITS_ONE, timeout=None,
                             s_port=1,
                             s_func=None,
                             ns_func=None):
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
            s_port {number} -- port to enable stream, for SIM921. If streaming 
                               is not used, set this value to -1(default: 1)
            s_func {function} -- Function for streaming process. If set to 
                                 None, will automatically use self.stream_sim921
                                 with the previous streaming port. (default: {None})
            ns_func {function} -- function run for non-streaming reading. If 
                                  there is no streaming, it might be better 
                                  to not use this functionality but just
                                  use the query commands (default: {None})
        '''

        # Deal with the serial port 
        self.ser = serial.Serial(port, baudrate=baudrate, 
                                       parity=parity, 
                                       stopbits=stopbits,
                                       timeout=timeout)

        if not self.ser.is_open:
            self.ser.open()
        
        # Steaming part
        
        # lock that controls the async behavior
        self.lock = Lock()

        self.s_port = s_port
        self.s_func = s_func if s_func else \
                      (None if s_port == -1 else \
                        lambda: self.stream_sim921(s_port))
        self.s_buf = []
        self.s_run = False


        # Non-streaming part
        self.ns_func = ns_func if ns_func else self.non_stream
        self.ns_buf = []

        self.configure()

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

    def configure(self):
        '''Set all termination to LF, set the port for streaming to pass 
        through mode.
        '''
        for i in range(1, 0xE):
            self.set("TERM", port=i, str_block="LF")
        if self.s_port != -1:
            self.set("RPER", integer=2 ** self.s_port)

    def send(self, message):
        '''General purpose send
        
        Arguments:
            message {str} -- message to send
        '''
        message += '\n'
        self.ser.write(message)

    def recv(self):
        '''General purpose receive
        
        Returns whatever is returned from the device, up to a LF.
        '''
        return self.ser.readline()

    def set(self, command, port=None, str_block=None, integer=None):
        '''a 'set' command does not have a return value. All arguments
        correspond to a field in the generalized command format (see 2-13 of 
        the instruction book of SIM900).
        
        Arguments:
            command {str} -- 4-letter command string       
        
        Keyword Arguments:
            port {number} -- port that this command should be route to. If set
                             to None, will only be send to mainframe (default: {None})
            integer {number} -- integer field of command (default: {None})
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
        if str_block: 
            message += ("," if port else " ") + str_block
        if integer:
            message += ("," if port or str_block else " ") + str(integer)

        self.send(message)


    def query(self, command, port=None, integer=None, 
              str_block=None, waittime=0):
        '''a 'query' command has a return value. All arguments
        correspond to a field in the generalized command format (see 2-13 of 
        the instruction book of SIM900).
        
        Arguments:
            command {str} -- 4-letter command string       
        
        Keyword Arguments:
            port {number} -- port that this command should be route to. If set
                             to None, will only be send to mainframe (default: {None})
            integer {number} -- integer field of command (default: {None})
            str_block {str} -- Multi-byte (string) block field of the command. 
                               If uses the Quote-delimited strings, please also
                               include the outer quotes since ' and " can be confusing.
                               If the field has a literal token instead of a 
                               string block, also put it here (of course without
                               the outer quotes.)
            waittime {int} -- time to wait before receive 
        '''
        message = command + "?"
        if port:    
            message += " " + str(port)
        if str_block: 
            message += ("," if port else " ") + str_block
        if integer:
            message += ("," if port or str_block else " ") + str(integer)

        self.send(message)

        time.sleep(waittime)

        return self.recv()

    def stream_sim921(self, port):
        pass

    def non_stream(self):
        pass





























