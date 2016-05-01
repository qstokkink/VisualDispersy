from dispersy.dispersy import Dispersy
from dispersy.community import Community
from dispersy.endpoint import StandaloneEndpoint
from dispersy.exception import CommunityNotFoundException
from dispersy.crypto import ECCrypto
from visualreporter import *

class VisualCommunity(Community):

    def vz_report_target(self, target_name, current, target):
        report_event(VD_CUSTOM_TARGET(self.dispersy.lan_address[1], target_name, current, target))

    def vz_wait_for_experiment_end(self):
        report_event(VD_EVT_END(self.dispersy.lan_address[1]))

class VisualDispersy(Dispersy):

    def vz_init_server_connection(self, port):
        init_reporter(('0.0.0.0', port))

    def __init__(self, endpoint, working_directory, database_filename=u"dispersy.db", crypto=ECCrypto()):
        self.myid = endpoint._port

        # Eavesdrop on the listen server connection accepting loop
        pt_ep_loop = endpoint._loop
        funcType = type(StandaloneEndpoint._loop)
        def epLoopMim(eself):
            self.myid = eself._port # This can change at this point, update it accordingly
            pt_ep_loop()
        endpoint._loop = funcType(epLoopMim, endpoint, StandaloneEndpoint)
        
        # Eavesdrop on the packet delegator
        pt_ep_data_came_in = endpoint.dispersythread_data_came_in
        funcType = type(StandaloneEndpoint.dispersythread_data_came_in)
        def epPacketRcvMim(eself, packets, timestamp, cache=True):
            fakepackets = []
            for sock_addr, data in packets:
                # On normal data, request the other's id so we can log communication
                # On an id request, log our id sending to the id of the requester
                if data.startswith("dpvizidrq"):
                    community_name = data[9:data.index(',')]
                    oid = int(data[data.index(',')+1:])
                    report_event(VD_EVT_COMMUNICATION(self.myid, oid, community_name))
                else:
                    try:
                        if data[22] != chr(248): # identity has no community
                            community_name = type(self.get_community(data[2:22], False, False)).__name__
                            request = "dpvizidrq" + community_name + "," + str(self.myid)
                            try:
                                eself._socket.sendto(request, sock_addr)
                            except socket.error:
                                with eself._sendqueue_lock:
                                    did_have_senqueue = bool(eself._sendqueue)
                                    eself._sendqueue.append((time(), candidate.sock_addr, request))
                                if not did_have_senqueue:
                                    eself._process_sendqueue()
                    except CommunityNotFoundException:
                        pass
                        
                    fakepackets.append((sock_addr, data))
            # Not just DV control messages
            if len(fakepackets) > 0:
                pt_ep_data_came_in(fakepackets, timestamp, cache)
        endpoint.dispersythread_data_came_in = funcType(epPacketRcvMim, endpoint, StandaloneEndpoint)

        # Actually init Dispersy with our modified endpoint
        super(VisualDispersy, self).__init__(endpoint, working_directory, database_filename, crypto)

    # Eavesdrop on all community joiners
    def get_community(self, cid, load=False, auto_load=True):
        community = super(VisualDispersy, self).get_community(cid, load, auto_load)
        if load:
            report_event(VD_EVT_CONNECT(self.myid, type(community).__name__))
        return community

    def attach_community(self, community):
        report_event(VD_EVT_CONNECT(self.myid, type(community).__name__))
        super(VisualDispersy, self).attach_community(community)

    def define_auto_load(self, community_cls, my_member, args=(), kargs=None, load=False):
        if load:
            report_event(VD_EVT_CONNECT(self.myid, type(community_cls).__name__))
        return super(VisualDispersy, self).define_auto_load(community_cls, my_member, args, kargs, load)

    
