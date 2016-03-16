from amf import AMF0
from message import Message


class FlowMessage(Message): pass


class AmfWithHandler(FlowMessage):
    id = 0x14

    f_amf = None
    f_name = None
    f_handler = None

    def _unpack(self):
        self.f_handler = self.read("uint32")
        self.f_amf = AMF0(self.read("bytes"))
        self.f_name = self.f_amf.read()

    def _pack(self):
        assert self.f_amf is not None
        self.write("uint32", self.f_handler or 0)
        amf = AMF0()
        amf.write(self.f_name)
        self.f_amf = AMF0(self.f_amf.data.getvalue())
        while True:
            try:
                data = self.f_amf.read()
                amf.write(data)
            except EOFError:
                break

        self.write("bytes", amf.data.getvalue())

class AmfWithHandler1(AmfWithHandler):
    id = 0x11

    def _unpack(self):
        self.f_handler = self.read("bytes", 1)
        super(AmfWithHandler1, self)._unpack()

    def _pack(self):
        self.write("uint8", self.f_handler or 0)
        super(AmfWithHandler1, self)._pack()


class RawWithHandler(FlowMessage):
    f_handler = None
    f_payload = None

    def _unpack(self):
        self.f_payload = self.read("bytes")

    def _pack(self):
        self.write("bytes", self.f_payload)


class RawWithHandler1(RawWithHandler):
    id = 0x04

    f_handler = None
    f_payload = None

    def _unpack(self):
        self.f_handler = self.read("uint32")
        self.f_payload = self.read("bytes")

    def _pack(self):
        self.write("uint32", self.f_handler or 0)
        self.write("bytes", self.f_payload)

db = {
    0x14: AmfWithHandler,
    0x11: AmfWithHandler1,
    0x04: RawWithHandler1
}