__author__ = 'fabio'
import ConfigParser
import multiprocessing
import json
from node import SOURCE_TAG, WEB, DEVICE, ALARM, BACKGROUND, RESET, SET, UPDATE_UI, COMMAND_TAG
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
MODE="MODE"

DEFAULT_ALARM_TRIGGER_THRESHOLD=1

GRID_SIZE_X_OPT="temperature_grid_rows"
GRID_SIZE_Y_OPT="temperature_grid_columns"
IMAGE_SIZE_X_OPT="image_grid_rows"
IMAGE_SIZE_Y_OPT="image_grid_columns"
ALARM_TRIGGER_THRESHOLD_OPT="alarm_trigger_threshold"
ALARM_COMMAND_OPT="alarm_command"
ALARM_MASK_OPT="alarm_mask"

DEFAULT_ALARM_COMMAND='{"LR":7}'

class Processor(multiprocessing.Process,analyser.ImageProcessor):

    def __init__(self, node_to_processor_queue, processor_to_node_queue, processor_to_web_queue,
                 debug_queue=None, config_file=None, detection_mode=MODE_ANY,
                 differential_temperature_threshold=DEFAULT_DIFFERENTIAL_THRESHOLD,
                 absolute_temperature_threshold=DEFAULT_ABSOLUTE_THRESHOLD,
                 frame_size_X=GRID_SIZE_X, frame_size_Y=GRID_SIZE_Y,
                 image_size_X=IMAGE_SIZE_X, image_size_Y=IMAGE_SIZE_Y,
                 window_size=DEFAULT_WINDOW_SIZE,
                 alarm_trigger_threshold=DEFAULT_ALARM_TRIGGER_THRESHOLD,
                 alarm_command=DEFAULT_ALARM_COMMAND):
        '''

        :param node_to_processor_queue:    input queue for data from the device (node)
        :param processor_to_node_queue:    output queue for events,alarms etc to the device (node)
        :param processor_to_web_queue:     output queue for events,alarms etc to the web server (update UI)
        :param debug_queue:                output queue for debugging messages
        :param config_file:                configuration file
        :param detection_mode:             mode of operation for the object detection. Can be:
                                           MODE_ABSOLUTE     - detection based on object's absolute temp.
                                           MODE_DIFFERENTIAL - detection based on object's temperature
                                                               difference with the background
        :param differential_temperature_threshold:   minimum differential temp. for positive detection
        :param absolute_temperature_threshold:       minimum absolute temp.  for positive detection
        :param frame_size_X:               temperature and alarm frame size X axis (number of rows)
        :param frame_size_Y:               temperature and alarm frame size Y axis (number of columns)
        :param image_size_X:               thermal image frame size X axis (number of rows)
        :param image_size_Y:               thermal image frame size Y axis (number of columns)
        :param window_size:                number of frames required to set background temperature
        :param alarm_trigger_threshold:    number of frames necessary for detecting the change
                                           and trigger the event
        :param alarm_command:              the JSON command to trigger the alarm on the device
        '''

        multiprocessing.Process.__init__(self)
        analyser.ImageProcessor.__init__(self, config_file=config_file,
                                         detection_mode=detection_mode,
                                         threshold_abs=absolute_temperature_threshold,
                                         threshold_diff=differential_temperature_threshold,
                                         window_size=window_size,
                                         debug_queue=debug_queue)
        self.size_X=frame_size_X
        self.size_Y=frame_size_Y
        self.image_size_X=image_size_X
        self.image_size_Y=image_size_Y
        self.node_to_processor_queue = node_to_processor_queue
        self.processor_to_node_queue = processor_to_node_queue
        self.processor_to_web_queue = processor_to_web_queue
        self.alarm_mask = Frame(frame_size_X, frame_size_Y, [0] * frame_size_X * frame_size_Y)
        self.alarm_trigger_threshold = alarm_trigger_threshold
        self.alarm_triggered = False
        self.alarm_counter = 0
        self.alarm_command = alarm_command
        if config_file:
            config = ConfigParser.ConfigParser()
            config.optionxform = str
            config.read(config_file)
            #override with configuration based settings
            if config.has_option(PROCESSOR_SECTION,GRID_SIZE_X_OPT):
                self.size_X=config.get(PROCESSOR_SECTION,GRID_SIZE_X_OPT)
            if config.has_option(PROCESSOR_SECTION,GRID_SIZE_Y_OPT):
                self.size_Y=config.getint(PROCESSOR_SECTION, GRID_SIZE_Y_OPT)
            if config.has_option(PROCESSOR_SECTION,IMAGE_SIZE_X_OPT):
                self.image_size_X=config.getint(PROCESSOR_SECTION, IMAGE_SIZE_X_OPT)
            if config.has_option(PROCESSOR_SECTION,IMAGE_SIZE_Y_OPT):
                self.image_size_Y=config.getint(PROCESSOR_SECTION, IMAGE_SIZE_Y_OPT)
            if config.has_option(PROCESSOR_SECTION,ALARM_TRIGGER_THRESHOLD_OPT):
                self.alarm_trigger_threshold=config.getint(PROCESSOR_SECTION, ALARM_TRIGGER_THRESHOLD_OPT)
            if config.has_option(PROCESSOR_SECTION,ALARM_COMMAND_OPT):
                self.alarm_command=config.get(PROCESSOR_SECTION, ALARM_COMMAND_OPT)
            if config.has_option(PROCESSOR_SECTION,ALARM_MASK_OPT):
                from ast import literal_eval
                for x in config.get(PROCESSOR_SECTION, ALARM_MASK_OPT).split(" "):
                    (x, y) = literal_eval(x)
                    self.alarm_mask.setValue(x, y, 1)

    def updateUI(self):
        #update UI
        for x in range (0, self.size_X):
            for y in range (0, self.size_Y):
                if self.alarm_mask.getValue(x,y)==1:
                    maskMessage = {}
                    maskMessage[X_TAG] = x + 1
                    maskMessage[Y_TAG] = y + 1
                    maskMessage[CELL] = SET
                    self.processor_to_web_queue.put(json.dumps(maskMessage))
        message={}
        message[MODE]=self.detection_mode
        self.processor_to_web_queue.put(message)

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
            imgFrame.expand(self.image_size_X,self.image_size_Y)
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
        if event==OBJECT_IN and not self.alarm_triggered:
            alarm = False
            for point in detected_object.getPoints():
                if self.alarm_mask.getValue(point.x, point.y) != 0:
                    if self.alarm_counter == self.alarm_trigger_threshold:
                        alarm = True
                        self.alarm_counter = 0
                    else:
                        self.alarm_counter += 1
                    break
            # update device if alarm has been triggered
            if alarm:
                # send only the relay setting to the device
                alarmMessage = {}
                #alarmMessage[LATCHING_RELAY] = 7
                self.processor_to_node_queue.put(json.dumps(json.loads(self.alarm_command)))
                #del alarmMessage[LATCHING_RELAY]
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
        self.updateUI()
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
                        self.alarm_counter = 0
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
                    # process data coming from the web
                    if COMMAND_TAG in message:
                        if message[COMMAND_TAG] == UPDATE_UI:
                            self.updateUI()
                    # (alarm mask settings)
                    elif all(key in message for key in (X_TAG, Y_TAG)):
                        maskMessage = {}
                        maskMessage[X_TAG]=message[X_TAG]
                        maskMessage[Y_TAG]=message[Y_TAG]
                        if self.alarm_mask.getValue(message[X_TAG]-1,message[Y_TAG]-1) == 1:
                            self.alarm_mask.setValue(message[X_TAG] - 1, message[Y_TAG] - 1,0)
                            maskMessage[CELL]=RESET
                        else:
                            self.alarm_mask.setValue(message[X_TAG] - 1, message[Y_TAG] - 1,1)
                            maskMessage[CELL]=SET
                        self.processor_to_web_queue.put(json.dumps(maskMessage))
                        if self.debug_queue:
                            self.debug_queue.put("PROCESSOR: alarm grid %s" % self.alarm_mask)

