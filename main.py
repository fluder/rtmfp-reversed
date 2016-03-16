from server import UDPServer
from ether import *
from mim import SessionMiMServer, FlowMiMServer
from flow_connection import *
from flow_group import *

import sys
import os
import amf

unbuffered = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stdout = unbuffered

#session_manager = SessionManager()
#ether = Ether(ETHER_SERVER, session_manager)
#server = UDPServer(("0.0.0.0", 1935), ether)
#server.start()

#print ether.session_manager.create(("p2p.rtmfp.net", 1935), 0x0a, "rtmfp://p2p.rtmfp.net/7d8e660a6cbf71bab35a0781-c086fb40c6fb")

#session = ether.session_manager.wait()
#print "Session acquired"

#gevent.sleep(5)

#flow = session.get_flow(2, ConnectionFlow)
#print flow
#data = flow.consume()
#print "New data in flow: %s" % repr(data)
#flow.produce("testtesttest")

#server.join()f

from mim import P2PFlowMiMServer
mim = P2PFlowMiMServer()
mim.run()

raw0_ether = Ether(ETHER_CLIENT, SessionManager(raw0=True))
server0 = UDPServer(("0.0.0.0", 2500), raw0_ether)
server0.start()

from  rendezvous_service import RendezvouzService
service = RendezvouzService(("0.0.0.0", 1935))
service.run()

session_manager = SessionManager()
ether = Ether(ETHER_CLIENT, session_manager)
server = UDPServer(("0.0.0.0", 10000), ether)

server.start()
session = ether.session_manager.create(('50.56.33.171', 10002), 0x0a, "rtmfp://p2p.rtmfp.net/7d8e660a6cbf71bab35a0781-c086fb40c6fb")
print "Created session"
gevent.sleep(2)
connection_flow = session.get_flow(2, ConnectionFlow)
msg = Connect(version=1.0, args=amf.Object(**{
    "app": u'7d8e660a6cbf71bab35a0781-c086fb40c6fb',
    "audioCodecs": 3575.0,
    "capabilities": 235.0,
    "flashVer": u'LNX 11,2,202,251',
    "fpad": False,
    "objectEncoding": 3.0,
    "pageUrl": amf.undefined,
    "swfUrl": amf.undefined,
    "tcUrl": u'rtmfp://p2p.rtmfp.net/7d8e660a6cbf71bab35a0781-c086fb40c6fb',
    "videoCodecs": 252.0,
    "videoFunction": 1.0,
    }))
print msg.explain(compact=False)
connection_flow.produce(msg)
response = connection_flow.consume()
assert isinstance(response, Result)
print "Received result"
msg = SetPeerInfo(addrs=["192.168.60.234:10000"], unknown1=0.0)
connection_flow.produce(msg)
response = connection_flow.consume()
assert isinstance(response, KeepAliveSettings)
group_flow = session.get_flow(3, GroupFlow)
msg = GroupJoin(group_id='!\x15\xbcJD\x94\xce\xf5)\xd7\xe8\xb8\xe9\xcc=\x9c\x8e\x1d\xa0vj\xac\xfd{\xcf\x9alV\x84\xeaM>u\xfb')
msg.f_handler = 0
group_flow.produce(msg)
session.delete_flow(2)
response = group_flow.consume()
assert isinstance(response, BestPeer)
print response.explain(compact=False)
gevent.sleep(5)
p2p_session = ether.session_manager.create(('50.56.33.171', 10002), 0x0f, response.f_peer_id)
gevent.sleep(50)
print "P2p session created"