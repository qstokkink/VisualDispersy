"""Graphical User Interface for controlling Visual Dispersy classes.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import re
import os
import sys
import time
import glob
import inspect
import traceback
import subprocess


class MainWindow(Gtk.Window):

    """The VisualDispersy Window object
    """

    def __init__(self):
        """Initialize all of the components in the window.
        """
        Gtk.Window.__init__(self, title="DispersyViz")
        self.set_border_width(10)
        self.set_default_size(300, 500)

        # Inits
        self.test_processes = []    # Maintain a list of all running processes
        self.numpeers = '3'         # The amount of peers/nodes in the experiment

        # GUI stuff
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        self.add(grid)

        self.liststore = Gtk.ListStore(str)
        for file in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments", "*.py")):
            name = os.path.splitext(os.path.basename(file))[0]
            self.liststore.append((name,))

        self.treeview = Gtk.TreeView(self.liststore)
        self.treeview.append_column(
            Gtk.TreeViewColumn("Found classes:",
                               Gtk.CellRendererText(),
                               text=0))
        self.treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.add(self.treeview)

        grid.attach(scrollable, 0, 0, 2, 10)

        numpeers_entry = Gtk.Entry()
        numpeers_entry.set_text(self.numpeers)
        numpeers_entry.connect("changed", self._correct_numpeers_input_to_int)

        self.nummessages_entry = Gtk.Entry()
        self.nummessages_entry.set_text('1')

        numpeers_label = Gtk.Label("Number of peers:")
        numpeers_label.set_justify(Gtk.Justification.LEFT)
        numpeers_label.set_halign(Gtk.Align.START)
        nummessages_label = Gtk.Label("Number of messages per peer:")
        nummessages_label.set_justify(Gtk.Justification.LEFT)
        nummessages_label.set_halign(Gtk.Align.START)

        grid.attach_next_to(
            numpeers_label,
            scrollable,
            Gtk.PositionType.BOTTOM,
            2,
            1)
        grid.attach_next_to(
            numpeers_entry,
            numpeers_label,
            Gtk.PositionType.BOTTOM,
            1,
            1)
        grid.attach_next_to(
            nummessages_label,
            numpeers_entry,
            Gtk.PositionType.BOTTOM,
            2,
            1)
        grid.attach_next_to(
            self.nummessages_entry,
            nummessages_label,
            Gtk.PositionType.BOTTOM,
            2,
            1)

        run_button = Gtk.Button(label="Run")
        run_button.connect("clicked", self.on_run)

        grid.attach_next_to(
            run_button,
            self.nummessages_entry,
            Gtk.PositionType.BOTTOM,
            1,
            1)

    def _correct_numpeers_input_to_int(self, widget, *args):
        """Absolutely do not allow the amount of peers to be
            less than three, on input. Graph-tool starts
            segfaulting and misbehaving if this is allowed.
        """
        trimmed = widget.get_text().strip()
        # If there is input here
        if trimmed:
            onlyd = re.sub(r'[^\d]', '', trimmed)
            try:
                if int(onlyd) < 3:
                    onlyd = '3'
            except ValueError:
                pass
            widget.set_text(onlyd)
            self.numpeers = onlyd

    def _validate_nummessages_script(self):
        """ Validate the user script by running it for all peer ids.
            Immediately determine the total amount of messages as well.

            Returns strings (pythonscript, totalmessages) if successful, None otherwise
        """
        totalmsg = 0
        uscript = self.nummessages_entry.get_text()
        for i in range(1, int(self.numpeers) + 1):
            try:
                msgs = eval(
                    self.nummessages_entry.get_text(),
                    {},
                    {'peerid': i})
                totalmsg = totalmsg + msgs
            except:
                return None
        return (uscript, str(totalmsg))

    def _blocking_dialog(self, title, message_type, text):
        """Generic dialog with title, type and text
        """
        dialog = Gtk.MessageDialog(self,
                                   Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   message_type,
                                   Gtk.ButtonsType.CLOSE,
                                   text)
        dialog.set_title(title)
        self.set_sensitive(False)
        dialog.run()
        dialog.destroy()
        self.set_sensitive(True)

    def on_run(self, widget):
        """Validate input when the run button is pressed.
            Disables the main window while an experiment is in progress.

            Validates:
                1. The message count is a valid python expression
                2. The selected experiment doesn't contain static errors
                3. The selected experiment has a proper main method
                4. The VisualServer gets launched correctly
                5. (After exit) all of the processes are terminated
        """
        selection = self.treeview.get_selection().get_selected()
        if selection[1]:
            self.set_sensitive(False)
            name = self.liststore[selection[1]][0]

            # Grab the user input
            uinput = self._validate_nummessages_script()
            if not uinput:
                self._blocking_dialog(
                    "ERROR",
                    Gtk.MessageType.ERROR,
                    "Your number of messages definition is not a valid number or python line.")
                return
            nummessages, totalmessages = uinput

            # (Try) Import the selected file
            sys.path.insert(
                0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments"))
            module = None
            try:
                module = __import__(name)
            except:
                if sys.exc_info()[2]:
                    # TODO Remove our own statement from this traceback, user
                    # will have no idea what __import__(name) means
                    self._blocking_dialog(
                        "ERROR", Gtk.MessageType.ERROR, "Import of %s.py failed.\n\n%s" %
                        (name, traceback.format_exc(sys.exc_info()[2])))
                else:
                    self._blocking_dialog(
                        "ERROR", Gtk.MessageType.ERROR, "Import of %s.py failed with error:\n\n%s: %s" %
                        (name, sys.exc_info()[0], sys.exc_info()[1]))
                return
            sys.path.pop(0)

            # Find a main function
            if not "main" in [str(member) for member in dir(module)]:
                self._blocking_dialog(
                    "ERROR",
                    Gtk.MessageType.ERROR,
                    "Could not find a main() function in %s.py." % (name))
                return

            main_function = getattr(module, "main")

            # Make sure the main function accepts our arguments
            if len(inspect.getargspec(main_function)[0]) != 5:
                self._blocking_dialog(
                    "ERROR",
                    Gtk.MessageType.ERROR,
                    "The main() function of %s.py needs to accept 4 arguments (peerid, total peers, starting messages, total messages, visual dispersy server port)." % (name))
                return

            # Wait for server to open without error
            p_vs_port = 54917
            p_visualserver = None
            # Retry 3 times with ports [54917->54919]
            tries_left = 3
            while tries_left > 0:
                p_visualserver = subprocess.Popen(
                    ['python',
                     '-u',
                     'dispersyviz/visualserver.py',
                     str(p_vs_port)],
                    cwd=os.path.join(
                        os.path.dirname(os.path.abspath(__file__))),
                    stdout=subprocess.PIPE,
                    bufsize=1)
                # Wait for console output or unplanned termination
                while (not p_visualserver.stdout.readline()) and (not p_visualserver.poll()):
                    time.sleep(0.5)
                if p_visualserver.returncode:  # None means not terminated (running fine)
                    p_vs_port = p_vs_port + 1
                    tries_left = tries_left - 1
                else:
                    break
            if p_visualserver.returncode:
                self._blocking_dialog(
                    "ERROR",
                    Gtk.MessageType.ERROR,
                    "Well this is embarrassing. The VisualServer object crashed before the experiment even began. Contact a programmer.")
                return

            # Launch processes once server has started
            children = [subprocess.Popen(
                        ['python', '-c', "import os,sys;sys.path.insert(0, '%s');peerid=%s;nummessages=%s;numpeers=%s;totalmessages=%s;getattr(__import__('%s'), 'main')(peerid,numpeers,nummessages,totalmessages,%s)" %
                         (os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiments"), str(peerid), nummessages, self.numpeers, totalmessages, name, str(p_vs_port))], cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)))) for peerid in range(1, int(self.numpeers) + 1)]

            self._blocking_dialog(
                "RUNNING EXPERIMENT",
                Gtk.MessageType.INFO,
                "Busy conducting experiment. Close this window to terminate all running processes.")

            # Clean up processes
            if not p_visualserver.poll():
                try:
                    p_visualserver.kill()
                except OSError:
                    print "Unable to kill process %d" % (p_visualserver.pid)
            for child in children:
                if not child.poll():
                    try:
                        child.kill()
                    except OSError:
                        print "Unable to kill process %d" % (p_visualserver.pid)

        else:
            self._blocking_dialog(
                "ERROR",
                Gtk.MessageType.ERROR,
                "Are you trying to be clever?\nYou didn't select any class to run, poopieface.")

# Outside of a __main__ check to avoid being imported
win = MainWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()
