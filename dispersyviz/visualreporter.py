"""Low-level interface for clients reporting to a VisualServer.

To use first initialize the link (init_reporter) and then send
events (report_event).
The following events are available:
 - VD_EVT_CONNECT: when joining a community
 - VD_EVT_COMMUNICATION: when two nodes interact
 - VD_CUSTOM_TARGET: when an arbitrary goal is updated
 - VD_EVT_END: when this client wants to exit
"""

import socket


def VD_EVT_CONNECT(myid, community_name):
    """Signal when a community is joined
    """
    return "CON" + str(myid) + "," + community_name


def VD_EVT_COMMUNICATION(fromid, toid, community_name):
    """Signal when communication occurs from one id to
        some other id for some community
    """
    return "COM" + str(fromid) + "," + str(toid) + "," + community_name


def VD_CUSTOM_TARGET(myid, dict_entry, received, target):
    """Signal when an experiment is getting closer to
        its goal
    """
    return "CTM" + str(myid) + "," + dict_entry + "," + str(received) + "," + str(target)


def VD_EVT_END(myid):
    """Signal when a node in the experiment wants to
        exit. Blocks until allowed by server.
    """
    return "END" + str(myid)

singleton_reporter = None


def init_reporter(sock_addr):
    """Define the signal sink socket address
    """
    global singleton_reporter
    if not singleton_reporter:
        singleton_reporter = VisualReporter(sock_addr)


def report_event(event):
    """Report a signal to some observer (if it exists)
    """
    global singleton_reporter
    singleton_reporter.report_event(event)


class VisualReporter:

    """Class to wrap a (sending) socket for communication
        with a VisualServer.
    """

    def __init__(self, sock_addr):
        """Connect a streaming socket to a certain address
        """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(sock_addr)
        self.open = True

    def report_event(self, event):
        """Send a string over the socket connection.
            If the string contains an END event, busy wait
            for the server to send the end confirmation.
            After confirmation, close the socket and return.
        """
        if self.open:
            try:
                self._socket.sendall(event + ";")
                if event.startswith('END'):
                    self.open = False
                    self._socket.recv(8)
                    self._socket.close()
            except socket.error:
                self.open = False
                print "[WARNING] Trying to report to unreachable VisualServer"
