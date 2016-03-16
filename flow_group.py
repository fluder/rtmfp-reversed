from flow import Flow
from flow_message import RawWithHandler
from message import Message


class RawGroupMessage(Message): pass

class GroupJoin(RawGroupMessage):
    id = 0x01

    f_group_id = None

    def _unpack(self):
        self.f_group_id = self.read("bytes")

    def _pack(self):
        self.write("bytes", self.f_group_id)

class BestPeer(RawGroupMessage):
    id = 0x0b

    f_peer_id = None

    def _unpack(self):
        self.f_peer_id = self.read("bytes")

    def _pack(self):
        self.write("bytes", self.f_peer_id)


db = {
    0x01: GroupJoin,
    0x0b: BestPeer
}


class GroupFlow(Flow):
    signature = "\x00GC"

    def consume(self, filter=None):
        msg = super(GroupFlow, self).consume()

        if isinstance(msg, RawWithHandler):
            try:
                type_ = db[msg.id]
            except KeyError:
                return msg

            c_msg = type_(msg.f_payload)
            c_msg.unpack()
            c_msg.f_handler = msg.f_handler

            return c_msg

    def produce(self, msg):
        c_msg = RawWithHandler(payload=msg.pack())
        c_msg.id = msg.id
        c_msg.f_handler = msg.f_handler
        super(GroupFlow, self).produce(c_msg)