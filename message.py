import struct
from copy import deepcopy


#: The maximum that can be represented by a signed 29 bit integer.
MAX_29B_INT = 0x0FFFFFFF

#: The minimum that can be represented by a signed 29 bit integer.
MIN_29B_INT = -0x10000000

def decode_u29(data, offset):
    """
    Decode C{int}.
    """
    n = result = 0
    b, = struct.unpack('B', data[n+offset])

    while b & 0x80 != 0 and n < 3:
        result <<= 7
        result |= b & 0x7f
        n += 1
        b, = struct.unpack('B', data[n+offset])

    if n < 3:
        result <<= 7
        result |= b
    else:
        result <<= 8
        result |= b

        if result & 0x10000000 != 0:
            result <<= 1
            result += 1

    return result, n+1

def encode_u29(n):
    """
    Encodes an int as a variable length signed 29-bit integer as defined by
    the spec.

    @param n: The integer to be encoded
    @return: The encoded string
    @rtype: C{str}
    @raise OverflowError: Out of range.
    """

    if n < MIN_29B_INT or n > MAX_29B_INT:
        raise OverflowError("Out of range")

    if n < 0:
        n += 0x20000000

    bytes = ''
    real_value = None

    if n > 0x1fffff:
        real_value = n
        n >>= 1
        bytes += chr(0x80 | ((n >> 21) & 0xff))

    if n > 0x3fff:
        bytes += chr(0x80 | ((n >> 14) & 0xff))

    if n > 0x7f:
        bytes += chr(0x80 | ((n >> 7) & 0xff))

    if real_value is not None:
        n = real_value

    if n > 0x1fffff:
        bytes += chr(n & 0xff)
    else:
        bytes += chr(n & 0x7f)

    return bytes

struct_map = {
    "int8": (">b", 1),
    "uint8": (">B", 1),
    "int16": (">h", 2),
    "uint16": (">H", 2),
    "int32": (">i", 4),
    "uint32": (">I", 4),
}

class Message(object):
    f_raw_data = None

    def __init__(self, data=None, **kwargs):
        self.buffer = data or ""
        self.pos = 0

        for key, value in kwargs.items():
            if not hasattr(self, "f_"+key):
                raise KeyError("Unknown field supplied: %s" % key)
            setattr(self, "f_"+key, value)

    def __getitem__(self, item):
        return self.buffer[item]

    def read(self, type, *args, **kwargs):
        if type in struct_map:
            spec, size = struct_map[type]
            if len(self.buffer) < self.pos+size:
                raise ValueError("Not enough bytes left")
            value, = struct.unpack(spec, self.buffer[self.pos:self.pos+size])
        elif type == "bytes":
            size = args[0] if args else kwargs.get("size", None)
            size = size or len(self.buffer)-self.pos
            if len(self.buffer) < self.pos+size:
                raise ValueError("Not enough bytes left")
            value = self.buffer[self.pos:self.pos+size]
        elif type == "int7":
            value, size = decode_u29(self.buffer[self.pos:], 0)
        elif type == "int7bytes":
            value = self.read("bytes", self.read("int7"))
            size = 0
        elif type == "int7int7bytes":
            self.read("int7")
            value = self.read("bytes", self.read("int7"))
            size = 0
        else:
            raise TypeError("Unknown type specifier supplied")

        self.pos+=size
        return value

    def write(self, type, value, *args, **kwargs):
        if type in struct_map:
            spec, size = struct_map[type]
            self.buffer+=struct.pack(spec, value)
        elif type == "bytes":
            self.buffer+=value
        elif type == "int7":
            self.buffer+=encode_u29(value)
        elif type == "int7bytes":
            self.write("int7", len(value))
            self.write("bytes", value)
        elif type == "int7int7bytes":
            self.write("int7", len(encode_u29(len(value)))+len(value))
            self.write("int7", len(value))
            self.write("bytes", value)
        else:
            raise TypeError("Unknown type specifier supplied")

    def reset(self, pos=0):
        self.pos = pos

    def crop(self, offset=0):
        self.buffer = self.buffer[:offset]
        self.reset(offset)

    def pack(self, *args, **kwargs):
        raw_data = str(self)
        self.crop()

        if hasattr(self , "_pack"):
            self._pack(*args, **kwargs)
        else:
            return raw_data


        return str(self)

    def unpack(self, *args, **kwargs):
        self.reset()
        if hasattr(self, "_unpack"):
            self._unpack(*args, **kwargs)

    def repack(self):
        msg = type(self)(str(self) or self.pack())
        msg.unpack()

        return msg

    def merge(self, other):
        assert isinstance(other, Message)

        for field in dir(other):
            if field.startswith("f_"):
                setattr(self, field, getattr(other, field))

    def rest(self):
        return self.buffer[self.pos:]

    def available(self):
        return len(self.buffer)-self.pos

    def __len__(self):
        return len(self.buffer)

    def __str__(self):
        return self.buffer

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
        if self.available() > 0:
            result+=" %s  not unpacked: %s\n" % (c, repr(self.rest()))

        return " "+result+" +"

