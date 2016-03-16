from server import UDPServer
from ether import *
from session_message import  *
from rendezvous_service import RendezvouzService


class SessionMiMServer(object):
    """
    Session-layer man-in-the-middle server
    """
    def __init__(self):
        self.server_ether = Ether(type=ETHER_SERVER, session_manager=SessionManager(raw=True))
        self.client_ether = Ether(type=ETHER_CLIENT, session_manager=SessionManager(raw=True))

        UDPServer(("0.0.0.0", 1935), self.server_ether).start()
        UDPServer(("0.0.0.0", 10000), self.client_ether).start()

    def run(self):
        self.client_session = self.client_ether.session_manager.create(
            ("p2p.rtmfp.net", 1935), 0x0a, "rtmfp://p2p.rtmfp.net/7d8e660a6cbf71bab35a0781-c086fb40c6fb"
        )
        self.server_session = self.server_ether.session_manager.wait()

        gevent.spawn(self._redirect, self.client_session, self.server_session)
        gevent.spawn(self._redirect, self.server_session, self.client_session)

        gevent.sleep(999999)

    def _redirect(self, consumer, producer):
        while True:
            print "---------------------------------->"
            msg = consumer.consume()
            if producer is self.server_session:
                print '\033[95m%s\033[0m' % msg.explain(compact=False)
            else:
                print '\033[92m%s\033[0m' % msg.explain(compact=False)
            producer.produce(msg)
            print "<----------------------------------"

class FlowMiMServer(object):
    """
    Flow-layer man-in-the-middle server
    """
    def __init__(self):
        self.server_ether = Ether(type=ETHER_SERVER, session_manager=SessionManager())
        self.client_ether = Ether(type=ETHER_CLIENT, session_manager=SessionManager())

        UDPServer(("0.0.0.0", 1935), self.server_ether).start()
        UDPServer(("0.0.0.0", 10000), self.client_ether).start()

        self.hacked = False

    def run(self):
        self.client_session = self.client_ether.session_manager.create(
            ("p2p.rtmfp.net", 1935), 0x0a, "rtmfp://p2p.rtmfp.net/7d8e660a6cbf71bab35a0781-c086fb40c6fb"
        )
        self.server_session = self.server_ether.session_manager.wait()

        self.client_session.connect("new-flow", self._new_flow)
        self.server_session.connect("new-flow", self._new_flow)

        gevent.sleep(999999)

    def _new_flow(self, session, flow):
        print "New flow"
        if session is self.server_session:
            self.client_session.get_flow(flow.id, type(flow))
        else:
            self.server_session.get_flow(flow.id, type(flow))

        gevent.spawn(self._flow_redirect, session, flow)

    def _flow_redirect(self, session, flow):
        while True:
            msg = flow.consume()
            if session is self.server_session:
                print '\033[92m[%i] %s\033[0m' % (flow.id, msg.explain(compact=False))
                self.client_session.get_flow(flow.id, type(flow)).produce(msg)
            else:
                if flow.id == 3 and not self.hacked:
                    # hack
                    self.hacked = True
                    self.client_session.delete_flow(2)
                    self.server_session.delete_flow(2)
                print '\033[95m[%i] %s\033[0m' % (flow.id, msg.explain(compact=False))
                self.server_session.get_flow(flow.id, type(flow)).produce(msg)


class P2PFlowMiMServer(object):
    def __init__(self):
        self.p2p_sm = SessionManager(middle_p2p_addr=["192.168.60.234", 5567])
        self.rendezvouz = RendezvouzService(("0.0.0.0", 1935), self.p2p_sm)


    def run(self):
        self.rendezvouz.start()
        gevent.sleep(15)
        self.ether = Ether(type=ETHER_CLIENT, session_manager=SessionManager(is_server=False, public_key=self.p2p_sm.ether.sessions[1].public_key))
        UDPServer(("0.0.0.0", 5567), self.ether).start()

        # self.p2p_incoming = self.ether.session_manager.wait()
        gevent.sleep(20)
        self.p2p_outgoing = self.ether.session_manager.create(
            self.p2p_sm.p2p[0][0], 0x0f, self.p2p_sm.p2p[0][1]
        )
        self.p2p_outgoing = self.ether.session_manager.create(
            self.p2p_sm.p2p[0][0], 0x0f, self.p2p_sm.p2p[0][1]
        )

        #self.p2p_incoming.connect("new-flow", self._new_flow)
        self.p2p_outgoing.connect("new-flow", self._new_flow)

        gevent.sleep(999999)

    def _new_flow(self, session, flow):
        print "New flow"
        if session is self.p2p_incoming:
            self.p2p_outgoing.get_flow(flow.id, type(flow))
        else:
            self.p2p_incoming.get_flow(flow.id, type(flow))

        gevent.spawn(self._flow_redirect, session, flow)

    def _flow_redirect(self, session, flow):
        while True:
            msg = flow.consume()
            if session is self.p2p_incoming:
                if flow.id == 3 and not self.hacked:
                    # hack
                    self.hacked = True
                    self.p2p_incoming.delete_flow(2)
                    self.p2p_outgoing.delete_flow(2)
                print '\033[92m[%i] %s\033[0m' % (flow.id, msg.explain(compact=False))
                self.p2p_outgoing.get_flow(flow.id, type(flow)).produce(msg)
            else:
                print '\033[95m[%i] %s\033[0m' % (flow.id, msg.explain(compact=False))
                self.p2p_incoming.get_flow(flow.id, type(flow)).produce(msg)

