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
        commit sudoku. Blocks until allowed by server.
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

    def __init__(self, sock_addr):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(sock_addr)
        self.open = True

    def report_event(self, event):
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

