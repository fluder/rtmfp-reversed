import dh
import gevent
from stream import Stream
from utils import random_bytes
from session_message import *
from gevent.queue import Queue
from flow import Flow, db as flow_db


class SessionManager(Stream):
    def __init__(self, raw=False, raw0=False, middle_p2p_addr=False, is_server=True, public_key=None):
        super(SessionManager, self).__init__()

        self.raw = raw
        self.raw0 = raw0
        self._session_counter = 1
        self._pending = set()
        self._new = Queue()
        self.peers = {}
        self.middle_p2p_addr = middle_p2p_addr
        self.p2p = []
        self.is_server = is_server
        self.public_key = public_key

        gevent.spawn(self._manage)

    def _manage(self):
        while True:
            type, payload, addr = self.consume()
            session_message = db.get(type, SessionMessage)(payload)
            session_message.unpack()
            session_message.f_type = type

            if self.raw0:
                print ("\033[95m%s\033[0m" % session_message.explain(c=">>m", compact=False))
                continue
            print session_message.explain(c=">>m", compact=False)
            if isinstance(session_message, InitiatorHello):
                if session_message.f_epd_type == 0x0f and self.is_server:
                    # p2p
                    try:
                        addrs, peer_session = self.peers[session_message.f_epd]
                    except KeyError:
                        print "[session_manager_debug] PeerID not found"
                        continue

                    response = ForwardedInitialHello(
                        epd_type=session_message.f_epd_type,
                        epd=session_message.f_epd,
                        tag=session_message.f_tag,
                        addr=addrs[0],
                        addr_is_public=True
                    )
                    #print response.repack().explain(c="<<m", compact=False)
                    peer_session.produce(response)
                    #self.produce((( (response.id, response.pack()), ), addrs[0], False))
                    if self.middle_p2p_addr:
                        self.p2p.append((addrs[0], session_message.f_epd))
                        addrs = [self.middle_p2p_addr]
                    response = ForwardedHelloResponse(
                        tag_echo=session_message.f_tag,
                        addrs=[(True, addrs[0])]
                    )
                    print response.repack().explain(c="<<m", compact=False)
                    self.produce((( (response.id, response.pack()), ), addr, True))
                else:
                    response = ResponderHello(tag_echo=session_message.f_tag, cookie=addr[0], certificate=random_bytes(64))
                    if session_message.f_epd_type == 0x0f:
                        response.f_certificate2 = self.public_key
                    print response.repack().explain(c="<<m", compact=False)
                    self.produce((( (response.id, response.pack()), ), addr, True))
            elif isinstance(session_message, InitiatorInitialKeying):
                if session_message.f_cookie_echo != addr[0]:
                    continue

                session = IncomingSession(addr=addr, near_id=self._session_counter, raw=self.raw)
                self.emit("new_session", session)
                self._new.put(session)
                session.queue.put((type, payload))
                self._session_counter+=1
            else:
                for session in self._pending:
                    session.queue.put((type, payload))

    def _on_session_produce(self, session, chunks):
        self.produce((chunks, session.addr, True))

    def _on_session_initialized(self, session):
        try:
            self._pending.remove(session)
        except ValueError:
            print "[session_manager_debug] Received initialized event from session not belongs to this manager"

        self.emit("new_session", session)

    def create(self, addr, epd_type, epd):
        session = OutgoingSession(epd_type=epd_type, epd=epd, addr=addr, near_id=self._session_counter, raw=self.raw)
        session.connect("initialized", self._on_session_initialized)
        session.produce_cb = self._on_session_produce
        self._session_counter+=1
        self._pending.add(session)

        return session

    def wait(self):
        return self._new.get()


class Session(Stream):
    def __init__(self, **kwargs):
        super(Session, self).__init__()

        self.raw = False
        self.near_id = 0
        self.far_id = 0
        self.encrypt_key = None
        self.decrypt_key = None
        self.in_handshake = True

        self.addr = None

        self.flows = {}
        self.active_flows = {}
        self.last_data_msg = None
        self.peer_id = None
        self.public_key = None

        for key, value in kwargs.items():
            setattr(self, key, value)

        gevent.spawn(self._manage)

    def consume(self, filter=None):
        while True:
            type, payload = super(Session, self).consume()
            message = db.get(type, SessionMessage)(payload)
            message.unpack()
            message.f_type = type
            message.id = type

            if filter is None or filter(message):
                print message.explain(c=">>s", compact=False)
                return message

    def produce(self, data):
        if not type(data) in (list, tuple):
            data = [data]

        chunks = []
        for message in data:
            chunks.append((message.id, message.pack()))
            print message.repack().explain(c="<<s", compact=False)

        super(Session, self).produce(chunks)

    def _manage(self):
        self._initialize()
        self.in_handshake = False
        if self.raw:
            return

        while True:
            message = self.consume()
            if isinstance(message, KeepAliveRequest):
                print "[session_debug] Keep alive request received"
                self.produce(KeepAliveResponse())
            elif isinstance(message, ClientFailed):
                print "[session_debug] Client failed request received"
                self.produce(SessionDied())
                self.emit("dead")
            elif type(message) in (NormalUserData, NextUserData):
                # New data in flow
                if isinstance(message, NextUserData):
                    if not self.last_data_msg:
                        print "[session_debug] Received next data msg with last_data_msg == None"
                        continue
                    message.f_seq = self.last_data_msg.f_seq+1
                    message.f_delta = self.last_data_msg.f_delta+1
                    message.f_flow_id = self.last_data_msg.f_flow_id
                self.last_data_msg = message

                flow = self.get_flow(message.f_flow_id, flow_db.get(message.f_signature, Flow))

                flow.handle(message)
            elif isinstance(message, Ack):
                try:
                    flow = self.flows[message.f_flow_id]
                except KeyError:
                    print "[flow_debug] Ack on unknown flow: %s" % message.f_flow_id
                else:
                    flow.handle(message)

    def _on_flow_produce(self, flow, msg):
        self.produce(msg)

    def _flow_activate(self, flow):
        self.active_flows[flow.id] = flow

        base_flow = self.active_flows.values()[0]
        for flow in self.flows.values():
            flow.base_flow = base_flow

    def get_flow(self, id, type):
        try:
            flow = self.flows[id]
        except KeyError:
            self.flows[id] = flow = type(id)
            if self.active_flows:
                flow.base_flow = self.active_flows.values()[0] if self.flows else None
            flow.produce_cb = self._on_flow_produce
            flow.connect("activate", self._flow_activate)
            self.emit("new-flow", flow)

        return flow

    def delete_flow(self, id):
        del self.flows[id]
        del self.active_flows[id]

        base_flow = self.active_flows.values()[0]
        for flow in self.flows.values():
            flow.base_flow = base_flow


class IncomingSession(Session):
    def _initialize(self):
        keying_msg = self.consume(lambda message: isinstance(message, InitiatorInitialKeying))
        self.peer_id = keying_msg.peer_id
        print "[session_debug] Keying message received"
        self.far_id = keying_msg.f_session_id

        _dh = dh.generate_dh()
        self.public_key = _dh["pub"]
        response = ResponderInitialKeying(session_id=self.near_id, public_key=_dh["pub"])

        shared_key = dh.compute_key(_dh, keying_msg.f_public_key)
        encrypt_key, decrypt_key = dh.compute_keys(shared_key, response.nonce, keying_msg.nonce)

        self.decrypt_key = decrypt_key
        self.produce(response)
        self.encrypt_key = encrypt_key

        self.emit("initialized")
        print "[session_debug] Incoming session initialized"


class OutgoingSession(Session):
    def __init__(self, epd_type=None, epd=None, **kwargs):
        super(OutgoingSession, self).__init__(**kwargs)

        self.epd_type = epd_type
        self.epd = epd

    def _initialize(self):
        tag = random_bytes(16)

        for i in xrange(10): # Redirection handling
            print "Sending initiator hello"
            self.produce(InitiatorHello(epd_type=self.epd_type, epd=self.epd, tag=tag))
            print "Sent initiator hello"
            hello_msg = self.consume(
                lambda msg: (isinstance(msg, ForwardedHelloResponse) or isinstance(msg, ResponderHello))
                and msg.f_tag_echo == tag
            )

            if isinstance(hello_msg, ForwardedHelloResponse):
                print "[session_debug] Forward hello received"
                self.addr = hello_msg.f_addrs[1][1]
                continue
            else:
                break
        else:
            print "[session_debug] Max redirection count reached"
            raise Exception("Redirection error")

        self.emit("initialized")
        _dh = dh.generate_dh()
        self.public_key = _dh["pub"]
        my_keying = InitiatorInitialKeying(cookie_echo=hello_msg.f_cookie, session_id=self.near_id,
            public_key=_dh["pub"], certificate=random_bytes(64))
        self.peer_id = my_keying.peer_id

        self.produce(my_keying)
        keying_msg = self.consume(lambda msg: isinstance(msg, ResponderInitialKeying))
        self.far_id = keying_msg.f_session_id

        shared_key = dh.compute_key(_dh, keying_msg.f_public_key)

        self.decrypt_key, self.encrypt_key = dh.compute_keys(shared_key, keying_msg.nonce, my_keying.nonce)
