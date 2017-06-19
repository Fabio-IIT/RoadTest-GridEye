__author__ = 'fabio'
import json
import multiprocessing
import datetime
from device import RoadTestDevice,NON_LATCHING_RELAY,LATCHING_RELAY,GE,STATUS_TAG,STATUS_ON

TIMESTAMP_TAG="TIME" #mandatory
SOURCE_TAG="SRC"

DEVICE="DEVICE"
WEB="WEB"
ALARM="ALARM"
BACKGROUND="BACKGROUND"
RESET="RESET"
SET="SET"

class Node(multiprocessing.Process):
    def __init__(self, web_to_node_queue, processor_to_node_queue, node_to_processor_queue, configFile, debug_queue=None):
        multiprocessing.Process.__init__(self)
        self.web_to_node_queue = web_to_node_queue
        self.processor_to_node_queue = processor_to_node_queue
        self.node_to_processor_queue = node_to_processor_queue
        self.debug_queue=debug_queue
        self.configFile=configFile

    def run(self):
        self.device = RoadTestDevice(self.configFile, self.debug_queue)
        while True:
            # look for incoming processor request (alarm trigger)
            while not self.processor_to_node_queue.empty():
                data = json.loads(self.processor_to_node_queue.get())
                alarmData={}
                if NON_LATCHING_RELAY in data:
                    alarmData[NON_LATCHING_RELAY]=data[NON_LATCHING_RELAY]
                if LATCHING_RELAY in data:
                    alarmData[LATCHING_RELAY] = data[LATCHING_RELAY]
                # send it to the serial device
                self.device.writeData(alarmData)

            # look for incoming tornado request
            if not self.web_to_node_queue.empty():
                data = self.web_to_node_queue.get()
                if self.debug_queue:
                    self.debug_queue.put(str("NODE: recv web msg - "+data))
                data = json.loads(data)
                # write data to the device
                if ALARM in data:
                    if data[ALARM]==RESET:
                        data[SOURCE_TAG]=ALARM
                        self.node_to_processor_queue.put(json.dumps(data))
                        self.device.writeData()
                if BACKGROUND in data:
                    data[SOURCE_TAG]=BACKGROUND
                    self.node_to_processor_queue.put(json.dumps(data))
                if NON_LATCHING_RELAY in data:
                    status = 1 if data[STATUS_TAG] == STATUS_ON else 0
                    self.device.setNonLatchingRelayStatus(int(data[NON_LATCHING_RELAY]), status)
                    del data[NON_LATCHING_RELAY]
                if LATCHING_RELAY in data:
                    status = 1 if data[STATUS_TAG] == STATUS_ON else 0
                    self.device.setLatchingRelayStatus(int(data[LATCHING_RELAY]),status)  # send it to the serial device
                    del data[LATCHING_RELAY]
                if GE in data:
                    status = 1 if data[STATUS_TAG] == STATUS_ON else 0
                    self.device.setSensorStatus(status)
                    del data[GE]
                self.device.writeData()

                if bool(data):
                    # send data for processing (alarm mask)
                    data[SOURCE_TAG]=WEB
                    self.node_to_processor_queue.put(json.dumps(data))

            # look for incoming serial data
            data = self.device.readData()
            # send data to processor
            if (data != None):
                data = json.loads(data)
                data[TIMESTAMP_TAG]=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data[NON_LATCHING_RELAY]=self.device.getNonLatchingRelays()
                data[LATCHING_RELAY]=self.device.getLatchingRelays()
                data[SOURCE_TAG]=DEVICE
                message = json.dumps(data)
                self.node_to_processor_queue.put(message)
                if self.debug_queue:
                    self.debug_queue.put("NODE: send msg to processor - %s" % message)
