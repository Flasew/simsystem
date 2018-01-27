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
from multiprocessing.queues import SimpleQueue


DEBUG = True

# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint(*args, **kwargs)

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

def file_writer(filename, title_line, formatted_str, buffer):
    '''File writing worker function. Buffer is expected to be a queue or a
    Simplequeue.
    '''
    with open(filename, 'w+') as f:

        f.write(title_line)

        while True:
            data = buffer.get()
            if data is None:
                break
            f.write(formatted_str % data)


class SIM900:

    def __init__(self, port, baudrate=9600, parity=serial.PARITY_NONE,
                             stopbits=serial.STOPBITS_ONE, timeout=0.5,
                             waittime=0, s_tper=100, ns_tper=1000,
                             s_fname=None, ns_fname=None,
                             s_fheader=None, ns_fheader=None,
                             s_fstr=None, ns_fstr=None):
        '''SIM900 class constructor. Set the serial attributes, and configure the
        stream/non-streaming ports.

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
        '''

        # Deal with the serial port
        self.ser = serial.Serial(port, baudrate=baudrate,
                                       parity=parity,
                                       stopbits=stopbits,
                                       timeout=timeout)

        if not self.ser.is_open:
            self.ser.open()

        self.waittime = waittime

        # stream / non-stream commands
        self.s_command = []
        self.ns_commands = []

        # stream time period
        self.s_tper = s_tper

        # time to wait between non-streaming readings
        self.ns_tper = ns_tper

        # log file attributes
        self.s_fname = s_fname if s_fname else None
        self.ns_fname = ns_fname if ns_fname else None
        self.s_fheader = ''
        self.ns_fheader = ''
        self.s_fstr = None
        self.ns_fstr = None

        # buffers
        self.s_buf = None
        self.ns_buf = None
        self.main_msg = []

        self.configure()
        self.signaled = False

    def __del__(self):
        if self.ser.is_open:
            self.ser.close()

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
            self.sendcmd("SNDT", port=i, str_block=makecmd("TERM", literal=0))
        self.sendcmd("RPER", num=sum([2 ** i for i in range(1, 0xF)]))

    def set_stream_cmd(self, port, cmd, msg_start):
        '''Set the streaming port and command. Notice that only ONE port can be
        streaming, so this command will overwrite whatever was in s_command.

        Arguments:
            port {int} -- port to stream from
            cmd {str} -- a command that the terminal device can understand and
            turns it into the stream mode.
        '''
        self.s_command = [port, cmd, msg_start]

    def add_nonstream_cmd(self, port, cmd, msg_start):
        '''Add a command to the non-streaming command list. This should
        be a query command. Unlike the non-streaming one, this one can have
        multiple ports.
        non-stream command also supports multiple commands for one port.
        THe commands are stored as port-list of command dictionary.

        Arguments:
            port {int} -- port to stream from
            cmd {str} -- a command that the terminal device can understand and
            turns it into the stream mode.
        '''
        self.ns_commands.append([port, cmd, msg_start])

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

    def sendcmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-send
        '''
        message = makecmd(command, port, str_block, literal, num)
        self.send(message)

    def querycmd(self, command, port=None, str_block=None, literal=None, num=None):
        '''Wrapper for makecmd-query
        '''
        message = makecmd(command, port, str_block, literal, num)
        return self.query(message)

    def sorter(self):
        '''A worker function that separates the return value from streaming
        thread from the non-streaming thread. Once a message is received from
        the SIM900, It will be put into either @self.s_buf if it it comes
        from a streaming port, or @self.ns_buf if it is not. Message from the
        mainframe will be put into @self.main_msg list, which is different from
        the other two SimpleQueue FIFO buffers.
        '''
        ns_recv_count = 0
        ns_all_msg = []

        while not self.signaled:

            port, raw_msg = parse_portmsg(self.recv())
            currtime = int(round(time.time() * 1000))

            if port == self.s_command[0]:
                msg = parse_retstr(raw_msg, self.s_command[2])
                self.s_buf.put((currtime, msg))

            elif port == 0:
                self.main_msg.append([currtime, msg])

            elif port == -1:
                eprint("WARNING: Serial port timed out")
                continue

            else:
                if ns_recv_count == 0:
                    ns_all_msg.append(currtime)

                ns_all_msg.append(
                    parse_retstr(raw_msg, self.ns_commands[ns_recv_count][2]))

                ns_recv_count += 1

                if ns_recv_count == len(self.ns_commands):
                    self.ns_buf.put(tuple(ns_all_msg))
                    ns_recv_count = 0
                    ns_all_msg[:] = []

        # put nones for exit
        self.sendcmd("SNDT", self.s_command[0], str_block="SOUT")
        self.s_buf.put(None)
        self.ns_buf.put(None)

    def ns_cmd_sender(self):
        while not self.signaled:
            for cmd in self.ns_commands:
                self.sendcmd("SNDT", cmd[0], str_block=cmd[1])
            time.sleep(self.ns_tper/1000.0)

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

        self.s_buf = SimpleQueue()
        self.ns_buf = SimpleQueue()

        s_fname = self.s_fname if self.s_fname else "{:s}stream.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))
        ns_fname = self.ns_fname if self.ns_fname else "{:s}nostream.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))

        s_fwrite_proc = Process(target = \
            lambda: file_writer(s_fname, self.s_fheader, self.s_fstr, self.s_buf))
        ns_fwrite_proc = Process(target = \
            lambda: file_writer(ns_fname, self.ns_fheader, self.ns_fstr, self.ns_buf))
        sort_proc = Process(target = self.sorter)
        ns_proc = Process(target = self.ns_cmd_sender)

        self.sendcmd("SNDT", self.s_command[0], str_block=makecmd("TPER", num=self.s_tper))
        self.sendcmd("SNDT", self.s_command[0], str_block=self.s_command[1])

        s_fwrite_proc.start()
        ns_fwrite_proc.start()
        sort_proc.start()
        ns_proc.start()

        sort_proc.join()
        ns_proc.join()
        s_fwrite_proc.join()
        ns_fwrite_proc.join()

        del self.s_buf
        del self.ns_buf

        # restore the original handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGHUP, original_sighup)
        signal.signal(signal.SIGTERM, original_sigterm)

def main():
    d = SIM900('/dev/ttyUSB0', s_fname="tests.csv", ns_fname="testns.csv")
    d.s_fheader = "Time, TVal\n"
    d.ns_fheader = "Time, sn4, sn5, sn6\n"
    d.s_fstr = "%d, %s\n"
    d.ns_fstr = "%d, %s, %s, %s\n"
    d.set_stream_cmd(1, makecmd("TVAL?", num=0), 4)
    d.add_nonstream_cmd(4, "*IDN?", 5)
    d.add_nonstream_cmd(5, "*IDN?", 5)
    d.add_nonstream_cmd(6, "*IDN?", 5)
    d.start()

# if __name__ == '__main__':
#    main()


    # def stream_sim921(self):
    #     '''Stream-reading working function for sim921 module.
    #     Stream function should handle file header.
    #     '''
    #     # start the stream
    #     dprint("DEBUG: Streaming process started.")

    #     self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("TPER", num=100))
    #     self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("TVAL?", num=0))

    #     while not self.signaled:
    #         self.lock.acquire()
    #         tval = self.parse(self.recv(), 8, 10)
    #         currtime = int(round(time.time() * 1000))
    #         dprint("DEBUG: sfunc ", end='')
    #         dprint(tval, currtime)

    #         self.s_buf.put((currtime, tval))
    #         self.lock.release()
    #         time.sleep(0.01)

    #     self.sendcmd("SNDT", self.s_port, str_block=self.makecmd("SOUT"))
    #     self.s_buf.put(None)

    #     dprint("DEBUG: Streaming process stopped.")

    # def non_stream(self):
    #     '''Non-streaming reading worker function. Also handles buffer-clear
    #     for the streaming thread.

    #     Lock the port, make all the query requests, release the lock, wait for a
    #     while, then re-acquire the lock and perform all the readings.

    #     This method assumes 100ms is enough for a lock-read-unlock period for
    #     the streaming function.
    #     '''
    #     dprint("DEBUG: Non-streaming process started.")

    #     while not self.signaled:
    #         self.lock.acquire()

    #         # query whatever is wanted
    #         self.sendcmd("SNDT", 4, str_block="*IDN?")
    #         self.sendcmd("SNDT", 5, str_block="*IDN?")
    #         self.sendcmd("SNDT", 6, str_block="*IDN?")
    #         currtime = int(round(time.time() * 1000))

    #         self.lock.release()

    #         time.sleep(1)
    #         res = [currtime]

    #         for port in (4,5,6):

    #             self.lock.acquire()
    #             self.sendcmd("RPER", num=0)
    #             # sn4 = 'N'
    #             # sn5 = 'N'
    #             # sn6 = 'N'
    #             self.sendcmd("RPER", num=2**port)
    #             res.append(self.parse(self.recv(), 2, 5))
    #             # sn5 = self.parse(self.querycmd("GETN?", 5, num=128), 2, 5)
    #             # sn6 = self.parse(self.querycmd("GETN?", 6, num=128), 2, 5)


    #             self.sendcmd("RPER", num=2 ** self.s_port)
    #             self.lock.release()
    #             time.sleep(0.01)

    #         self.ns_buf.put(tuple(res))

    #     self.ns_buf.put(None)
    #     dprint("DEBUG: Non-streaming process stopped.")

    #"{:s}nostream.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))
































