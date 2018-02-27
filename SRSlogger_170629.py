# -*- coding: utf-8 -*-
"""
Created on Fri Feb 05 09:49:49 2016

@author: Logan

###############################################################################
This is a temperature logging script for the Stanford Research Systems (SRS)
Small Instrumentation Modules (SIMs).

It WILL break if you try to use it with 'simInterface.py' so YOU MUST USE
'SIMinterface.py' as I have changed some function names to increase clarity.

If you need more info on this script you can either:
    1) Run the script with the help command line option, i.e.
       'python SRSlogger.py -h'. This will describe possible command line
       options.
    2) Consult 'SRSlogger README.txt' or look on the UCSD cosmology wiki under
       'TemperatureLogging'

###############################################################################
"""

#-----------------------------------------------------------------------------#
#-----------------------------------------------------------------------------#
#                                   MAIN                                      #
#-----------------------------------------------------------------------------#
#-----------------------------------------------------------------------------#
from simstreamer import SimStreamer
from simframe import SIM921

def main():
    # Setup some useful path variables
    basePath = sp.check_output('pwd').split('\n')[0]
    sensorPath = basePath + '/Sensors/'
    sys.path.append(basePath)
    print 'Base path =', basePath
    # Parse the command line options
    (opts, args) = parseOptions(basePath)
    #print opts
    # Check that the /Sensors and /Data folders exist. If /Sensors doesn't exist
    # quit, if /Data doesn't exist create it and continue
    checkFolders(basePath)
    # Check to make sure the config file exists and is correct.
    PORT_CONFIG_FILE = basePath + '/port_config.txt'
    #checkUSBportConfig(PORT_CONFIG_FILE, opts.USBport)
    # Load sensor names and calibration file names from file
    (sensors, calibrationFile) = \
        loadSensorNamesAndCalFiles(sensorPath + opts.sensorAndCalNamesFile,
        sensorPath, opts.nMux + 4*opts.nDiodeMod + 1)
    # Once the USB port is checked and loaded we can import SIMinterface
    from SIMinterface import SIMinterface
    time.sleep(.1)
    # Setup data files and write the file headers
    (dataFile, dataFileRaw, dataFileFast, dataFileRawFast) = \
        init_data_file(opts, basePath, sensors)
    SIM = SIMinterface()

    fast_dev = SIM921(opts.fastUSBport)
    streamer = SimStreamer(sim921=fast_dev, fname921=dataFileFast,
                           fname921raw=dataFileRawFast, cmd921='RVAL? 0',
                           interp_data=np.loadtxt(calibrationFile[-1], skiprows=4))

    time.sleep(.2)


    try:
        # PTC SIM900 mainframe full device ID:
        # 'Stanford_Research_Systems,SIM900,s/n072195,ver3.5':
        # Wet lab SIM900 mainframe full device ID:
        # 'Stanford_Research_Systems,SIM900,s/n105263,ver3.6'

        # Check that the correct SIM900 mainframe is connected. Make sure this
        # is the full device ID of the specific SIM900 mainframe you are using.
        print 'Initializing serial interface...'
        SIM.connectToMainframePort(0)
        SIMid = SIM.getFullDeviceID()
        time.sleep(.2)
        if SIMid != 'Stanford_Research_Systems,SIM900,s/n130796,ver3.6':
            print 'Failed to connect to SIM900. Check device ID, USB port, ' \
                'or try power cycling.'
            print 'Device ID:', SIM.getFullDeviceID()
            sys.exit()
        print 'Done.\n'
        SIM.connectToMainframePort(1)
        #SIM.SIM921setExcitationFreq(60)
        SIM.SIM921setExcitationFreq(opts.freq921)
        print 'Excitation frequency:', SIM.SIM921getExcitationFreq(), 'Hz\n'
        SIM.SIM921setTimeConstant(opts.tau921)
        print 'Time constant:', SIM.SIM921getTimeConstant(), '\n'

        # calibrate sim921 fast data
        fast_dev.setExcitationFreq(opts.freq921)
        fast_dev.setTimeConstant(opts.tau921)
        fast_dev.setResistanceRange(opts.resistanceRangeFast)
        if opts.exciteRange921 == -1:
            SIM.SIM921setExcitationRange(6)

        # If we have specified a constant excitation range use that
        elif opts.exciteRange921 != -1:
            print 'Fixed excitation chosen: ' + str(opts.exciteRange921)
            fast_dev.setExcitationRange(opts.exciteRange921)

        streamer.start_kb_listener()

        # Initialize variables for the first iteration. The excitation and
        # resistance ranges are autoset after the first iteration. For the first
        # iteration excitation is set to max and resistance range is set to the
        # command line specification or option parser default.
        FIRST_ITERATION = True
        exciteRange921 = np.zeros(opts.nMux, int)
        resistanceRange = np.array(opts.resistanceRange921)
        # This loop measures and records all temperature sensors. It will run
        # until you press ctrl+c or there is a problem connecting to the SRS
        # mainframe or one of its modules.
        while True:
            if FIRST_ITERATION == True:
                print 'First pass.'
            # Initialize variables and data arrays for each iteration
            temperatureData = np.array([])
            rawData = np.array([])
            resistance = np.array([])
            # Disconnect from any SIM module in case we are still connected
            SIM.escape()
            # Record the time when the measurement loop begins
            loopStartTime = time.time()
            temperatureData = np.append(temperatureData, loopStartTime)
            rawData = np.append(rawData, loopStartTime)

            #########################################################
            # Measure all SIM921 resistances. Loop over mux channel #
            #########################################################

            for ch in range(opts.nMux):
                # Connect to SIM925 mux and switch to desired channel
                SIM.connectToMainframePort(opts.SIM925port)
                SIM.SIM925switchMUX(ch + 1)
                SIM.escape()
                SIM.connectToMainframePort(opts.SIM921port)
                # Set excitation and resistance range to initial values if
                # this is the first iteration
                if FIRST_ITERATION == True:
                    SIM.SIM921setResistanceRange(opts.resistanceRange921[ch])
                    if opts.exciteRange921 == -1:
                        SIM.SIM921setExcitationRange(6)

                    # If we have specified a constant excitation range use that
                    elif opts.exciteRange921 != -1:
                        print 'Fixed excitation chosen: ' + str(opts.exciteRange921)
                        SIM.SIM921setExcitationRange(opts.exciteRange921)
                # If this isn't the first iteration, set the excitation and
                # resistance ranges to the appropriate values gathered from the
                # previous iteration.
                elif opts.exciteRange921 != -1:
                    print 'Fixed excitation chosen: ' + str(opts.exciteRange921)
                    SIM.SIM921setExcitationRange(opts.exciteRange921)
                else:
                    SIM.SIM921setExcitationRange(exciteRange921[ch])
                    SIM.SIM921setResistanceRange(resistanceRange[ch])
                # Take resistance measurement and append
                res = SIM921measureResistance(opts, SIM, ch)
                res = abs(float(res))
                SIM.escape()
                resistance = np.append(resistance, res)
                rawData = np.append(rawData, res)
                # Print mux resistances if desired
                if opts.PRINT_MUX_RES == True:
                    print 'Mux', ch + 1, ': ', res, 'Ohms'
                    print 'Auto excitation =', exciteRange921[ch], ', Auto resistance =', resistanceRange[ch]
                # Interpolate mux resistances to temperatures and store
                muxT = interpRaw(res, calibrationFile[ch])
                temperatureData = np.append(temperatureData, muxT)
                # Select and store resistance and excitation range for next
                # iteration
                resistanceRange[ch] = autoSelSIM921Resistance(opts, resistance[ch], ch)
                exciteRange921[ch] = autoSelSIM921Excitation(temperatureData[ch + 1])
            print ''

            #########################################################
            # Measure all diode voltages. Loop over mainframe port. #
            #########################################################

            for diodeMod in range(opts.nDiodeMod):
                diodeVolts = np.array([])
                diodeTemps = np.array([])
                port = opts.diodeModStart + diodeMod
                SIM.connectToMainframePort(port)
                diodeVolts = SIM.SIM922getDiodeVoltages()
                if opts.PRINT_DIODE_VOLTS == True:
                    print 'Diode Module', diodeMod,  'Voltages:', diodeVolts
                rawData = np.append(rawData, diodeVolts)
                SIM.escape()
                # Interpolate diode voltages to temperatures and store
                for i in range(0, 4):
                    diodeT = interpRaw(diodeVolts[i],calibrationFile[opts.nMux + 4*diodeMod + i])
                    temperatureData = np.append(temperatureData, diodeT)
            # Print Mux temperatures
            for i in range(0, opts.nMux):
                print str(sensors[i]) + ": " +  \
                    str(temperatureData[i + 1])
            # Print diode temperatures if desired
            if opts.PRINT_DIODES == True:
                for i in range(0, 4*opts.nDiodeMod):
                    print str(sensors[opts.nMux + i] + ": " +  \
                        str(temperatureData[opts.nMux + i + 1])).format()
            print ''
            # Save temperature data to file
            temperatureDataStr = formatDataStr(temperatureData)
            writeToFile(dataFile, temperatureDataStr, 'a')

            if (streamer.proc_fast_dev):
                writeToFile(dataFile, "{:+.6E}".format(streamer.latest_fast_data.value), 'a')
            else:
                writeToFile(dataFile, "FAST_DEV_OFF", 'a')

            # Save raw data to file if desired
            if opts.SAVE_RAW == True:
                rawDataStr = formatDataStr(rawData)
                writeToFile(dataFileRaw, rawDataStr, 'a')
                if (streamer.proc_fast_dev):
                    writeToFile(dataFile, "{:+.6E}".format(streamer.latest_fast_data_raw.value), 'a')
                else:
                    writeToFile(dataFile, "FAST_DEV_OFF", 'a')
            FIRST_ITERATION = False
    except KeyboardInterrupt:
        print '\nReceived interrupt - exiting.'
        SIM.escape()
        SIM.closeSerial()
        sys.exit()
    finally:
        SIM.closeSerial()
        streamer.stop()
        streamer.stop_kb_listener()

#-----------------------------------------------------------------------------#
#-----------------------------------------------------------------------------#
#-----------------------------------------------------------------------------#
#-----------------------------------------------------------------------------#


###############################################################################
###############################################################################
#                                  FUNCTIONS                                  #
###############################################################################
###############################################################################


###############################################################################
###############################################################################
# FUNCTION: Add and parse command line options

def parseOptions(basePath):
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option('--path',
        help = 'Root path. Default = %default',
        dest = 'path',
        action = 'store',
        default = basePath)

    parser.add_option('--newFile',
        help = 'Create a new data file. 1 = True, 0 = False (default = %default).' \
        ' If newFile = 0 the script appends to the most recent file in /Data/',
        dest = 'NEWFILE',
        action = 'store',
        default = 0)

    parser.add_option('--USBport',
        help = 'SIM900 mainframe USB device port string. Default = %default ' \
        'for a linux computer. Windows computers want something like ' \
        '\'\\\\.\\COM5\'.',
        dest = 'USBport',
        action = 'store',
        default = '/dev/ttyUSB0')

    parser.add_option('--fastUSBport',
        help = 'SIM921 fast streaming device device port string. Default = %default ' \
        'for a linux computer. Windows computers want something like ' \
        '\'\\\\.\\COM5\'.',
        dest = 'fastUSBport',
        action = 'store',
        default = '/dev/ttyUSB1')

    parser.add_option('--dataFileName',
        help = 'Data file name (do not specify extension, appends \'.txt\' ' \
       'automatically). Default is a date and timestamp, i.e. %default but ' \
       'an argument here will add the string to the filename',
        dest = 'dataFileName',
        action = 'store',
        default = str(time.strftime("%Y%m%d-%H%M%S")))

    parser.add_option('--sensorAndCalNamesFile',
        help = 'File for sensor names and corresponding calibration files. ' \
        'Default = %default, located in the \'Sensors\' folder. If there are ' \
        'empty diode channels enter \'empty\' as the sensor name',
        dest = 'sensorAndCalNamesFile',
        action = 'store',
        default = 'sensor_and_cal_file_names.txt')

    parser.add_option('--nMux',
        help = 'Number of Mux channels to read. Default = %default',
        dest = 'nMux',
        action = 'store',
        type = int,
        default = 8)

    parser.add_option('--nDiodeMod',
        help = 'Number of diode modules. Default = %default',
        dest = 'nDiodeMod',
        action = 'store',
        type = int,
        default = 5)

    parser.add_option('--diodeModStart',
        help = 'First SIM922 diode module mainframe port. Default = %default',
        dest = 'diodeModStart',
        action = 'store',
        type = int,
        default = 4)

    parser.add_option('--queryPeriod',
        help = 'Query period [s] (time between data points). Default = ' \
        '%default',
        dest = 'queryPeriod',
        action = 'store',
        default = 0,
        type = float)

    parser.add_option('--Settle',
        help = 'SIM921 settle time [s]. Default = %default',
        dest = 'resistanceBridgeSettle',
        action = 'store',
        default = 5,
        type = float)

    parser.add_option('--resistanceRange921',
        help = 'SIM921 initial resistance range (8 args, default = %default)',
        dest = 'resistanceRange921',
        action = 'store',
        nargs = 8,
        default = (6, 6, 6, 6, 6, 6, 6, 6, 6),
        type = int)

    parser.add_option('--resistanceRangeFast',
          help='fast data resistance range (default = %default)',
          dest='resistanceRangeFast',
          action='store',
          default=6,
          type=int)

    parser.add_option('--921excitationFrequency',
        help = 'SIM921 excitation frequency (1.95-61.1 Hz). Defualt = %defualt Hz',
        dest = 'freq921',
        action = 'store',
        default = 18.27,
        type = float)

    parser.add_option('--921filterTimeConstant',
        help = 'SIM921 filter time constant (integers -1-6, -1 = no filter). Defualt = 1 ()',
        dest = 'tau921',
        action = 'store',
        default = 1,
        type = int)

    parser.add_option('--fixedExcitation',
        help = 'Specify fixed SIM921 excitation range. Default = %default,' \
        '-1 = automatic excitation. Valid values = 0-7 (0 is highest excitation)',
        dest = 'exciteRange921',
        action = 'store',
        default = -1,
        type = int)

    parser.add_option('--SIM921port',
        help = 'SIM921 AC resistance bridge mainframe port. Default = %default',
        dest = 'SIM921port',
        action = 'store',
        default = 1,
        type = int)

    parser.add_option('--SIM925port',
        help = 'SIM925 multiplexer mainframe port. Default = %default',
        dest = 'SIM925port',
        action = 'store',
        default = 3,
        type = int)

    parser.add_option('--saveRaw',
        help = 'Save raw sensor units (1 = True, 2 = False). Default = ' \
        '%default',
        dest = 'SAVE_RAW',
        action = 'store',
        default = 1,
        type = int)

    parser.add_option('--printMux',
        help = 'Print Mux resistances (1 = True, 0 = False). Default = ' \
        '%default',
        dest = 'PRINT_MUX_RES',
        action = 'store',
        default = 1)

    parser.add_option('--printDiodes',
        help = 'Print diode temperatures (1 = True, 0 = False). Default = ' \
        '%default',
        dest = 'PRINT_DIODES',
        action = 'store',
        default = 1,
        type = int)

    parser.add_option('--printDiodeVolts',
        help = 'Print diode Voltages (1 = True, 0 = False). Default = ' \
        '%default',
        dest = 'PRINT_DIODE_VOLTS',
        action = 'store',
        default = 0,
        type = int)

    parser.set_defaults(verbose = True)
    (opts, args) = parser.parse_args()
    return (opts, args)

###############################################################################
###############################################################################
# FUNCTION: Make sure the /Sensors and /Data folders exist under ths base path

def checkFolders(basePath):
    if not os.path.isdir('Sensors'):
        print '\'/Sensors\' folder does not exist in base path. See README ' \
        'or wiki for instructions on setting up the sensor folder.'
        sys.exit()
    if not os.path.isdir('Data'):
        print '\'/Data\' folder does not exist in base path, creating folder.'
        sp.Popen('mkdir Data', shell = True)

###############################################################################
###############################################################################
# FUNCTION: Check SIM900 USB port

def checkUSBportConfig(fileName, devPort):
    devList = sp.check_output('ls /dev', shell = True).split('\n')
    device = []
    # Show what devices are connected on ttyUSB ports
    print 'Devices connected on ports:'
    for dev in devList:
        if dev[0:6] == 'ttyUSB':
            device.append(dev)
            print dev
    # Look for the 'port_config.txt' file and load the USB address from it
    if os.path.isfile(fileName):
        with open(fileName, 'r') as f:
            text = f.readlines()
            configFileDev = text[0].split('\n')[0]
        for dev in device:
            # See if the port address in 'port_config.txt' matches
            if '/dev/' + dev == '/dev/' + configFileDev or '/dev/' + dev == devPort:
                DEVICE_PORT_MATCH = True
                devFound = dev
            else:
                DEVICE_PORT_MATCH = False
        # If the port address in 'port_config.txt' matches an active port move
        # on, if not print the config file device port and quit.
        if DEVICE_PORT_MATCH == False:
            print 'ERROR: Supplied device port or config file device port ' \
                'do not match connected devices.'
            print 'Config file device port =', configFileDev
            print 'Suitable device ports:', device
            sys.exit()
        else:
            print 'Using device on', devFound
    # If 'port_config.txt' does not exist create it and save the address to it.
    # This will either be the default ('/dev/ttyUSB0') or whatever is speciefied
    # in the command line.
    else:
        with open(fileName, 'w') as f:
            f.write(devPort)
        print 'Config file not found, created config file.'
        print 'Device port created =', devPort

###############################################################################
###############################################################################
# FUNCTION: Load sensor name and calibration curves

def loadSensorNamesAndCalFiles(fileName, sensorPath, nSensors):
    if os.path.isfile(fileName):
        with open(fileName, 'r') as f:
            text = f.read().splitlines()
            sensorNames = text[0].split(',')
            calFileNames = text[1].split(',')
        for i in range(0, len(calFileNames)):
            calFileNames[i] = sensorPath + calFileNames[i]
        print 'len(sensorNames): ', len(sensorNames)
        print 'len(calfileNames): ', len(calFileNames)
        print 'nSensors: ', nSensors
        # Check for errors in the number of expected calibration files and/or
        # sensors
        if len(sensorNames) != nSensors:
            print 'ERROR: Number of sensors in name file does not match ' \
                'expected number of sensors.'
            sys.exit()
        elif len(calFileNames) != nSensors:
            print 'ERROR: Number of calibration files does not match ' \
                'expected number of files.'
            sys.exit()
        elif len(sensorNames) != len(calFileNames):
            print 'ERROR: Number of sensor names does not match number of ' \
                'cailbration files.'
            sys.exit()
    # Catch the error where there is no 'sensor_and_cal_
    else:
        print 'ERROR: Sensor name and calibration file list not found. ' \
        'Create a comma-separated text file (.txt) with sensor names in the ' \
        'first line and corresponding calibration curve file names in the ' \
        'second line in the \'/Sensors\' folder.'
        sys.exit()
    return (sensorNames, calFileNames)

###############################################################################
###############################################################################
# FUNCTION: Initialize data file and write file header

def init_data_file(opts, basePath, sensors):
    fileNames = os.listdir(basePath + '/Data/')
    files = [basePath + '/Data/' + s for s in fileNames]
    files = sorted(files, key = os.path.getctime)
    # If we want a new data file, create it and write the headers.
    if opts.NEWFILE == True or (len(files) == 0 and opts.NEWFILE == False):
        dataFile = basePath + '/Data/' + opts.dataFileName + '.txt'
        headerStr = 'Date: ' + time.strftime("%Y/%m/%d") + ', Time: ' + \
            time.strftime("%H:%M:%S") + '\n________________________________\n'
        headerStr = headerStr + 'Time,' + ','.join(sensors) + '\n'
        dataFileRaw = basePath + '/Data/' + opts.dataFileName + 'RAW.txt'
        headerStrRaw = 'Date: ' + time.strftime("%Y/%m/%d") + ', Time: ' + \
            time.strftime("%H:%M:%S") + '\nRAW SENSOR UNITS FILE' \
            '\n________________________________\n'
        headerStrRaw = headerStrRaw + 'Time,' + ','.join(sensors) + '\n'

        dataFileFast = basePath + '/Data/' + opts.dataFileName + 'FAST.txt'
        headerStrFast = 'Date: ' + time.strftime("%Y/%m/%d") + ', Time: ' + \
            time.strftime("%H:%M:%S") + '\n________________________________\n'
        headerStrFast = headerStrFast + 'Time,' + sensors[-1] + '\n'
        dataFileRawFast = basePath + '/Data/' + opts.dataFileName + 'RAWFAST.txt'
        headerStrRawFast = 'Date: ' + time.strftime("%Y/%m/%d") + ', Time: ' + \
            time.strftime("%H:%M:%S") + '\nRAW SENSOR UNITS FILE' \
            '\n________________________________\n'
        headerStrRawFast = headerStrRawFast + 'Time,' + sensors[-1] + '\n'

        if opts.SAVE_RAW == True:
            writeToFile(dataFileFast, headerStrFast, 'w')
            writeToFile(dataFileRawFast, headerStrRawFast, 'w')
            writeToFile(dataFile, headerStr, 'w')
            writeToFile(dataFileRaw, headerStrRaw, 'w')
        else:
            writeToFile(dataFileFast, headerStrFast, 'w')
            writeToFile(dataFile, headerStr, 'w')
        if len(files) == 0 and opts.NEWFILE == False:
            print 'No existing data file to append to and newFile = 0. ' \
                'Created data file: ' + dataFile

    elif len(files) != 0 and opts.NEWFILE == False:
        lastFile = files[-1]
    
        dataFile = lastFile.rstrip('.txt').rstrip('FAST').rstrip('RAW') + '.txt'
        dataFileRaw = dataFile.strip('.txt') + 'RAW.txt'
        dataFileFast = dataFile.strip('.txt') + 'FAST.txt'
        dataFileRawFast = dataFile.strip('.txt') + 'RAWFAST.txt'
        
        print 'Appending data to: ' + dataFile
    return (dataFile, dataFileRaw, dataFileFast, dataFileRawFast)

###############################################################################
###############################################################################
# FUNCTION: SIM921 measure resistance

def SIM921measureResistance(opts, SIM, channel):
# Check we are on the right SIM900 port, turn on excitation, wait for settle,
# turn off excitation
    if SIM.getDeviceID() == 'SIM921':
        SIM.SIM921setExcitationOnOff(1)
        time.sleep(opts.resistanceBridgeSettle)
        resistance = SIM.getResistanceAC()
        SIM.SIM921setExcitationOnOff(0)
        SIM.escape()
        return resistance
    else:
        print 'Failed to connect to SIM921 Resistance Bridge. Try power-' \
            'cycling.'

###############################################################################
###############################################################################
# FUNCTION: Interpolate raw units to temperature

def interpRaw(measuredValue, calibrationFile):
    calData = np.loadtxt(calibrationFile, skiprows = 4)
    calData = np.flipud(calData)
    calTemp = calData[:, 0]
    calMeasured = calData[:, 1]
    Temperature = np.interp(measuredValue,calMeasured,calTemp)
    return Temperature

###############################################################################
###############################################################################
# FUNCTION: Autoselect SIM921 resistance range

def autoSelSIM921Resistance(opts, resistance, ch):
    if resistance < 1e-2:
        return 0
    elif resistance >= 1e-2 and resistance < 1e-1:
        return 1
    elif resistance >= 1e-1 and resistance < 1e0:
        return 2
    elif resistance >= 1e0 and resistance < 1e1:
        return 3
    elif resistance >= 1e1 and resistance < 1e2:
        return 4
    elif resistance >= 1e2 and resistance < 1e3:
        return 5
    elif resistance >= 1e3 and resistance < 1e4:
        return 6
    elif resistance >= 1e4 and resistance < 1e5:
        return 7
    elif resistance >= 1e5 and resistance < 1e6:
        return 8
    elif resistance >= 1e6 and resistance < 1e7:
        return 9
    else:
        return opts.range921[ch]

###############################################################################
###############################################################################
# FUNCTION: Autoselect SIM921 excitataion voltage

def autoSelSIM921Excitation(temp):
    if temp <= 0.5:
        return 1
    elif temp > 0.7 and temp <= 1:
        return 2
    elif temp > 1 and temp <= 2:
        return 3
    elif temp > 2 and temp <= 4:
        return 5
    else:
        return 7

###############################################################################
###############################################################################
# FUNCTION: Write to file

def writeToFile(fileName, writeStr, writeMethod):
    with open(fileName, writeMethod) as f:
        f.write(writeStr)

###############################################################################
###############################################################################
# FUNCTION: Format data into usable string

def formatDataStr(data):
    dataStr = []
    for i in range(len(data)):
        if i == 0:
            dataStr.append('{0:.16e}'.format(data[i]))
        else:
            dataStr.append('{0:.8e}'.format(data[i]))
    dataStr = ','.join(dataStr) + '\n'
    return dataStr

###############################################################################
###############################################################################

# Execution of main loop
import sys, os, time
import numpy as np
import subprocess as sp
import time
print '\n---------------------------'
print 'Starting Temperature Logger'
print '---------------------------\n'
main()
