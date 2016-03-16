from stream import Stream
from session_message import *
from flow_message import db as message_db, FlowMessage, RawWithHandler
import gevent


class FlowBuffer(object):
    def __init__(self):
        self.max_seq = 0
        self.seq = 1
        self.segments = {}

    def add(self, seq, segment):
        assert isinstance(seq, int)
        if seq < self.seq:
            return

        self.segments[seq] = segment

        while True:
            if not self.segments.has_key(self.max_seq+1):
                break
            self.max_seq+=1


    def pop(self):
        if self.max_seq < self.seq:
            return None

        segment = self.segments[self.seq]
        del self.segments[self.seq]
        self.seq+=1

        return segment

    def abandon(self, to_seq):
        if to_seq <= self.seq:
            return

        for seq in self.segments.keys():
            if seq < to_seq:
                del self.segments[seq]

        self.seq = to_seq
        self.max_seq = to_seq-1

        while True:
            if not self.segments.has_key(self.max_seq+1):
                break
            self.max_seq+=1


class Flow(Stream):
    signature = None

    def __init__(self, id, base_flow=None):
        super(Flow, self).__init__()

        self.id = id
        self.base_flow = None

        self.buffer = FlowBuffer()
        self.out_buffer = []
        self.out_seq = 1
        self.acked = False
        self.accumulator = []
        self.created = False

        self.active = False

        gevent.spawn(self._writer)

    def handle(self, msg):
        if not self.active:
            self.active = True
            self.emit("activate")
        if type(msg) in (NormalUserData, NextUserData):
            self.buffer.add(msg.f_seq, msg)
            print "Added segment to buffer"

            if self.buffer.seq < msg.f_seq-msg.f_delta:
                self.buffer.abandon(msg.f_seq-msg.f_delta)
                self.accumulator = []

            super(Flow, self).produce(Ack(flow_id=self.id, seq=self.buffer.seq, value=1))

            while True:
                msg = self.buffer.pop()
                if msg is None:
                    break

                if msg.f_withbeforepart and not self.accumulator:
                    print "[flow_debug] with_before_part but accumulator is empty (packet loss?)"
                    continue

                self.accumulator.append(msg.f_segment)
                if not msg.f_withafterpart:
                    # last segment
                    data = ""
                    for segment in self.accumulator:
                        data+=segment

                    self.accumulator = []

                    msg_type, data = ord(data[0]), data[1:]
                    flow_msg = message_db.get(msg_type, RawWithHandler)(data)
                    flow_msg.unpack()
                    flow_msg.f_id = flow_msg.id = msg_type
                    self.queue.put(flow_msg)

        elif isinstance(msg, Ack):
            if msg.f_value >= 0:
                self.acked = True
                count = self.out_seq-msg.f_seq
                if count < 0:
                    print "[debug_flow] Strange seq in ack"
                    count = 0
                self.out_buffer = self.out_buffer[:0-count]


    def produce(self, msg):
        data = chr(msg.id)+msg.pack()

        last_data = None
        while len(data):
            segment_data, data = data[:1024], data[1024:]

            print self.signature if not self.acked else None
            segment = NormalUserData(
                flow_id=self.id, seq=self.out_seq, delta=len(self.out_buffer)+1,
                signature=self.signature if not self.acked else None,
                fullduplex=self.base_flow.id if not self.acked and self.base_flow else None,
                segment=segment_data, withbeforepart=(last_data!=None), withafterpart=(len(data)>0)
            )
            self.out_buffer.append(segment)
            self.out_seq+=1
            last_data = segment_data

            print "Producing %s" % segment.__class__
            super(Flow, self).produce(segment)
        if not self.active:
            self.active = True
            self.emit("activate")

    def _writer(self):
        while True:
            gevent.sleep(2)
            for i, segment in enumerate(self.out_buffer):
                segment.f_delta = i+1
                if self.acked:
                    segment.f_fullduplex = None
                    segment.f_signature = None
                super(Flow, self).produce(segment)



from flow_connection import ConnectionFlow
from flow_group import GroupFlow

db = {
    "\x00TC\x04\x00": ConnectionFlow,
    "\x00GC": GroupFlow
}