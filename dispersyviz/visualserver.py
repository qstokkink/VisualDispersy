"""Server object handling communication with clients
and displaying graphs.
"""

import socket
import threading
import string
import time
import math
import sys
from graph_tool.all import *

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning


class Visualizer:

    """Object to manage graph windows and their contents.
    """

    def _ring_layout(self, graph, radius=10.0):
        """Layout the nodes evenly over a left half of
            a circle and a right half, with a separation
            between the two halves.
        """
        totalvs = graph.num_vertices()
        pmap = graph.new_vertex_property("vector<float>")
        if totalvs == 0:
            return pmap
        if totalvs == 1:
            for v in graph.vertices():
                pmap[v] = [1.0, 1.0]
        else:
            num = 0
            for v in graph.vertices():
                rads = 2.0 * math.pi / totalvs * num
                num = num + 1
                x = radius * math.cos(rads)
                y = radius * math.sin(rads)
                pmap[v] = [x + 0.2 * (radius if x > 0 else -radius), y]
        return pmap

    def __init__(self, closecallback):
        """Initialize fields.
        """
        self.graphs = {}
            # Graph per community name {str/community_name:Graph}
        self.vertices = {}
            # Vertex per community name for a node identifier
            # {str/node_id:{str/community_name:Vertex}}
        self.vlabels = {}
            # Vertex labels per community name (formatted vtargets)
            # {str/community_name:PropertyMap}
        self.vcolors = {}
            # Vertex colors per community name {str/community_name:PropertyMap}
        self.vtargets = {}
            # Vertex targets per node identifier
            # {str/node_id:{str/target_name:str/value}}
        self.windows = {}
            # Window object per community name {str/community_name:GraphWindow}
        self.edgequeue = {}
            # Edge buffer per community name
            # {str/community_name:[(int/from,int/to)]}
        self.glock = threading.RLock()
                                     # Reentrant lock for modifying graph data
        self.elocks = {}
            # List of reentrant locks for modifying edges in different graphs
        self.closecallback = closecallback  # Callback for when we want to close
        self.alive = True                   # Experiment is running

    def __killall(self, widget, event, data=None):
        """Callback for when the user force exits.
        """
        self.alive = False
        for window in self.windows:
            self.windows[window].destroy()
        self.closecallback()
        Gtk.main_quit()
        reactor.callFromThread(reactor.stop)
        print "GUI Elements destroyed"

    def assert_community(self, name):
        """Make sure we own a graph, window, and vertex property maps for some community name.
        """
        if name not in self.graphs:
            self.glock.acquire()
            self.elocks[name] = threading.RLock()
            self.edgequeue[name] = []
            self.graphs[name] = Graph()
            self.vlabels[name] = self.graphs[name].new_vp("string")
            self.vcolors[name] = self.graphs[name].new_vp("vector<float>")
            self.glock.release()

    def assert_node(self, pid):
        """Make sure a node exists in the graphs.
        """
        # Check if in all graphs
        if not str(pid) in self.vertices:
            self.vertices[str(pid)] = {}
            self.set_target_value(str(pid), "id", str(pid))
        self.glock.acquire()
        for name in self.graphs:
            if not name in self.vertices[str(pid)]:
                self.vertices[str(pid)][name] = self.graphs[name].add_vertex()
                self.format_node_label(str(pid), name)
        self.glock.release()

    def format_node_label(self, pid, community=None):
        """Take the current targets and generate a node label.
            Possibly for all communities.
        """
        label = ""
        for target_name, value in self.vtargets[str(pid)].iteritems():
            label = label + target_name + ": " + value + ", "
        label = label[:-2]
        if community:
            self.set_node_text(community, str(pid), label)
        else:
            [self.format_node_label(pid, comm) for comm in self.graphs]

    def set_node_text(self, community, pid, text):
        """Set the node label for a certain community.
        """
        self.vlabels[community][self.vertices[str(pid)][community]] = text

    def set_node_color(self, community, pid, color):
        """Set the node color for a certain community.
        """
        self.vcolors[community][self.vertices[str(pid)][community]] = color

    def set_target_value(self, pid, target, value):
        """Set a certain target value for some node.
        """
        self.glock.acquire()
        if not str(pid) in self.vtargets:
            self.vtargets[str(pid)] = {}
        self.vtargets[str(pid)][target] = value
        self.glock.release()

    def draw_communication(self, fromid, toid, community):
        """Queue drawing an edge in a certain community.
        """
        self.elocks[community].acquire()
        fv = int(self.vertices[str(fromid)][community])
        tv = int(self.vertices[str(toid)][community])
        self.edgequeue[community].append((fv, tv))
        self.elocks[community].release()

    def draw_node_finish(self, pid, pct=1.0):
        """Color a node for a certain percentage [0.0 ~ 1.0]:[red -> green].
        """
        self.glock.acquire()
        for name in self.graphs:
            self.set_node_color(
                name,
                str(pid),
                [(1 - pct) * 0.640625,
                 pct * 0.640625,
                 0,
                 0.9])
        self.glock.release()

    def update_view(self):
        """Redraw callback.
        """
        # Are we open for business or
        # still initializing?
        if not Gtk.main_level():
            return
        # Deep copy all current graphs
        gvs = {}
        self.glock.acquire()
        for name in self.graphs:
            gvs[name] = self.graphs[name].copy()
        self.glock.release()
        # Make sure a window for each graph exists
        for name in gvs:
            if not name in self.windows:
                window = GraphWindow(
                    gvs[name],
                    self._ring_layout(gvs[name]),
                    (800,
                     400),
                    fit_area=0.95)
                window.graph.handler_block_by_func(
                    window.graph.motion_notify_event)
                window.graph.handler_block_by_func(
                    window.graph.button_press_event)
                window.graph.handler_block_by_func(
                    window.graph.button_release_event)
                window.graph.handler_block_by_func(window.graph.scroll_event)
                window.graph.handler_block_by_func(
                    window.graph.key_press_event)
                window.graph.handler_block_by_func(
                    window.graph.key_release_event)
                window.connect("delete_event", self.__killall)
                window.set_title(name)
                window.show_all()
                self.windows[name] = window
            gw = self.windows[name].graph

            # Regen GraphWidget contents
            gw.g = gvs[name]
            gw.pos = self._ring_layout(gvs[name])
            gw.vprops["text"] = gvs[name].new_vp("string")
            gw.vprops["fill_color"] = gw.g.own_property(self.vcolors[name])
            gw.vprops["text_position"] = 0
            gw.vprops["size"] = 10
            gw.selected = gvs[name].new_vertex_property("bool", False)
            gw.highlight = gvs[name].new_vertex_property("bool", False)
            gw.sel_edge_filt = gvs[name].new_edge_property("bool", False)
            gw.fit_to_window()
            gw.vprops["text"] = gw.g.own_property(self.vlabels[name])

            # Insert edges
            self.elocks[name].acquire()
            gvs[name].add_edge_list(self.edgequeue[name])
            self.edgequeue[name] = []
            self.elocks[name].release()
            gw.regenerate_surface()
            gw.queue_draw()
        return self.alive


class VisualServer:

    """Object to handle client communication and forward it
        to the graph window handler (Visualizer).
    """

    def __init__(self):
        """Initialize all of our fields
        """
        self.endlist = []
            # List of ids which want to end
        self.allids = []
            # List of ids we have encountered
        self.isopen = False                         # Experiment is done or forced exited
        self.visualizer = Visualizer(self.close)    # Visualizer object

    def open(self, port):
        """Open our server socket on a certain port
        """
        self.isopen = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.bind(('0.0.0.0', port))
        self._socket.listen(4)
        reactor.callInThread(self.run)

    def run(self):
        """Accept clients as quickly as possible and handle
            their further communication in a thread.
        """
        while self.isopen:
            try:
                conn, addr = self._socket.accept()
                conn.settimeout(5.0)    # Stay responsive for clean exits
                reactor.callInThread(self.client, conn, addr)
            except socket.error:    # Timeout, check if alive and keep going
                pass

    def client(self, connection, address):
        """Handle a single client.
            Delegate input to the proper handler functions.
        """
        ended = False
        while self.isopen and (not ended):
            data = None
            try:
                data = connection.recv(1024)
            except socket.error:
                continue
            if not data:
                break
            for gdata in string.split(data, ';'):
                if not gdata:
                    break
                content = string.split(gdata[3:], ',')
                if gdata.startswith('CON'):
                    self.handle_connect(*content)
                elif gdata.startswith('COM'):
                    self.handle_communication(*content)
                elif gdata.startswith('CTM'):
                    self.handle_custom_target(*content)
                elif gdata.startswith('END'):
                    self.handle_end(*content)
                    connection.sendall('OK')
                    Gtk.main_quit()
                    reactor.callFromThread(reactor.stop)
                    self.close()
                    ended = True
                    break
        connection.close()

    def close(self):
        """Close our socket.
        """
        self.isopen = False
        self._socket.close()

    def assert_id(self, pid):
        """Make sure an identifier is registered.
        """
        self.visualizer.assert_node(str(pid))
        if str(pid) not in self.allids:
            self.allids.append(str(pid))

    def handle_connect(self, pid, community_name):
        """Add this identifier to the graph of a certain community.
        """
        if community_name == "ABCMeta":
            return
        self.visualizer.assert_community(community_name)
        self.assert_id(pid)

    def handle_communication(self, fromid, toid, community_name):
        """Draw communication between two identifiers.
        """
        if community_name == "ABCMeta":
            return
        self.assert_id(fromid)
        self.assert_id(toid)
        self.visualizer.draw_communication(fromid, toid, community_name)

    def handle_custom_target(self, pid, dict_entry, received, target):
        """Set some value of a custom target.
        """
        self.assert_id(pid)
        self.visualizer.set_target_value(
            str(pid),
            dict_entry,
            str(received) + "/" + str(target))
        self.visualizer.format_node_label(str(pid))
        self.visualizer.draw_node_finish(
            str(pid),
            float(received) / float(target))

    def handle_end(self, pid):
        """Signal some identifier wants to exit and wait for the experiment to end.
        """
        self.endlist.append(str(pid))
        while set(self.endlist) != set(self.allids):
            time.sleep(4.0)

if __name__ == "__main__":
    server = VisualServer()
    if len(sys.argv) > 1:
        server.open(int(sys.argv[1]))
    else:
        server.open(54917)
    print "ONLINE"
    GObject.timeout_add(500, server.visualizer.update_view)
    reactor.callLater(0.0, Gtk.main)
    reactor.run()
