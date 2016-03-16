import hashlib
from message import Message

class SessionMessage(Message):
    pass

class InitiatorHello(SessionMessage):
    id = 0x30

    f_epd_type = None
    f_epd = None
    f_tag = None

    def _unpack(self):
        epd_data = self.read("int7int7bytes")
        self.f_epd_type = ord(epd_data[0])
        self.f_epd = epd_data[1:]

        self.f_tag = self.read("bytes", 16)

    def _pack(self):
        assert self.f_epd_type is not None
        assert self.f_epd is not None
        assert self.f_tag is not None and len(self.f_tag) == 16

        epd_data = chr(self.f_epd_type)+self.f_epd
        self.write("int7int7bytes", epd_data)
        self.write("bytes", self.f_tag)


class ResponderHello(SessionMessage):
    id = 0x70

    f_tag_echo = None
    f_cookie = None
    f_certificate = None
    f_certificate2 = None

    def _unpack(self):
        self.f_tag_echo = self.read("int7bytes")
        self.f_cookie = self.read("int7bytes")
        self.read("bytes", 4)
        self.f_certificate = self.read("bytes", 64)

    def _pack(self):
        assert self.f_tag_echo is not None
        assert self.f_cookie is not None
        assert self.f_certificate is not None and len(self.f_certificate) == 64

        self.write("int7bytes", self.f_tag_echo)
        self.write("int7bytes", self.f_cookie)
        if self.f_certificate2:
            self.write("bytes", "\x81\x02\x1D\x02")
        else:
            self.write("bytes", "\x01\x0a\x41\x0e")

        if self.f_certificate2:
            self.write("bytes", self.f_certificate2)
        else:
            self.write("bytes", self.f_certificate)
            self.write("bytes", "\x02\x15\x02\x02\x15\x05\x02\x15\x0E")


class InitiatorInitialKeying(SessionMessage):
    id = 0x38

    f_session_id = None
    f_cookie_echo = None
    f_certificate = None
    f_public_key = None

    @property
    def nonce(self):
        return "\x02\x1d\x02\x41\x0e"+self.f_certificate+"\x03\x1a\x02\x0a\x02\x1e\x02"

    @property
    def peer_id(self):
        m = Message()
        m.write("int7bytes", "\x1d\x02"+self.f_public_key)

        return hashlib.sha256(m.pack()).digest()

    def _unpack(self):
        self.f_session_id = self.read("uint32")
        self.f_cookie_echo = self.read("int7bytes")
        key_data = self.read("int7bytes")
        self.f_public_key = key_data[-128:]
        certificate_data = self.read("int7bytes")
        self.f_certificate = certificate_data[5:-7]
        self.read("bytes", 1)

    def _pack(self):
        assert self.f_session_id is not None
        assert self.f_cookie_echo is not None
        assert self.f_certificate is not None
        assert self.f_public_key is not None

        self.write("uint32", self.f_session_id)
        self.write("int7bytes", self.f_cookie_echo)
        self.write("int7int7bytes", "\x1d\x02"+self.f_public_key)
        self.write("int7bytes", self.nonce)
        self.write("bytes", "\x58")


class ResponderInitialKeying(SessionMessage):
    id = 0x78

    f_session_id = None
    f_public_key = None

    @property
    def nonce(self):
        return "\x03\x1a\x00\x00\x02\x1e\x00\x81\x02\x0d\x02"+self.f_public_key

    def _unpack(self):
        self.f_session_id = self.read("uint32")
        key_data = self.read("int7bytes")
        self.f_public_key = key_data[11:]
        self.read("bytes", 1)

    def _pack(self):
        assert self.f_session_id is not None
        assert self.f_public_key is not None

        self.write("uint32", self.f_session_id)
        self.write("int7bytes", self.nonce)
        self.write("bytes", "\x58")


class ForwardedHelloResponse(SessionMessage):
    id = 0x71

    f_tag_echo = None
    f_addrs = None

    def _unpack(self):
        self.f_tag_echo = self.read("int7bytes")
        self.f_addrs = []

        while self.available() > 0:
            flags = self.read("uint8")

            addr = (
                "%i.%i.%i.%i" % (self.read("uint8"), self.read("uint8"), self.read("uint8"), self.read("uint8")),
                self.read("uint16")
            )
            is_public = bool(flags & 0x02)

            self.f_addrs.append((is_public, addr))

    def _pack(self):
        self.write("int7bytes", self.f_tag_echo)

        for is_public, addr in self.f_addrs:
            self.write("uint8", 0x02 if is_public else 0x01)
            for bit in addr[0].split("."):
                self.write("uint8", int(bit))
            self.write("uint16", addr[1])


class ForwardedInitialHello(SessionMessage):
    id = 0x0f

    f_epd_type = None
    f_epd = None
    f_addr = None
    f_addr_is_public = None
    f_flags = None
    f_tag = None

    def _unpack(self):
        epd_data = self.read("int7int7bytes")
        self.f_epd_type = ord(epd_data[0])
        self.f_epd = epd_data[1:]
        self.f_flags = flags = self.read("uint8")
        self.f_addr_is_public = bool(flags & 0x02)
        self.f_addr = (
            "%i.%i.%i.%i" % (self.read("uint8"), self.read("uint8"), self.read("uint8"), self.read("uint8")),
            self.read("uint16")
            )
        self.f_tag = self.read("bytes")

    def _pack(self):
        epd_data = chr(self.f_epd_type)+self.f_epd
        self.write("int7int7bytes", epd_data)
        self.write("uint8", 0x02 if self.f_addr_is_public else 0x01)

        for bit in self.f_addr[0].split("."):
            self.write("uint8", int(bit))
        self.write("uint16", self.f_addr[1])
        self.write("bytes", self.f_tag)


class SessionInfoMessage(SessionMessage):
    def _unpack(self): pass
    def _pack(self): pass


class KeepAliveRequest(SessionInfoMessage): id = 0x01
class KeepAliveResponse(SessionInfoMessage):  id = 0x41
class ClientFailed(SessionInfoMessage): id = 0x0c
class SessionDied(SessionInfoMessage): id = 0x4c


WITH_BEFOREPART = 0x20
WITH_AFTERPART = 0x10
FLOW_END = 0x01

class UserData(SessionMessage):
    f_segment = None
    f_signature = None
    f_fullduplex = None
    f_withbeforepart = None
    f_withafterpart = None
    f_end = None

    def _unpack_header(self):
        headers = []
        while True:
            header_size = self.read("uint8")
            if not header_size:
                break

            headers.append(Message(self.read("bytes", header_size)))

        if len(headers) > 0:
            self.f_signature = str(headers[0])
        if len(headers) > 1:
            headers[1].read("bytes", 1)
            self.f_fullduplex = headers[1].read("int7")

    def _pack_header(self):
        if self.f_signature is not None:
            self.write("uint8", len(self.f_signature))
            self.write("bytes", self.f_signature)
        if self.f_fullduplex is not None:
            header = Message()
            header.write("uint8", 0x0a)
            header.write("int7", self.f_fullduplex)

            self.write("uint8", len(str(header)))
            self.write("bytes", str(header))

        if self.f_fullduplex or self.f_signature:
            self.write("uint8", 0x00)

    def _unpack_flags(self, flags):
        self.f_flags = flags
        self.f_withafterpart = bool(flags & WITH_AFTERPART)
        self.f_withbeforepart = bool(flags & WITH_BEFOREPART)
        self.f_end = bool(flags & FLOW_END)

    def _pack_flags(self):
        flags = 0
        if self.f_signature:
            flags|=0x80

        if self.f_withafterpart:
            flags|=WITH_AFTERPART

        if self.f_withbeforepart:
            flags|=WITH_BEFOREPART

        if self.f_end:
            flags|=FLOW_END

        return flags

class NormalUserData(UserData):
    id = 0x10

    f_flow_id = None
    f_seq = None
    f_delta = None

    def _unpack(self):
        flags = self.read("uint8")
        self.f_flow_id = self.read("int7")
        self.f_seq = self.read("int7")
        self.f_delta = self.read("int7")

        if flags & 0x80:
            self._unpack_header()

        self._unpack_flags(flags)

        self.f_segment = self.read("bytes")

    def _pack(self):
        assert self.f_flow_id is not None
        assert self.f_seq is not None
        assert self.f_delta is not None

        flags = self._pack_flags()

        self.write("uint8", flags)
        self.write("int7", self.f_flow_id)
        self.write("int7", self.f_seq)
        self.write("int7", self.f_delta)

        self._pack_header()

        if self.f_segment:
            self.write("bytes", self.f_segment)


class NextUserData(UserData):
    id = 0x11

    def _unpack(self):
        flags = self.read("uint8")
        if flags & 0x80:
            self._unpack_header()

        self._unpack_flags(flags)

        self.f_segment = self.read("bytes")

    def _pack(self):
        flags = self._pack_flags()

        self.write("uint8", flags)
        self._pack_header()

        self.write("bytes", self.f_segment)


class Ack(SessionMessage):
    id = 0x51

    f_flow_id = None
    f_value = None
    f_seq = None

    def _unpack(self):
        self.f_flow_id = self.read("int7")
        marker = self.read("int8")

        while marker == -0x1:
            # Happens after response is resend many times...
            marker = self.read("int8")

        self.f_value = marker
        self.f_seq = self.read("int7")

    def _pack(self):
        assert self.f_flow_id is not None
        assert self.f_value is not None
        assert self.f_seq is not None

        self.write("int7", self.f_flow_id)
        self.write("int8", self.f_value)
        self.write("int7", self.f_seq)

class Nack(SessionMessage):
    id = 0x5e

    f_flow_id = None

    def _unpack(self):
        self.f_flow_id = self.read("int7")

    def _pack(self):
        assert self.f_flow_id is not None

        self.write("int7", self.f_flow_id)


db = {
    0x30: InitiatorHello,
    0x70: ResponderHello,
    0x38: InitiatorInitialKeying,
    0x78: ResponderInitialKeying,
    0x71: ForwardedHelloResponse,
    0x0f: ForwardedInitialHello,
    0x01: KeepAliveRequest,
    0x41: KeepAliveResponse,
    0x10: NormalUserData,
    0x11: NextUserData,
    0x51: Ack,
    0x5e: Nack,
    0x0c: ClientFailed,
    0x4c: SessionDied
}