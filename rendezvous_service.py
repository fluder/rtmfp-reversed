from server import UDPServer
from ether import Ether, ETHER_SERVER
from session import SessionManager
from flow_connection import ConnectionFlow, Connect, Result, SetPeerInfo, KeepAliveSettings
from flow_group import GroupFlow, GroupJoin, BestPeer
from utils import random_bytes
import gevent


class RendezvouzService(object):
    def __init__(self, addr, session_manager=None):
        session_manager = session_manager or SessionManager()
        self.ether = ether = Ether(ETHER_SERVER, session_manager)
        self.server = UDPServer(addr, ether)
        self.peers = []
        self.keys = {}

    def start(self):
        gevent.spawn(self.run)

    def run(self):
        self.server.start()
        print "Waiting new session"
        while True:
            session = self.ether.session_manager.wait()
            gevent.spawn(self._manage_session, session)

    def _manage_session(self, session):
        # new client session
        connection_flow = session.get_flow(2, ConnectionFlow)
        msg = connection_flow.consume()
        assert isinstance(msg, Connect)
        #args: { "code": u'NetConnection.Connect.Success', "description": u'Connection succeeded',
        # "level": u'status', "objectEncoding": 3.0, }
        response = Result(version=1.0,
            args={
                "code": "NetConnection.Connect.Success",
                "description": "Connection succeeded",
                "level": u'status',
                "objectEncoding": 3.0
            })
        connection_flow.produce(response)
        msg = connection_flow.consume()
        assert isinstance(msg, SetPeerInfo)
        print msg.explain(compact=False)
        response = KeepAliveSettings(server=15000, peer=10000)
        connection_flow.produce(response)
        group_flow = session.get_flow(3, GroupFlow)
        msg = group_flow.consume()
        assert isinstance(msg, GroupJoin)
        gevent.sleep(2)
        session.delete_flow(2)
        my_peer_id = session.peer_id
        self.keys[my_peer_id] = session.public_key
        self.peers.append(my_peer_id)
        self.ether.session_manager.peers[my_peer_id] = [[session.addr], session]

        while True:
            gevent.sleep(5)
            for peer_id in self.peers:
                if peer_id == my_peer_id:
                    continue
                response = BestPeer(peer_id=peer_id)
                response.f_handler = 0
                print response.explain(compact=False)
                group_flow.produce(response)
