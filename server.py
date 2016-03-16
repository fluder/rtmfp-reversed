import socket
import gevent
import gevent.socket


class UDPServer(object):
    def __init__(self, addr, stream):
        self.stream = stream

        self.sock = gevent.socket.socket(type=socket.SOCK_DGRAM)
        self.sock.bind(addr)

        self._manage_greenlet = None

    def start(self):
        assert self._manage_greenlet is None

        self.stream.produce_cb = self._produce_cb
        self._manage_greenlet = gevent.spawn(self._manage)

    def stop(self):
        assert self._manage_greenlet is not None

        self._manage_greenlet.kill()
        self.stream.produce_cb = lambda data: None

    def join(self):
        assert  self._manage_greenlet is not None

        self._manage_greenlet.join()

    def run(self):
        self.start()
        self.join()

    def _produce_cb(self, stream, data):
        data, addr = data
        self.sock.sendto(data, addr)

    def _manage(self):
        while True:
            data, addr = self.sock.recvfrom(4096)
            self.stream.queue.put((data, addr))
