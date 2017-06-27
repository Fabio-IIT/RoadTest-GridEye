import multiprocessing
import json
from node import SOURCE_TAG, WEB, DEVICE, ALARM, BACKGROUND, RESET, SET
from device import GRID_SIZE_X,GRID_SIZE_Y,GE,NON_LATCHING_RELAY,LATCHING_RELAY
import analyser
from analyser import *

IMAGE_SIZE_X = 64
IMAGE_SIZE_Y = 64

GE_MIN = "GE_MIN"
GE_MAX = "GE_MAX"
GE_AVG = "GE_AVG"
GE_MDN = "GE_MDN"
GE_STD = "GE_STD"
GE_BINARY = "GE_BINARY"
GE_TEMP = "GE_TEMP"
GE_CORR_COEFF = "GE_CORR_COEFF"
X_TAG = "X"
Y_TAG = "Y"
CELL="CELL"

class Processor(multiprocessing.Process,analyser.ImageProcessor):

    def __init__(self, node_to_processor_queue, processor_to_node_queue, processor_to_web_queue, debug_queue=None,
                 detection_mode=MODE_ANY,  differential_temperature_threshold=DEFAULT_DIFFERENTIAL_THRESHOLD,
                 absolute_temperature_threshold=DEFAULT_ABSOLUTE_THRESHOLD,
                 frame_size_X=GRID_SIZE_X, frame_size_Y=GRID_SIZE_Y, window_size=DEFAULT_WINDOW_SIZE):
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
        analyser.ImageProcessor.__init__(self,detection_mode=detection_mode, threshold_abs=absolute_temperature_threshold,
        threshold_diff=differential_temperature_threshold, window_size=window_size)
        self.size_X=frame_size_X
        self.size_Y=frame_size_Y
        self.node_to_processor_queue = node_to_processor_queue
        self.processor_to_node_queue = processor_to_node_queue
        self.processor_to_web_queue = processor_to_web_queue
        self.debug_queue = debug_queue
        self.alarm_mask = Frame(frame_size_X, frame_size_Y, [0] * frame_size_X * frame_size_Y)
        self.alarm_triggered = False

    def process(self, message):
        from copy import deepcopy
        processedMessage = deepcopy(message)
        if GE in processedMessage and len(processedMessage[GE]) > 0:
            imgFrame = Frame(self.size_X,self.size_Y,processedMessage[GE])
            imgFrame.flipH()
            imgFrame.flipV()
            status = self.processFrame(imgFrame)
            if status == ImageProcessor.S_PROCESS_IMAGE:
                processedMessage[GE_TEMP] = list(imgFrame.rawData)
                processedMessage[GE_BINARY] = list(imgFrame.binary(self.getDetectedObjects()).rawData)
            processedMessage[GE_MIN] = imgFrame.min()
            processedMessage[GE_MAX] = imgFrame.max()
            processedMessage[GE_AVG] = imgFrame.mean()
            processedMessage[GE_MDN] = imgFrame.median()
            processedMessage[GE_STD] = imgFrame.stdDev()
            imgFrame.expand(IMAGE_SIZE_X,IMAGE_SIZE_Y)
            imgFrame.filterNoise()
            processedMessage[GE] = list(imgFrame.rawData)
        return processedMessage

    def detect_cb(self,detected_object,event,frame):
        '''
        callback invoked upon detection.
        :param detected_object:
        :param event:
        :param frame:
        :return:
        '''
        if event==OBJECT_IN:
            alarm = False
            for point in detected_object.getPoints():
                if self.alarm_mask.getValue(point.x, point.y) != 0 and not self.alarm_triggered:
                    alarm = True
                    break
            # update device if alarm has been triggered
            if alarm and not self.alarm_triggered:
                # send only the relay setting to the device
                alarmMessage = {}
                alarmMessage[LATCHING_RELAY] = 7
                self.processor_to_node_queue.put(json.dumps(alarmMessage))
                del alarmMessage[LATCHING_RELAY]
                alarmMessage[ALARM] = SET
                self.processor_to_web_queue.put(json.dumps(alarmMessage))
                self.alarm_triggered = True
                if self.debug_queue:
                    self.debug_queue.put("PROCESSOR: send msg to node - %s" % alarmMessage)

    def run(self):
        '''
        This is the loop for the process.
        Basically the loop will check for incoming messages,
        process and route them to their next destination.
        :return:
        '''
        self.addDetectionCallback(self.detect_cb,OBJECT_IN)
        while True:
            while not self.node_to_processor_queue.empty():
                # process data from the device
                message = self.node_to_processor_queue.get()
                if self.debug_queue:
                    self.debug_queue.put("PROCESSOR: recv msg from node - %s" % message)
                message = json.loads(message)
                if message[SOURCE_TAG] == ALARM:
                    if message[ALARM] == RESET:
                        # reset the alarm status and
                        # broadcast the reset command to all the
                        # web clients, to update their UI control
                        alarmMessage = {}
                        alarmMessage[ALARM] = RESET
                        self.alarm_triggered = False
                        self.processor_to_web_queue.put(json.dumps(alarmMessage))
                elif message[SOURCE_TAG] == BACKGROUND:
                    # upgrade the background image
                    self.updateBackground()
                elif message[SOURCE_TAG] == DEVICE:
                    message = self.process(message)
                    # update UI
                    self.processor_to_web_queue.put(json.dumps(message))
                    if self.debug_queue and False:
                        self.debug_queue.put("PROCESSOR: send msg to web - %s" % message)
                elif message[SOURCE_TAG] == WEB:
                    # process data coming from the web (alarm mask settings)
                    if all(key in message for key in (X_TAG, Y_TAG)):
                        maskMessage = {}
                        maskMessage[X_TAG]=message[X_TAG]
                        maskMessage[Y_TAG]=message[Y_TAG]
                        if self.alarm_mask.getValue(message[X_TAG]-1,message[Y_TAG]-1) == 1:
                            self.alarm_mask.setValue(message[X_TAG] - 1, message[Y_TAG] - 1,0)
                            maskMessage[CELL]=RESET
                        else:
                            self.alarm_mask.setValue(message[X_TAG] - 1, message[Y_TAG] - 1,1)
                            maskMessage[CELL]=SET
                        self.processor_to_web_queue.put(maskMessage)
                        if self.debug_queue:
                            self.debug_queue.put("PROCESSOR: alarm grid %s" % self.alarm_mask)
