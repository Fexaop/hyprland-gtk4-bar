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
from modules.notification import NotificationCenter

class Notch(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="notch-box",
        )
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)  # Always at top
        
        # Track the original size
        self.normal_height = 30  # Default height for the notch
        # Pass self to Dashboard so it can access the stack later.
        self.dashboard = Dashboard(notch=self)
        self.active_event_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="active-event-box")
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        self.active_event_box.set_vexpand(True)
        self.active_event_box.set_hexpand(True)
        
        # Setup corners with exact sizing
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
        
        # Add the various stack pages
        self.stack.add_named(self.dashboard, 'dashboard')
        self.stack.add_named(self.active_event_box, 'active-event-box')
        
        # Initialize the notification center
        self.notification_center = NotificationCenter(self)
        
        # Create a notification stack page
        self.notification_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-page")
        self.notification_page.append(self.notification_center.notification_view)
        self.stack.add_named(self.notification_page, 'notification')
        
        # Default to showing the active event box
        self.stack.set_visible_child_name('active-event-box')
        self.append(self.stack)
        
        # Right corner with exact sizing
        self.right_corner = Corner("top-left")
        self.right_corner.set_size_request(20, 30)
        self.right_corner.set_valign(Gtk.Align.START)
        self.right_corner.set_vexpand(False)
        self.right_corner.get_style_context().add_class("corner")
        self.append(self.right_corner)
        
        # Create a click event for the active event box
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_active_event_box_click)
        self.active_event_box.add_controller(gesture)
        self.active_event_box.set_receives_default(True)
        self.active_event_box.set_can_focus(True)
        
        # Start time updater
        GLib.timeout_add_seconds(1, self.update_time)

    def update_time(self):
        """Update the time label every second"""
        self.time_label.set_text(f"{datetime.datetime.now():%H:%M:%S}")
        return True  # Continue calling

    def on_active_event_box_click(self, gesture, n_press, x, y):
        """Handle click on the active event box to show dashboard"""
        self.stack.add_css_class("dashboard")
        self.dashboard.add_css_class("open")
        self.stack.set_visible_child_name('dashboard')
        self.dashboard.show()
        return True
    
    def show_notification(self):
        self.stack.add_css_class("notification")
        self.notification_center.notification_view.add_css_class("open")
        self.stack.set_visible_child_name('notification')
        
    def hide_notification(self):
        self.stack.remove_css_class("notification")
        self.notification_center.notification_view.remove_css_class("open")
        self.stack.set_visible_child_name('active-event-box')
        GLib.timeout_add(300, self.collapse_notch)
    
    def collapse_notch(self):
        """Collapse the notch back to original size"""
        # Only collapse if we're not showing the dashboard
        if self.stack.get_visible_child_name() == 'dashboard':
            return False
        
        # Switch back to time display
        self.stack.set_visible_child_name('active-event-box')
        
        # Reset corner heights to normal
        self.left_corner.set_size_request(20, 30)
        self.right_corner.set_size_request(20, 30)

