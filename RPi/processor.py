import multiprocessing
import json
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import sobel
from scipy.ndimage.filters import median_filter
from node import SOURCE_TAG,WEB,DEVICE,ALARM,BACKGROUND,RESET,SET

GRID_SIZE_X = 8
GRID_SIZE_Y = 8


START_MARKER = '{'
END_MARKER = '}'
GE = "GE"
GE_MIN="GE_MIN"
GE_MAX="GE_MAX"
GE_AVG="GE_AVG"
GE_MDN="GE_MDN"
GE_STD="GE_STD"
GE_BINARY="GE_BINARY"
GE_CORR_COEFF="GE_CORR_COEFF"
NON_LATCHING_RELAY = "NLR"
LATCHING_RELAY = "LR"
X_TAG="X"
Y_TAG="Y"
HUMAN_TEMPERATURE_THRESHOLD=26.0
STD_THRESHOLD=1

class Processor (multiprocessing.Process):
    S_PROCESS_BACKGROUND = 1 # need to acquire frames to set background
    S_PROCESS_IMAGE = 2      # background is set, can process image for change

    def __init__(self, node_to_processor_queue, processor_to_node_queue, processor_to_web_queue, debug_queue=None, frame_size=8*8, window_size=10,triggering_event_threshold=2):
        '''
        :param node_to_processor_queue:   input queue for data from the device (node)
        :param processor_to_node_queue:  output queue for events,alarms etc to the device (node)
        :param processor_to_web_queue:   output queue for events,alarms etc to the web server (update UI)
        :param frame_size:    image frame size in pixels
        :param window_size:   observation window expressed as number of frames to analyse
        :param triggering_event_threshold: number of frames necessary for detecting the change
                                           and trigger the event
        '''
        multiprocessing.Process.__init__(self)
        self.node_to_processor_queue = node_to_processor_queue
        self.processor_to_node_queue = processor_to_node_queue
        self.processor_to_web_queue = processor_to_web_queue
        self.debug_queue=debug_queue
        self.frame_size=frame_size
        self.window_size=window_size
        self.background_frame=[0]*frame_size
        self.triggering_event_threshold=triggering_event_threshold
        self.alarm_mask=[0]*frame_size
        self.status=Processor.S_PROCESS_BACKGROUND
        self.background_window_idx=0
        self.window_frame_idx=0
        self.alarm_triggered=False

    def processFrame(self,frame):
        binaryFrame = self.getPixelBinary(frame, min(self.background_frame))
        alarm = False
        frameDiff = np.array(frame) - np.array(self.background_frame)
        for idx in range(0,len(frameDiff)):
            #if frameDiff[idx]>=4 or frame[idx] >= HUMAN_TEMPERATURE_THRESHOLD:
            if frameDiff[idx]>=STD_THRESHOLD:
                binaryFrame[idx]=1
            else:
                binaryFrame[idx]=0
        alarmMap = np.array(binaryFrame) * np.array(self.alarm_mask)
        if self.debug_queue and False:
            self.debug_queue.put("PROCESSOR:\n\tmask %s\n\tbinFrame %s\n\talarmMap %s" %(self.alarm_mask,binaryFrame,alarmMap))
        if 1 in alarmMap:
            alarm = True
        return (binaryFrame,alarm)

    def filterNoise(self,width,height,dataIn):
        dataOut = median_filter(np.reshape(dataIn,(-1,width)),3)
        return dataOut.flatten().tolist()

    def expandMatrix(self,dataIn,size):
        values = np.reshape(dataIn, 64)
        reshape=True 
        pts = np.array([[i, j] for i in np.linspace(0, 1, 8) for j in np.linspace(0, 1, 8)])
        if size==64*64:
            grid_x, grid_y = np.mgrid[0:1:64j, 0:1:64j]
        elif size==32*32: 
            grid_x, grid_y = np.mgrid[0:1:32j, 0:1:32j]
        elif size==16*16:
            grid_x, grid_y = np.mgrid[0:1:16j, 0:1:16j]
        else:
            dataOut=dataIn
            reshape=False
        if reshape:
            dataOut = np.reshape(griddata(pts, values, (grid_x, grid_y), method='cubic'),size)
        return dataOut

    def convertToTemperature(self,width, height, dataIn):
        dataOut = [None] * width * height
        for idx1 in range(0, width*height):
            dataOut[idx1] = float(dataIn[idx1]) / 256
        return dataOut

    def getPixelBinary(self,dataIn,threshold):
        dataOut = np.array(dataIn) - threshold > 4
        return dataOut.tolist()

    def process(self,message):
        from copy import deepcopy
        alarm=False
        processedMessage=deepcopy(message)
        if GE in processedMessage and len(processedMessage[GE]) > 0:
            processedMessage[GE] = np.reshape(np.fliplr(np.flipud(np.reshape(processedMessage[GE], (-1, GRID_SIZE_X)))), GRID_SIZE_X * GRID_SIZE_Y)
            temperatureMap = self.convertToTemperature(GRID_SIZE_X,GRID_SIZE_Y,processedMessage[GE])
            processedMessage[GE_MIN] = min(temperatureMap)
            processedMessage[GE_MAX] = max(temperatureMap)
            processedMessage[GE_AVG] = np.mean(temperatureMap)
            processedMessage[GE_MDN] = np.median(temperatureMap)
            processedMessage[GE_STD] = np.std(temperatureMap)
            processedMessage[GE] = self.convertToTemperature(64, 64, self.expandMatrix(processedMessage[GE],64*64))
            processedMessage[GE] = self.filterNoise(64, 64, processedMessage[GE])
            if self.status == Processor.S_PROCESS_BACKGROUND:
                #process background
                if self.background_window_idx < self.window_size:
                    corr_coeff=1.0
                    if self.background_window_idx > 0:
                        corr_coeff = abs(np.corrcoef(np.array((self.background_frame, temperatureMap)))[0, 1])
                    if corr_coeff >= 0.5: #moderate to strong correlation
                        self.background_window_idx = self.background_window_idx + 1
                        self.background_frame = (self.background_frame + np.array(temperatureMap))/2
                    else:
                        self.background_frame = np.array(temperatureMap)
                        self.background_window_idx = 1
                else:
                    self.status = Processor.S_PROCESS_IMAGE
            if self.status == Processor.S_PROCESS_IMAGE:
                #check alarm
                (processedMessage[GE_BINARY],alarm)=self.processFrame(temperatureMap)
        return (processedMessage,alarm)

    def run(self):
        while True:
            while not self.node_to_processor_queue.empty():
                # process data from the device
                message = self.node_to_processor_queue.get()
                if self.debug_queue:
                    self.debug_queue.put("PROCESSOR: recv msg from node - %s" % message)
                message = json.loads(message)
                if message[SOURCE_TAG]==ALARM:
                    if message[ALARM]==RESET:
                        alarmMessage={}
                        alarmMessage[ALARM]=RESET
                        self.alarm_triggered=False
                        self.processor_to_web_queue.put(json.dumps(alarmMessage))
                elif message[SOURCE_TAG]==BACKGROUND:
                   self.status = Processor.S_PROCESS_BACKGROUND 
                   self.background_window_idx = 1
                elif message[SOURCE_TAG]==DEVICE:
                    (message,alarm) = self.process(message)
                    # update UI
                    self.processor_to_web_queue.put(json.dumps(message))
                    if self.debug_queue and False:
                        self.debug_queue.put("PROCESSOR: send msg to web - %s" % message)
                    # update device if alarm has been triggered
                    if alarm and not self.alarm_triggered:
                        # send only the relay setting to the device
                        alarmMessage={}
                        alarmMessage[LATCHING_RELAY]=7
                        self.processor_to_node_queue.put(json.dumps(alarmMessage))
                        del alarmMessage[LATCHING_RELAY]
                        alarmMessage[ALARM]=SET
                        self.processor_to_web_queue.put(json.dumps(alarmMessage))
                        self.alarm_triggered = True
                        if self.debug_queue:
                            self.debug_queue.put("PROCESSOR: send msg to node - %s" % alarmMessage)
                elif message[SOURCE_TAG]==WEB:
                    #process data coming from the web (alarm mask settings)
                    if all(key in message for key in (X_TAG, Y_TAG)):
                        if self.alarm_mask[GRID_SIZE_X*(message[Y_TAG]-1) + message[X_TAG]-1]==1:
                            self.alarm_mask[GRID_SIZE_X*(message[Y_TAG]-1) + message[X_TAG]-1]=0
                        else:
                            self.alarm_mask[GRID_SIZE_X*(message[Y_TAG]-1) + message[X_TAG]-1]=1
                        if self.debug_queue:
                            self.debug_queue.put("PROCESSOR: alarm grid %s" % self.alarm_mask)
