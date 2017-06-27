import ConfigParser
import serial
import time
import sys

DEVICE_ID=1 # matches the device ID stored in the firmware
DEVICE_TYPE=2 # DEVICE_TYPE_MRD130_MRD131
CONFIG_FILE_DEFAULT='./config/grideye.cfg'

GRID_SIZE_X = 8
GRID_SIZE_Y = 8

PORT_TAG = 'port'
SPEED_TAG = 'speed'
RANGE_TAG = 'range'
PORT_DEFAULT = '/dev/ttyACM0'
SPEED_DEFAULT = 115200
RANGE_DEFAULT = '5m'

ID_TAG = 'id'
TYPE_TAG = 'type'
DEVICE_SECTION = 'Device'
NLR_SECTION= 'Non_Latching_Relays'
LR_SECTION= 'Latching_Relays'
RELAY='Relay'
SEP_TAG='_'
STATUS_TAG='STATUS'
STATUS_ON='ON'
STATUS_OFF='OFF'
GE = "GE"
START_MARKER = '{'
END_MARKER = '}'
NON_LATCHING_RELAY = "NLR"
LATCHING_RELAY = "LR"

startFound = False
endFound = False
buffer = ''

class RoadTestDevice(object):
    def __init__(self,cfgFile=None, debug_queue=None):
        self.debug_queue=debug_queue
        self.config = ConfigParser.ConfigParser()
        self.config.optionxform = str
        self.cfgFile = CONFIG_FILE_DEFAULT if cfgFile==None else cfgFile
        self.config.read(self.cfgFile)
        if not self.config.has_section(DEVICE_SECTION):
            self.config.add_section(DEVICE_SECTION)
            self.config.set(DEVICE_SECTION,ID_TAG,str(DEVICE_ID)) # set in the firmware code
            self.config.set(DEVICE_SECTION,TYPE_TAG,str(DEVICE_TYPE))
            self.config.set(DEVICE_SECTION,GE,STATUS_ON)
            self.config.set(DEVICE_SECTION, RANGE_TAG, RANGE_DEFAULT)
            self.config.set(DEVICE_SECTION, PORT_TAG, PORT_DEFAULT)
            self.config.set(DEVICE_SECTION, SPEED_TAG, SPEED_DEFAULT)
        if not self.config.has_section(NLR_SECTION):
            self.config.add_section(NLR_SECTION)
        self.nlr=0
        for i in range(1, 9):
            if not self.config.has_option(NLR_SECTION,RELAY + SEP_TAG + str(i)):
                self.config.set(NLR_SECTION, RELAY + SEP_TAG +str(i), STATUS_OFF)
            else:
                if self.config.get(NLR_SECTION, RELAY + SEP_TAG + str(i)) == STATUS_ON:
                    self.nlr += pow(2,i-1)
        if not self.config.has_section(LR_SECTION):
            self.config.add_section(LR_SECTION)
        self.lr=0
        for i in range(1, 4):
            if not self.config.has_option(LR_SECTION, RELAY + SEP_TAG + str(i)):
                self.config.set(LR_SECTION, RELAY + SEP_TAG + str(i), STATUS_OFF)
            else:
                if self.config.get(LR_SECTION, RELAY + SEP_TAG + str(i)) == STATUS_ON:
                    self.lr += pow(2, i-1)
        with open(self.cfgFile, 'wb') as configfile:
            self.config.write(configfile)
        self.sp = serial.Serial(self.config.get(DEVICE_SECTION,PORT_TAG), self.config.get(DEVICE_SECTION,SPEED_TAG), timeout=1)
        time.sleep(2)  # give time to the serial interface to settle
        self.sp.flushInput()
        self.writeData()

    def getNonLatchingRelayStatus(self,relay):
        ''' returns 1 if set, 0 if reset'''
        status = 0
        #relay_str = str((relay-1)%8 if relay > 0 else 0)
        if self.config.has_option(NLR_SECTION,RELAY+SEP_TAG+str(relay)):
            status = 1 if self.config.get(NLR_SECTION,RELAY+SEP_TAG+str(relay))==STATUS_ON else 0
        return status

    def getLatchingRelayStatus(self,relay):
        ''' returns 1 if set, 0 if reset'''
        status = 0
        if self.config.has_option(LR_SECTION,RELAY+SEP_TAG+str(relay)):
            status = 1 if self.config.get(LR_SECTION,RELAY+SEP_TAG+str(relay))==STATUS_ON else 0
        return status

    def setNonLatchingRelayStatus(self,relay,value):
        if relay > 0 and relay < 9:
            if value == 1:
                self.nlr = self.nlr | pow(2, relay - 1)
                status = STATUS_ON
            else:
                self.nlr = self.nlr ^ pow(2, relay - 1)
                status = STATUS_OFF
            self.config.set(NLR_SECTION,RELAY+SEP_TAG+str(relay),status)

            with open(self.cfgFile, 'wb') as configfile:
                self.config.write(configfile)

    def setLatchingRelayStatus(self,relay,value):
        if relay > 0 and relay < 4:
            if value == 1:
                self.lr = self.lr | pow(2, relay - 1)
                status = STATUS_ON
            else:
                self.lr = self.lr ^ pow(2, relay - 1)
                status = STATUS_OFF
            self.config.set(LR_SECTION,RELAY+SEP_TAG+str(relay),status)
            with open(self.cfgFile, 'wb') as configfile:
                self.config.write(configfile)

    def setNonLatchingRelays(self,status):
        '''
        Set the non-latching relays status
        :param status: 0-255 It is the bit-wise OR of
                       the 8 relays' status. Each bit
                       represents a relay, and its status is
                       ON if the bit=1, OFF otherwise,
                       where bit0=Relay1 ... bit7=Relay8.
        :return:
        '''
        if status>=0 and status<=255:
            self.nlr=status

    def setLatchingRelays(self,status):
        '''
        Set the latching relays status
        :param status: 0-7 It is the bit-wise OR of
                       the 3 relays' status. Each bit
                       represents a relay, and its status is
                       ON if the bit=1, OFF otherwise,
                       where bit0=Relay1 ... bit2=Relay3.
        :return:
        '''
        if status>=0 and status<=7:
            self.lr=status

    def getSensorStatus(self):
        status = 0
        if self.config.has_option(DEVICE_SECTION,GE):
            status = 1 if self.config.get(DEVICE_SECTION,GE) == STATUS_ON else 0
        return status

    def setSensorStatus(self,enabled):
        '''
        :param enabled: 0 to disable, 1 to enable
        :return: None
        '''
        self.config.set(DEVICE_SECTION,GE,STATUS_ON if enabled==1 else STATUS_OFF)
        with open(self.cfgFile, 'wb') as configfile:
            self.config.write(configfile)

    def getNonLatchingRelays(self):
        return self.nlr

    def getLatchingRelays(self):
        return self.lr

    def __str__(self):
        return (u"{'NLR':%d,'LR':%d,'GE':%r}" % (self.nlr,self.lr,self.getSensorStatus()))

    def encode(self):
        return (u"{'NLR':%d,'LR':%d,'GE':%r}" % (self.nlr,self.lr,self.getSensorStatus())).encode()

    def writeData(self,data=None):
        if data == None:
            dataStr = self.encode()
        elif all(x in data for x in (NON_LATCHING_RELAY,LATCHING_RELAY)):
            dataStr = (u"{'NLR':%d,'LR':%d}" % data[NON_LATCHING_RELAY],data[LATCHING_RELAY]).encode()
        elif NON_LATCHING_RELAY in data:
            dataStr = (u"{'NLR':%d}" % data[NON_LATCHING_RELAY]).encode()
        elif LATCHING_RELAY in data:
            dataStr = (u"{'LR':%d}" % data[LATCHING_RELAY]).encode()
        else:
            dataStr = self.encode()

        self.sp.write(dataStr)
        time.sleep(0.1)

        if self.debug_queue:
            self.debug_queue.put("DEVICE: Sent to Serial Port: %s" % (self.encode()))

    def convertToTemperature(self, width, height, dataIn):
        dataOut = [None] * width * height
        for idx1 in range(0, width * height):
            dataOut[idx1] = float(dataIn[idx1]) / 256
        return dataOut

    def readData(self):
        global endFound, startFound, buffer, write, writeFinal

        while self.sp.inWaiting() > 0 and not endFound:
            ch = self.sp.read()
            if (ch == START_MARKER):
                startFound = True
                buffer = ''

            if ((startFound) and (not endFound)):
                buffer += ch

            if (ch == END_MARKER):
                if (startFound):
                    endFound = True
                    startFound = False
                    try:
                        import json
                        reading = json.loads(buffer)
                        if GE in reading:
                            reading[GE] = self.convertToTemperature(GRID_SIZE_X,GRID_SIZE_Y,reading[GE])
                        data = json.dumps(reading)
                        return data
                    except ValueError as e:
                        print "Unexpected error:", sys.exc_info()[0]
                        print e
        if (endFound):
            endFound = False
        return None

if __name__ == '__main__':
    # import datetime
    # print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # exit(0)
    # import json
    # data=json.loads('{"NLR":100,"LR":2,"GE":0}')
    # for k, v in data.items():
    #     print k,v
    # if "GE" in data:
    #     print "GE is %s" % data["GE"]
    # del data["GE"]
    # print data
    device=RoadTestDevice()
    print device
    #device.setNonLatchingRelayStatus(8,1)
    print device
    device.setLatchingRelayStatus(2,1)
    print device
    device.writeData()