from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

import gi
import signal
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('GLib', '2.0')

from gi.repository import Gtk, GLib, Gdk, Gio
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
from widgets.corner import Corner
from modules.dashboard import Dashboard
from modules.music import MusicPlayer
class Notch(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="notch-box",
        )
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        
        # Pass self to Dashboard so it can access the stack later.
        self.dashboard = Dashboard(notch=self)
        self.active_event_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="active-event-box")
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        self.active_event_box.set_vexpand(True)
        self.active_event_box.set_hexpand(True)
        self.left_corner = Corner("top-right")
        self.left_corner.set_size_request(20, 30)
        self.left_corner.set_valign(Gtk.Align.START)
        self.left_corner.set_vexpand(False)
        self.left_corner.get_style_context().add_class("corner")
        self.append(self.left_corner)
        # Add time label to active event box
        self.time_label = Gtk.Label(label=f"{datetime.datetime.now():%H:%M:%S}")
        self.active_event_box.append(self.time_label)

        # Create a Gtk.Stack and add the dashboard widget as a page
        self.stack = Gtk.Stack(
            name="notch-content",
            transition_type="crossfade",
            transition_duration=100,
        )
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.add_named(self.dashboard, 'dashboard')
        self.append(self.stack)
        self.stack.add_named(self.active_event_box, 'active-event-box')
        self.stack.set_visible_child_name('active-event-box')
        self.right_corner = Corner("top-left")
        self.right_corner.set_size_request(20, 30)
        self.right_corner.set_valign(Gtk.Align.START)
        self.right_corner.set_vexpand(False)
        self.right_corner.get_style_context().add_class("corner")
        self.append(self.right_corner)
        #create a on click event for the active event box
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_active_event_box_click)
        self.active_event_box.add_controller(gesture)
        self.active_event_box.set_receives_default(True)
        self.active_event_box.set_can_focus(True)


    def on_active_event_box_click(self, gesture, n_press, x, y):
        self.stack.add_css_class("dashboard")
        self.dashboard.add_css_class("open")
        self.stack.set_visible_child_name('dashboard')
        self.dashboard.show()
        return True