from flow import Flow
from message import Message
from flow_message import AmfWithHandler, RawWithHandler, FlowMessage
from amf import AMF0

class FlowConnectionMessage(object):
    def __init__(self, amf=None, **kwargs):
        self.amf = amf

        for key, value in kwargs.items():
            print "f_"+key
            assert hasattr(self, "f_"+key)
            setattr(self, "f_"+key, value)

    def unpack(self):
        if hasattr(self, "_unpack"):
            self._unpack(self.amf)

    def pack(self):
        if hasattr(self, "_pack"):
            amf = AMF0()
            self._pack(amf)
            return amf
        else:
            return self.amf


    def explain(self, fields=None, c="|", compact=True):
        result = "%s %s\n" % (c, type(self))

        if compact:
            return result.strip()

        for field in dir(self):
            if field.startswith("f_"):
                if fields is not None and field[2:] not in fields:
                    continue
                value = getattr(self, field)
                if value is None:
                    continue
                result+=" %s  %s: %s\n" % (c, field[2:], repr(getattr(self, field)))

        return " "+result+" +"

class Connect(FlowConnectionMessage):
    id = "connect"

    f_version = None
    f_args = None

    def _unpack(self, amf):
        self.f_version = amf.read()
        self.f_args = amf.read()

    def _pack(self, amf):
        amf.write(self.f_version)
        amf.write(self.f_args)

class Result(FlowConnectionMessage):
    id = "_result"

    f_args = None
    f_version = None
    f_unknown = None

    def _unpack(self, amf):
        self.f_version = amf.read()
        self.f_unknown = amf.read()
        self.f_args = amf.read()

    def _pack(self, amf):
        assert self.f_args is not None

        amf.write(self.f_version)
        amf.write(self.f_unknown)
        amf.write(self.f_args)

class SetPeerInfo(FlowConnectionMessage):
    id = "setPeerInfo"

    f_unknown1 = None
    f_unknown2 = None
    f_addrs = None

    def _unpack(self, amf):
        self.f_unknown1 = amf.read()
        self.f_unknown2 = amf.read()
        self.f_addrs = []

        while True:
            try:
                address = amf.read()
            except EOFError:
                break

            self.f_addrs.append(address)

    def _pack(self, amf):
        amf.write(self.f_unknown1)
        amf.write(self.f_unknown2)
        for addr in self.f_addrs:
            amf.write(addr)


class RawConnectionMessage(Message): pass

class KeepAliveSettings(RawConnectionMessage):
    id = 0x04

    f_server = None
    f_peer = None

    def _unpack(self):
        self.read("uint16")
        self.f_server = self.read("uint32")
        self.f_peer = self.read("uint32")

    def _pack(self):
        self.write("uint16", 0x29)
        self.write("uint32", self.f_server)
        self.write("uint32", self.f_peer)


db = {
    "connect": Connect,
    "_result": Result,
    "setPeerInfo": SetPeerInfo,
    0x04: KeepAliveSettings
}


class ConnectionFlow(Flow):
    signature = "\x00TC\x04\x00"

    def consume(self, filter=None):
        msg = super(ConnectionFlow, self).consume()
        if isinstance(msg, AmfWithHandler):
            c_msg = db.get(msg.f_name, FlowConnectionMessage)(msg.f_amf)
            c_msg.unpack()
            c_msg.f_id = c_msg.id = msg.f_name

            return c_msg
        elif isinstance(msg, RawWithHandler):
            try:
                type_ = db[msg.id]
            except KeyError:
                return msg

            c_msg = type_(msg.f_payload)
            c_msg.unpack()

            return c_msg

    def produce(self, msg):
        if isinstance(msg, FlowMessage):
            super(ConnectionFlow, self).produce(msg)
        elif isinstance(msg, FlowConnectionMessage):
            c_msg = AmfWithHandler(name=msg.id, amf=msg.pack())
            super(ConnectionFlow, self).produce(c_msg)
        else:
            c_msg = RawWithHandler(payload=msg.pack())
            c_msg.id = msg.id
            super(ConnectionFlow, self).produce(c_msg)

