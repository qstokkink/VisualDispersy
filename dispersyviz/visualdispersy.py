"""Class for hooking and overriding Dispersy classes
(Dispersy and Community) to automatically report events
through the visualreporter class.

"""

from dispersy.dispersy import Dispersy
from dispersy.community import Community
from dispersy.endpoint import StandaloneEndpoint
from dispersy.exception import CommunityNotFoundException
from dispersy.crypto import ECCrypto
from .visualreporter import *


class VisualCommunity(Community):

    """Community object to inherit from when creating custom communities.
    """

    def vz_report_target(self, target_name, current, target):
        """Report to the VisualServer that some target has changed
            value.
        """
        report_event(
            VD_CUSTOM_TARGET(self.dispersy.lan_address[1],
                             target_name,
                             current,
                             target))

    def vz_wait_for_experiment_end(self):
        """Report to the VisualServer that this community wants
            to exit out of the experiment.
            Note that this method BLOCKS until the server allows
            the exit.
        """
        report_event(VD_EVT_END(self.dispersy.lan_address[1]))


class VisualDispersy(Dispersy):

    """Dispersy object to initialize instead of normal Dispersy.
    """

    def vz_init_server_connection(self, port):
        """Initialize the connection to a VisualServer.
            This is always on localhost, so it doesn't require
            a server ip. This would have to change to
            support remote VisualServers.
        """
        init_reporter(('0.0.0.0', port))

    def __init__(
        self,
        endpoint,
     working_directory,
     database_filename=u"dispersy.db",
     crypto=ECCrypto()):
        """Provide hooks into the endpoint, otherwise equal to
            the normal Dispersy() constructor.

            Hooks into:
                - Endpoint socket data loop: to establish local port (/peer id)
                - Endpoint packet handler: to log data between peer ids
        """
        self.myid = endpoint._port

        # Eavesdrop on the listen server connection accepting loop
        pt_ep_loop = endpoint._loop
        funcType = type(StandaloneEndpoint._loop)

        def epLoopMim(eself):
            self.myid = eself._port  # This can change at this point, update it accordingly
            pt_ep_loop()
        endpoint._loop = funcType(epLoopMim, endpoint, StandaloneEndpoint)

        # Eavesdrop on the packet delegator
        pt_ep_data_came_in = endpoint.dispersythread_data_came_in
        funcType = type(StandaloneEndpoint.dispersythread_data_came_in)

        def epPacketRcvMim(eself, packets, timestamp, cache=True):
            fakepackets = []
            for sock_addr, data in packets:
                if data.startswith("dpvizidrq"):
                    # On an id request, log our id sending to the id of the
                    # requester
                    community_name = data[9:data.index(',')]
                    oid = int(data[data.index(',') + 1:])
                    report_event(
                        VD_EVT_COMMUNICATION(
                            self.myid,
                            oid,
                            community_name))
                else:
                    # On normal data, request the other's id so we can log
                    # communication
                    try:
                        if data[22] != chr(248):  # dispersy-identity has no community
                            community_name = type(
                                self.get_community(data[2:22],
                                                   False,
                                                   False)).__name__
                            request = "dpvizidrq" + \
                                community_name + "," + str(self.myid)
                            try:
                                eself._socket.sendto(request, sock_addr)
                            except socket.error:
                                with eself._sendqueue_lock:
                                    did_have_senqueue = bool(eself._sendqueue)
                                    eself._sendqueue.append(
                                        (time(), candidate.sock_addr, request))
                                if not did_have_senqueue:
                                    eself._process_sendqueue()
                    except CommunityNotFoundException:
                        pass  # We have discovered external communities, ignore these

                    fakepackets.append((sock_addr, data))
            # If the incoming packets are more than VisualDispersy id requests
            # forward them to the actual Dispersy object.
            if len(fakepackets) > 0:
                pt_ep_data_came_in(fakepackets, timestamp, cache)
        endpoint.dispersythread_data_came_in = funcType(
            epPacketRcvMim, endpoint, StandaloneEndpoint)

        # Actually init Dispersy with our modified endpoint
        super(
            VisualDispersy,
            self).__init__(
                endpoint,
                working_directory,
         database_filename,
         crypto)

    # Eavesdrop on all community joiners
    def get_community(self, cid, load=False, auto_load=True):
        """Overwritten to determine community join events
        """
        community = super(
            VisualDispersy,
            self).get_community(
                cid,
                load,
         auto_load)
        if load:
            report_event(VD_EVT_CONNECT(self.myid, type(community).__name__))
        return community

    def attach_community(self, community):
        """Overwritten to determine community join events
        """
        report_event(VD_EVT_CONNECT(self.myid, type(community).__name__))
        super(VisualDispersy, self).attach_community(community)

    def define_auto_load(
        self,
        community_cls,
     my_member,
     args=(),
     kargs=None,
     load=False):
        """Overwritten to determine community join events
        """
        if load:
            report_event(
                VD_EVT_CONNECT(self.myid,
                               type(community_cls).__name__))
        return super(VisualDispersy, self).define_auto_load(community_cls, my_member, args, kargs, load)
