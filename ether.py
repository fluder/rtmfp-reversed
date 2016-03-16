import gevent
import time

from stream import Stream
from ether_message import *
from session import SessionManager


ETHER_SERVER = 0x02
ETHER_CLIENT = 0x01

class Ether(Stream):
    def __init__(self, type=ETHER_SERVER, session_manager=None):
        super(Ether, self).__init__()

        self.type = type
        self.session_manager = session_manager
        self.session_manager.ether = self
        self.session_manager.connect("new_session", self._on_new_session)
        self.session_manager.produce_cb = self._on_session_manager_produce
        self.sessions = {}
        self._pending = set()

        gevent.spawn(self._manage)

    def _manage(self):
        while True:
            data, addr = self.consume()
            print "\n-> data [%s]" % repr(addr)
            ether_message = EtherMessage(data)
            ether_message.unpack_basic()

            # Find session with given session_id
            if ether_message.f_session_id != 0:
                session = self.sessions.get(ether_message.f_session_id, None)
                if not session:
                    print "[ether_debug] Message on invalid session"
                    continue
                key = session.decrypt_key
            else:
                session, key = None, None

            ether_message.unpack(key)
            if not ether_message.f_is_valid:
                print "[ether_debug] Invalid message"
                continue

            print ether_message.explain(c=">e", compact=False)

            for type, payload in ether_message.f_chunks:
                if session:
                    session.addr = addr
                    session.queue.put((type, payload))
                else:
                    self.session_manager.queue.put((type, payload, addr))

    def _on_session_manager_produce(self, manager, data):
        chunks, addr, is_handshake = data

        timestamp = int(time.time()*1000/4) & 0xffff
        print "handshake is "+str(is_handshake)
        ether_message = EtherMessage(session_id=0, timestamp=timestamp, is_handshake=is_handshake,
            direction=FLASH_TO_SERVER if self.type == ETHER_CLIENT else SERVER_TO_FLASH, chunks=chunks)
        ether_message.pack()
        #print ether_message.repack().explain([], c="<e")

        self.produce((str(ether_message), addr))
        print "<- %s\n" % repr(addr)

    def _on_session_produce(self, session, chunks):
        addr = session.addr

        timestamp = int(time.time()*1000/4) & 0xffff
        ether_message = EtherMessage(session_id=session.far_id, timestamp=timestamp, is_handshake=session.in_handshake,
            direction=FLASH_TO_SERVER if self.type == ETHER_CLIENT else SERVER_TO_FLASH, chunks=chunks)
        ether_message.pack(session.encrypt_key)
        print ether_message.repack(session.encrypt_key).explain(c="<e", compact=False)

        self.produce((str(ether_message), addr))
        print "<- %s\n" % repr(addr)

    def _on_new_session(self, manager, session):
        print "[ether_debug] New session registered"
        self.sessions[session.near_id] = session
        session.produce_cb = self._on_session_produce
        session.connect("dead", self._on_dead_session)

    def _on_dead_session(self, session):
        print "[ether_debug] Session unregistered"
        session.produce_cb = lambda data, session: None
        try:
            del self.sessions[session.near_id]
        except KeyError:
            print "[ether_debug] Session %i not found during unregistration" % session.near_id