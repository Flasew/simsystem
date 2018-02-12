import serial
import time

with open('port_config.txt', 'r') as f:
    text = f.readlines()
    SIM900devicePort = '/dev/' + text[0].split('\n')[0]
print 'SIMinterface port =', SIM900devicePort

#devicePort = '/dev/ttyUSB0' #USB to serial device
escapeString = 'xyz' #some random string of letters that won't ever look like a command
serialBaudRate = 9600 #default for the 922
serialTimeout = 1

responseWaitTime = 0.25 #seconds

class SIMinterface():
    def __init__(self):
        self.devicePort = SIM900devicePort
        self.escapeString = escapeString
        self.serialBaudRate = serialBaudRate
        self.serialTimeout = serialTimeout
        self.verbose = False
        self.confSerial()
        self.openSerial()

    def confSerial(self):
        self.Sim = serial.Serial()
        self.Sim.port = self.devicePort
        self.Sim.baudrate = self.serialBaudRate
        self.Sim.timeout = self.serialTimeout

        if self.Sim.isOpen():
            self.closeSerial()

    def openSerial(self):
        self.Sim.open()
        self.Sim.write('CONS OFF') #turn console mode off incase it's on
#		self.Sim.write(self.escapeString)
        self.getFullDeviceID()

    def clearStatus(self):
        self.write('*CLS')

    def closeSerial(self):
        self.Sim.close()

    def connectToMainframePort(self, port):
        self.write('CONN {0}, "{1}"'.format(port, self.escapeString))
        time.sleep(responseWaitTime)

    def escape(self):
        self.write(escapeString)

    def flushOutput(self):
        self.write('FLSO')

    def flushBuffers(self):
        self.write('FLSH')

    def write(self,message):
        message = message + '\r\n'
        self.Sim.write(message)
        if self.verbose:
            print message

    def readline(self):
        return self.Sim.readline()

    def getDeviceID(self):
        id = self.getFullDeviceID()
        try:
            return id.split(',')[1]
        except IndexError:
            return 'None'

    def getFullDeviceID(self):
        return self.query('*IDN?')

    def initDiodeCal(self, channel,curvename):
        self.write('CINI {0},0,"{1}"'.format(channel,curvename))

    def queryDiodeCal(self,channel):
        return self.query('CINI? {0}'.format(channel))

    def addCalPoint(self, voltpoint, temppoint):
        self.write('CAPT 4,{0},{1}'.format(voltpoint, temppoint))

    def queryCalPoint(self, calpoint):
        return self.query('CAPT? 4,{0}'.format(calpoint))

    def selectCalCurve(self, channel):    #curve can be 'STAN 0' or 'USER 1'
        self.write('CURV {0},1'.format(channel))

    def queryCalCurve(self, channel):
        return self.query('CURV? {0}'.format(channel))

    def query(self, message):
        self.write(message)
        time.sleep(responseWaitTime)
        return self.readline().rstrip()

    def SIM922getDiodeVoltages(self):
        volts = self.query('VOLT? 0,1')
        volts = volts.split(',')
        try:
            voltages = map(float, volts)
        except ValueError:
            voltages = [float('nan')]
        return voltages

    def SIM922getDiodeTemps(self):
        temps = self.query('TVAL? 0,1')
        temps = temps.split(',')
        try:
            temperatures = map(float,temps)
        except ValueError:
            temperatures = [float('nan')]
        return temperatures

    def SIM925switchMUX(self,channel):
        self.write('CHAN {0}'.format(channel))

    def setCalCurveAC(self,channel):
        self.write('CURV {0}'.format(channel))

    def queryCalCurveAC(self):
        return self.query('CURV?')

    def getTempAC(self):
        temp = self.query('TVAL?')
        return temp

    def getResistanceAC(self):
        resistance = self.query('RVAL?')
        return resistance

    def SIM921setExcitationOnOff(self,state):
        self.write('EXON {0}'.format(state))

    def SIM921setExcitationRange(self,e_int):
        self.write('EXCI {0}'.format(e_int))

    def SIM921excitation_q(self):
        return self.query('EXON?')

    def SIM921setResistanceRange(self,r_int):
        self.write('RANG {0}'.format(r_int))

    def SIM921setExcitationFreq(self, freq):
        self.write('FREQ {0}'.format(freq))

    def SIM921getExcitationFreq(self):
        return self.query('FREQ?')

    def SIM921setTimeConstant(self, tau):
        self.write('TCON {0}'.format(tau))

    def SIM921getTimeConstant(self):
        return self.query('TCON?')
