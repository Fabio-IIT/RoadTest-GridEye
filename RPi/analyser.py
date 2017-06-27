__author__ = 'fabio'
from copy import deepcopy
import numpy as np
from scipy.interpolate import griddata
from scipy.signal import medfilt
import math

DEFAULT_WINDOW_SIZE = 10

DEFAULT_ABSOLUTE_THRESHOLD=24
DEFAULT_DIFFERENTIAL_THRESHOLD=2

MODE_ABSOLUTE=1
MODE_DIFFERENTIAL=2
MODE_BOTH=3
MODE_ANY=4

SKIP_TEMPERATURE=-999

OBJECT_IN = 0
OBJECT_OUT = 1

class Point(object):
    def __init__(self,x,y, value=None):
        self.x=x
        self.y=y
        self.value = value

    def __sub__(a,b):
        return a.distance(b)

    def distance(self, other):
        return math.sqrt(math.pow(self.x - other.x,2) + math.pow(self.y - other.y,2))

    def __hash__(self):
        return hash((self.x,self.y))

    def __repr__(self):
        return "(%r,%r):%r" % (self.x,self.y,self.value)

class Frame(object):
    def __init__(self,sizeX,sizeY,data):
        '''
        Frame object constructor.
        :param sizeX: number of rows of the Frame image matrix
        :param sizeY: number of columns of the Frame image matrix
        :param data: can be either sizeX*sizeY 1-D array of values, or
                        a (sizeX,sizeY) 2-D array
        '''
        self.sizeX = sizeX
        self.sizeY = sizeY
        self.size = sizeX * sizeY
        self.shape = np.shape(data)
        if len(self.shape) == 1:
            if sizeX * sizeY != len(data):
                raise ValueError("Data points and (X,Y) size for the image do not match!")
            # 1-D array
            self.rawData = deepcopy(data)
            self.imgMatrix = np.reshape(self.rawData, (sizeX, sizeY))
        elif self.shape == (sizeX, sizeY):
            # 2-D array of the right size
            self.imgMatrix = np.reshape(data, (sizeX, sizeY))
            self.rawData = self.imgMatrix.flatten().tolist()
        else:
            # anything else is bad!
            raise ValueError("rawData array dimension does not match (X,Y) size!")

    def setValue(self, x, y, temperature):
        self.rawData[x*self.sizeY+y]=temperature
        self.imgMatrix[x][y]=temperature

    def getValue(self, x, y):
        return self.imgMatrix[x][y]

    def getSize(self):
        return self.size

    def getShape(self):
        return self.shape

    def average(self, otherFrame):
        self.imgMatrix = np.reshape((self.imgMatrix + otherFrame.imgMatrix) / 2,(self.sizeX,self.sizeY))
        self.rawData = self.imgMatrix.flatten().tolist()

    def __add__(a, b):
        return Frame(a.sizeX,a.sizeY,np.array(a.rawData) + np.array(b.rawData))

    def __sub__(a, b):
        return Frame(a.sizeX,a.sizeY,np.array(a.rawData) - np.array(b.rawData))

    def __mul__(a, b):
        return Frame(a.sizeX,a.sizeY,np.array(a.rawData) * np.array(b.rawData))

    def __div__(a, b):
        return Frame(a.sizeX,a.sizeY,np.array(a.rawData) / np.array(b.rawData))

    def correlation(a,b):
        '''
        Calculate the correlation coefficient between the frame a and b.
        The coefficient can range from -1 to +1
        :param a: a Frame
        :param b: b Frame
        :return: the correlation value between a and b
        '''
        return np.corrcoef(np.array((a.rawData,b.rawData)))[0, 1]

    def binary(self,detected_objects):
        '''

        :param detected_objects: list of DetectedObject instances
        :return: a Frame istance, with all background pixels = 0
                 and the objects pixels = 1
        '''
        binaryFrame = Frame(self.sizeX,self.sizeY,[0]*self.sizeX*self.sizeY)
        for detectedObj in detected_objects:
            for point in detectedObj.getPoints():
                binaryFrame.setValue(point.x, point.y,1)
        return binaryFrame

    def stdDev(self):
        '''
        Calculate Standard Deviation of the frame temperature
        :return: the standard deviation
        '''
        return np.std(self.rawData)

    def expand(self, sizeX, sizeY):
        pts = np.array([[i, j] for i in np.linspace(0, 1, self.sizeX) for j in np.linspace(0, 1, self.sizeY)])
        grid_x, grid_y = np.mgrid[0:1:sizeX * 1j, 0:1:sizeY * 1j]
        self.rawData = np.reshape(griddata(pts, self.rawData, (grid_x, grid_y), method='cubic'), sizeX * sizeY)
        self.sizeX = sizeX
        self.sizeY = sizeY
        self.imgMatrix = np.reshape(self.rawData, (sizeX, sizeY))

    def flipH(self):
        self.imgMatrix = np.fliplr(self.imgMatrix)
        self.rawData = self.imgMatrix.flatten().tolist()

    def flipV(self):
        self.imgMatrix = np.flipud(self.imgMatrix)
        self.rawData = self.imgMatrix.flatten().tolist()

    def max(self):
        return max(self.rawData)

    def min(self):
        return min(self.rawData)

    def mean(self):
        return np.mean(self.rawData)

    def median(self):
        return np.median(self.rawData)

    def clone(self):
        return Frame(self.sizeX,self.sizeY,self.rawData)

    def filterNoise(self):
        self.imgMatrix = medfilt(self.imgMatrix, 5)
        self.rawData = self.imgMatrix.flatten().tolist()

    def __repr__(self):
        return str(self.imgMatrix)

class DetectedObject(object):
    def __init__(self,label=None,points=[]):
        '''
        Initialise the object
        :param label: the name of the detected object
        :param points: dictionary of points making up the
                       detected object. Each point is
                       a dictionary {(x,y) :temperature}
        '''
        self.label=label
        self.points=points

    def getLabel(self):
        return self.label

    def getSize(self):
        pass

    def getPoints(self):
        return self.points

    def setLabel(self,label):
        self.label=label

    def addPoint(self,point):
        self.points= self.points + [point]

    def removePoint(self,point):
        pass

    def getAvgTemperature(self):
        pass

    def distance(self,otherObject):
        '''
        calculate distance between 2 object, using
        a naive definition of distance as the minimun distance
        between pixels of the 2 object
        :param otherObject: the second object to calculate
        distance from
        :return:
        '''
        distance=999
        for pointA in self.getPoints():
            for pointB in otherObject.getPoints():
                currDistance = pointA - pointB
                if currDistance < distance:
                    distance = currDistance
        return distance

    def __eq__(self,other):
        if self.__hash__() == other.__hash__():
            return True
        else:
            return True if self.distance(other) <= 1.0 else False

    def __hash__(self):
        h=hash(frozenset(self.points))
        return h

    def __repr__(self):
        return "%r,%r" % (self.label, self.points)

class ImageProcessor(object):
    S_PROCESS_BACKGROUND = 1  # need to acquire frames to set background
    S_PROCESS_IMAGE = 2  # background is set, can process image for change

    def __init__(self, detection_mode=MODE_ANY , threshold_abs=DEFAULT_ABSOLUTE_THRESHOLD,
                 threshold_diff=DEFAULT_DIFFERENTIAL_THRESHOLD, window_size = DEFAULT_WINDOW_SIZE):
        '''

        :param detection_mode: detection mode. Available modes are
                               MODE_ABSOLUTE: the threshold for detection is
                                              an absolute temperature
                               MODE_DIFFERENTIAL: the threshold for detection
                                                  is evaluated on the difference
                                                  between foreground and backgroud
                                                  temperatures
                               The modes can be combined together using bitwise OR,
                               which will use both thresholds to detect objects
                               default value: MODE_ABSOLUTE | MODE_DIFFERENTIAL
        :param threshold_abs: value for the absolute temperature (default 25C)
        :param threshold_diff:value for the differential temperature (default 2C)
        :param window_size:number of frame processed to set the background image
        '''
        self.thresholdDiff = threshold_diff
        self.thresholdAbs = threshold_abs
        self.detectionMode=detection_mode
        self.background=None
        self.currentFrame=None
        self.detectedObjects={}
        self.detectionCallbacks={}
        self.detectionCallbacks[OBJECT_IN] = []
        self.detectionCallbacks[OBJECT_OUT] = []
        self.trackingCallbacks={}
        self.currentFrame=None
        self.bkgIdx = 0
        self.windowSize = window_size
        self.status = ImageProcessor.S_PROCESS_BACKGROUND

    def getDetectedObjects(self):
        return self.detectedObjects

    def getObjectByLabel(self,label):
        pass

    def addDetectionCallback(self, callback, event):
        '''
        Add a detection callback, invoked whenever an object is
        detected.
        The callback will receive the following arguments:
        detection_callback(detected_object,event,frame)
            detected_object: a DetectedObject instance
            event: either OBJECT_IN (new detection) or OBJECT_OUT (object disappeared)
            frame: a Frame instance of the frame where object has been detected
        :param callback: function called in event of movement detected
        :param event: detection event as follow
                      OBJECT_IN = new object detected
                      OBJECT_OUT= previously detected object now undetected
        :return:
        '''
        if event not in self.detectionCallbacks.keys():
            self.detectionCallbacks[event] = []

        self.detectionCallbacks[event] += [callback]

    def addTrackingCallback(self,objectLabel, callback):
        '''
        Add a tracking callback, invoked whenever an object movement is
        detected.
        The callback will receive the following arguments:
        tracking_callback(object_label,old_position_points,new_position_points)

        :param objectLabel: label of the object to be tracked
        :param callback: function called in event of movement detected
        :return:
        '''
        pass

    def updateBackground(self):
        self.bkgIdx = 0
        self.status=ImageProcessor.S_PROCESS_BACKGROUND

    def processFrame(self,frame):
        '''
        process the frame
        :param frame: frame to process
        :return: status of the processing
        '''
        if self.status == ImageProcessor.S_PROCESS_BACKGROUND:
            # process background:
            # The background thermal image will be calculated as
            # the moving average of 'self.windowSize' number of
            # consecutive frames. As the background image is supposed
            # to be sort of 'steady-state', each frame should show strong
            # correlation with the previously acquired sample.
            # If change is detected, start the processing of the background
            # again.
            if self.bkgIdx == 0:
                self.background = frame.clone()
            elif self.bkgIdx < self.windowSize -1 :
                corr_coeff = Frame.correlation(self.background, frame)
                if abs(corr_coeff) >= 0.5:  # moderate to strong correlation
                    self.background.average(frame)
                else:
                    self.background = frame.clone()
                    self.bkgIdx = 0
            else:
                self.status = ImageProcessor.S_PROCESS_IMAGE
            self.bkgIdx = self.bkgIdx + 1
        elif self.status == ImageProcessor.S_PROCESS_IMAGE:
            currentDetectedObjs = deepcopy(self.detectedObjects)
            self.currentFrame = frame.clone()
            self.detectedObjects = self.detectObjects()
            detectedObjs = deepcopy(self.detectedObjects)
            # compare the list of detected objects with
            # the one already detected and notify callbacks
            differentObjs = list(set(detectedObjs) ^ set(currentDetectedObjs))
            detectedObjs = list(set(detectedObjs) & set(differentObjs))
            currentDetectedObjs = list(set(currentDetectedObjs) & set(differentObjs))
            for newDetObj in detectedObjs:
                for cb in self.detectionCallbacks[OBJECT_IN]:
                    cb(newDetObj, OBJECT_IN, frame)
            for currDetObj in currentDetectedObjs:
                for cb in self.detectionCallbacks[OBJECT_OUT]:
                    cb(currDetObj, OBJECT_OUT, frame)
        return self.status

    def isThresholdPassed(self,x,y,frame=None):
        passed = False
        currentFrame = frame if frame != None else self.currentFrame
        temperature = currentFrame.getValue(x,y)
        if temperature != SKIP_TEMPERATURE:
            passedAbs = temperature>=self.thresholdAbs
            if self.background != None:
                passedDiff = (temperature - self.background.getValue(x, y)) >= self.thresholdDiff
            else:
                passedDiff = False
            if self.detectionMode == MODE_ABSOLUTE:
                passed = passedAbs
            elif self.detectionMode == MODE_DIFFERENTIAL:
                passed = passedDiff
            elif self.detectionMode == MODE_BOTH:
                passed = passedAbs and passedDiff
            else: #default MODE_ANY
                passed = passedAbs or passedDiff
        return passed

    def detectObjects(self):
        objects=[]
        objIdx=1
        workFrame = self.currentFrame.clone()
        for x in range(0,workFrame.sizeX):
            for y in range(0,workFrame.sizeY):
                if self.isThresholdPassed(x,y):
                    points = self.extractPoints(x,y,workFrame)
                    detectedObj = DetectedObject(str(objIdx),points)
                    objects = objects + [detectedObj]
                    objIdx = objIdx + 1
        return objects

    def extractPoints(self,x,y,frame):
        '''
        Extract all the points that belong to the same object with temperature >= threshold
        (points belong to the same object if they are neighbors of the (x,y) point)

        :param x: x coord. center of the neighbors matrix to check
        :param y: y coord. center of the neighbors matrix to check
        :param frame: the image to scan
        :return: points dictionary (ex: {(x1,y1):temp1,(x2,y2):temp2})
        '''
        points=[Point(x, y, frame.getValue(x, y))]
        xmin = x-1 if x>0 else 0
        xmax = x+1 if x<frame.sizeX-1 else frame.sizeX-1
        ymin = y-1 if y>0 else 0
        ymax = y+1 if y<frame.sizeY-1 else frame.sizeY-1
        frame.imgMatrix[x][y] = SKIP_TEMPERATURE #self.background.imgMatrix[x][y]
        for xi in range(xmin,xmax+1):
            for yi in range(ymin,ymax+1):
                if self.isThresholdPassed(xi,yi,frame) and (xi,yi) != (x,y):
                    points= points + self.extractPoints(xi, yi, frame)
        return points


if __name__ == '__main__':
    # data=[1,2,3,4]
    # data2=[5,6,7,8]
    # f=Frame(2,2,data)
    # f2=Frame(2,2,data2)
    #
    # fdiff = f-f2
    # print fdiff
    # print f.getShape()
    # print f.getSize()
    # print f.rawData
    # print f.imgMatrix
    # print f2.imgMatrix
    # f.average(f2)
    # print f.rawData
    # print f.imgMatrix
    # f.expand(4,4)
    # print f
    # f.flipH()
    # print f
    # do = DetectedObject('test')
    # do.addPoint((1,1,25))
    # do.addPoint((2,3,24))
    # print do

    frame=[None]*14
    frame[0]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[1]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[2]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[3]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[4]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[5]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[6]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[7]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[8]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[9]=Frame(4,4,[20,23,21,23,20,23,22,23,20,23,23,23,22,23,21,23])
    frame[10]=Frame(4,4,[20,23,21,23,20,23,24,23,20,23,25,23,22,23,21,23])
    frame[11]=Frame(4,4,[20,23,21,23,24,23,23,23,25,23,23,23,26,23,21,23])
    frame[12]=Frame(4,4,[20,23,21,23,24,22,23,23,25,23,23,23,26,23,21,23])
    frame[13]=Frame(4,4,[20,23,21,23,20,23,24,23,20,23,25,23,26,23,21,23])

    monitor = ImageProcessor()

    def callback_f(detected,event,frame):
        if event == OBJECT_IN:
            print "detected object! (%s)" % detected
        else:
            print "deleted object! (%s)" % detected

    monitor.addDetectionCallback(callback_f, OBJECT_IN)
    monitor.addDetectionCallback(callback_f, OBJECT_OUT)

    for currFrame in frame:
        monitor.processFrame(currFrame)

    print monitor.detectedObjects
    # print frame
    # print frame.binary(24)
    # print monitor.detectObjects(frame)
    #
    # tup1=Point(1,1,20)
    # tup2=Point(4,7,21)
    #


    # print tup1 -tup2
    # print tup2.distance(tup1)