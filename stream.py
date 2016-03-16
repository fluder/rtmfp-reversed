from gevent.queue import Queue
from events import EventDriven

class Stream(EventDriven):
    def __init__(self):
        super(Stream, self).__init__()

        self.queue = Queue()
        self.produce_cb = lambda stream, data: None

    def consume(self, filter=None):
        while True:
            data = self.queue.get()
            if not filter or filter(data):
                break

        return data

    def produce(self, data):
        self.produce_cb(self, data)