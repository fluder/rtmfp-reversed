import random
import struct

def random_bytes(size):
    result = ''
    for i in xrange(size):
        byte = random.randint(0,255)
        result+=struct.pack('B', byte)

    return result