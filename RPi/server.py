import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.gen
from tornado.options import define, options
import multiprocessing
import node
import processor
import sys
import analyser

CONFIG_FILE_DEFAULT='./config/grideye.cfg'
NODE_SECTION = 'Node'
NLR_SECTION= 'Non_Latching_Relays'
LR_SECTION= 'Latching_Relays'
RELAY='Relay'
SEP_TAG='_'
STATUS_ON='ON'
STATUS_OFF='OFF'

define("port", default=8080, help="run on the given port", type=int)

clients = []
                                                    # Communication direction
web_to_node_queue = multiprocessing.Queue()         # UI -> Node
processor_to_web_queue = multiprocessing.Queue()    # Processor -> UI
processor_to_node_queue = multiprocessing.Queue()   # Processor -> Node
node_to_processor_queue = multiprocessing.Queue()   # Node -> Processor

debug_queue = None # multiprocessing.Queue()
processor_debug_queue = None # multiprocessing.Queue()
alarms = []
device = {}

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('./web/index.html')

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print 'new connection'
        clients.append(self)
        self.write_message("connected")

    def on_message(self, message):
        # print 'tornado received from client: %s' % json.dumps(message)
        # self.write_message('ack')
        web_to_node_queue.put(message)
        if debug_queue:
            debug_queue.put("WEB: send msg to node - %s" % message)
        else:
            print "WEB: send msg to node - %s" % message

    def on_close(self):
        print 'connection closed'
        clients.remove(self)


## check the queue for pending messages, and rely that to all connected clients
def checkQueue():
    while not processor_to_web_queue.empty():
        message = processor_to_web_queue.get()
        if debug_queue:
            debug_queue.put( "WEB: recv msg from processor - %s" % message)
        for c in clients:
            c.write_message(message)

def printDebug():
    if debug_queue and not debug_queue.empty():
        print debug_queue.get()
    if processor_debug_queue and not processor_debug_queue.empty():
        print processor_debug_queue.get()

if __name__ == '__main__':
    #read config
    cfgFile = sys.argv[1] if len(sys.argv)>1 else CONFIG_FILE_DEFAULT
    ## start the serial worker in background (as a deamon)
    node = node.Node(web_to_node_queue, processor_to_node_queue, node_to_processor_queue,cfgFile, debug_queue)
    ## start the monitoring process worker in background (as a deamon)
    proc = processor.Processor(node_to_processor_queue, processor_to_node_queue, processor_to_web_queue, processor_debug_queue,
                               detection_mode=analyser.MODE_DIFFERENTIAL,differential_temperature_threshold=2)

    node.daemon = True
    proc.daemon = True
    node.start()
    proc.start()
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        handlers=[
            (r"/", IndexHandler),
            (r'/(jquery.onoff.js)', tornado.web.StaticFileHandler, {'path': './web/'}),
            (r'/(rainbow.js)', tornado.web.StaticFileHandler, {'path': './web/'}),
            (r'/(grideye.js)', tornado.web.StaticFileHandler, {'path': './web/'}),
            (r'/(jquery.onoff.css)', tornado.web.StaticFileHandler, {'path': './web/'}),
            (r'/(grideye.css)', tornado.web.StaticFileHandler, {'path': './web/'}),
            (r"/ws", WebSocketHandler)
        ]
    )
    httpServer = tornado.httpserver.HTTPServer(app)
    httpServer.listen(options.port)
    print "Listening on port:", options.port

    mainLoop = tornado.ioloop.IOLoop.instance()
    # adjust the scheduler_interval according to the frames sent by the serial port
    scheduler_interval = 50
    scheduler = tornado.ioloop.PeriodicCallback(checkQueue, scheduler_interval, io_loop=mainLoop)
    # uncomment if debugging 
    scheduler2 = tornado.ioloop.PeriodicCallback(printDebug, scheduler_interval, io_loop=mainLoop)
    scheduler2.start()
    scheduler.start()
    mainLoop.start()
