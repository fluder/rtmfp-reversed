from Crypto.Cipher import AES
import struct
from message import Message

DEFAULT_KEY = "Adobe Systems 02"

WITH_TIMESTAMP = 0x08
WITH_TIMESTAMP_ECHO = 0x04
FLASH_TO_SERVER = 0x01
SERVER_TO_FLASH = 0x02


class EtherMessage(Message):
    f_session_id = None
    f_encrypted_part = None

    # Merged from EtherDecryptedPart
    f_checksum = None
    f_is_valid = None
    f_invalid_payload = None
    f_timestamp = None
    f_timestamp_echo = None
    f_direction = None
    f_is_handshake = None
    f_chunks = None

    def unpack_basic(self):
        scrambled_id = self.read("uint32")
        self.f_session_id = scrambled_id^self.read("uint32")^self.read("uint32")
        self.reset(4)
        self.f_encrypted_part = self.read("bytes")

    def _unpack(self, key=None):
        assert self.f_encrypted_part is not None

        self.read("bytes")
        cipher = AES.new(key or DEFAULT_KEY, AES.MODE_CBC, "\x00"*16)
        decrypted_part = EtherDecryptedPart(cipher.decrypt(self.f_encrypted_part))
        decrypted_part.unpack()

        self.merge(decrypted_part)

    def _pack(self, key=None):
        assert self.f_session_id is not None

        decrypted_part = EtherDecryptedPart()
        decrypted_part.merge(self)
        cipher = AES.new(key or DEFAULT_KEY, AES.MODE_CBC, "\x00"*16)
        self.f_encrypted_part = cipher.encrypt(decrypted_part.pack())

        bits = struct.unpack_from(">II", self.f_encrypted_part)
        scrambled_id = self.f_session_id^bits[0]^bits[1]

        self.write("uint32", scrambled_id)
        self.write("bytes", self.f_encrypted_part)

    def repack(self, key=None):
        msg = type(self)(str(self) or self.pack())
        msg.unpack_basic()
        msg.unpack(key)

        return msg

class EtherDecryptedPart(Message):
    f_checksum = None
    f_is_valid = None
    f_invalid_payload = None
    f_timestamp = None
    f_timestamp_echo = None
    f_direction = None
    f_is_handshake = None
    f_chunks = None

    def _unpack(self):
        self.f_checksum = self.read("uint16")
        self.f_is_valid = (self._compute_checksum(self.rest()) == self.f_checksum)

        if not self.f_is_valid:
            self.f_invalid_payload = self.rest()
            return

        flags = self.read("uint8")
        self.f_timestamp = self.read("uint16")
        if flags & WITH_TIMESTAMP_ECHO:
            self.f_timestamp_echo = self.read("uint16")
        self.f_is_handshake = True if (flags & FLASH_TO_SERVER and flags & SERVER_TO_FLASH) else False
        if not self.f_is_handshake:
            self.f_direction = FLASH_TO_SERVER if flags & FLASH_TO_SERVER else SERVER_TO_FLASH

        self.f_chunks = []
        while self.available() > 0:
            type = self.read("uint8")
            if type == 0x00 or type == 0xff:
                break

            size = self.read("uint16")
            payload = self.read("bytes", size)

            self.f_chunks.append((type, payload))

    def _pack(self):
        assert self.f_timestamp is not None
        assert self.f_is_handshake or self.f_direction
        flags = WITH_TIMESTAMP
        if self.f_timestamp_echo is not None:
            flags|=WITH_TIMESTAMP_ECHO
        if self.f_is_handshake:
            flags|=FLASH_TO_SERVER
            flags|=SERVER_TO_FLASH
        else:
            flags|=self.f_direction

        self.write("uint8", flags)
        self.write("uint16", self.f_timestamp)
        if self.f_timestamp_echo:
            self.write("uint16", self.f_timestamp_echo)

        assert self.f_chunks is not None
        for type, payload in self.f_chunks:
            self.write("uint8", type)
            self.write("uint16", len(payload))
            self.write("bytes", payload)


        padding_len = 16 - ((len(self)+2) % 16)

        if padding_len:
            self.write("bytes", "\xff"*padding_len)

        data = str(self)
        checksum = self._compute_checksum(data)
        self.crop()

        self.write("uint16", checksum)
        self.write("bytes", data)

    def _compute_checksum(self, data):
        """
        Compute checksum of the decrypted data
        """
        parser = Message(data)
        result = 0

        while parser.available():
            result+=parser.read('uint16') if parser.available > 1 else parser.read('uin8')

        result = (result >> 16) + (result & 0xffff)
        result += result >> 16

        return ~result % 2**16