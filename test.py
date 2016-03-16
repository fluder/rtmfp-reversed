
#: The maximum that can be represented by a signed 29 bit integer.
MAX_29B_INT = 0x0FFFFFFF

#: The minimum that can be represented by a signed 29 bit integer.
MIN_29B_INT = -0x10000000

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


print repr(encode_u29(1))
print repr(encode_u29(255))
print repr(encode_u29(257))
print repr(encode_u29(65536))
print repr(encode_u29(655360))
print repr(encode_u29(6553600))\


import gevent.event
while True:
    co, msg = wait_something("consume", flows+sessions)
    endpoint_session = self.seessions[flow.session]
    endpoint_flow = endpoint_session.get_flow(flow.id, type(flow))
    endpoint_flow.produce(msg)