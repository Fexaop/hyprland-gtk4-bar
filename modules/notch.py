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
from modules.notifications import NotificationCenter

class Notch(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="notch-box",
        )
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)  # Always at top
        
        # Make sure the box receives events and can be focused
        self.set_can_target(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        
        # Track the original size
        self.normal_height = 30  # Default height for the notch
        # Pass self to Dashboard so it can access the stack later.
        self.dashboard = Dashboard(notch=self)
        self.active_event_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="active-event-box")
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        # Set margins and expansion for active_event_box
        self.active_event_box.set_margin_start(10)
        self.active_event_box.set_margin_end(10)
        self.active_event_box.set_margin_top(10)
        self.active_event_box.set_margin_bottom(10)
        self.active_event_box.set_vexpand(False)
        self.active_event_box.set_hexpand(False)
        
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
            transition_type=Gtk.StackTransitionType.OVER_UP,  # Use CROSSFADE for fade effect
            transition_duration=550,  # Set to 0.2s (200ms) for fade transition
        )
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_hhomogeneous(False)  # Allows variable widths
        self.stack.set_vhomogeneous(False)  # Allows variable heights
        self.stack.set_interpolate_size(True)  # Enables smooth size transitions
        
        # Configure dashboard with margins and expansion
        self.dashboard.set_margin_start(10)
        self.dashboard.set_margin_end(10)
        self.dashboard.set_margin_top(10)
        self.dashboard.set_margin_bottom(10)
        self.dashboard.set_vexpand(False)
        self.dashboard.set_hexpand(False)
        
        # Add the various stack pages
        self.stack.add_named(self.dashboard, 'dashboard')
        self.stack.add_named(self.active_event_box, 'active-event-box')
        
        # Initialize the notification center
        self.notification_center = NotificationCenter(self)
        
        # Create a notification stack page
        self.notification_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-page")
        self.notification_page.append(self.notification_center.notification_view)
        # Set margins and expansion for notification_page
        self.notification_page.set_margin_start(10)
        self.notification_page.set_margin_end(10)
        self.notification_page.set_margin_top(10)
        self.notification_page.set_margin_bottom(10)
        self.notification_page.set_vexpand(False)
        self.notification_page.set_hexpand(False)
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
        
        # Gesture on the active event box (time display)
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_active_event_box_click)
        self.active_event_box.add_controller(gesture)
        self.active_event_box.set_receives_default(True)
        self.active_event_box.set_can_focus(True)
        
        # Enhanced keyboard focus handling
        self.set_can_target(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        
        # Make all child widgets focusable too
        self.dashboard.set_can_focus(True)
        self.dashboard.set_focusable(True)
        self.notification_page.set_can_focus(True)
        self.notification_page.set_focusable(True)
        
        # Add key event controller to the entire notch
        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(self.key_controller)
        
        # Also add to each child widget to ensure we catch events
        for widget in [self.dashboard, self.notification_page, self.active_event_box, self.stack]:
            key_controller = Gtk.EventControllerKey.new()
            key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            key_controller.connect("key-pressed", self.on_key_pressed)
            widget.add_controller(key_controller)
        
        # Start time updater
        GLib.timeout_add_seconds(1, self.update_time)
        
        # Add event after initialization to ensure focus
        GLib.timeout_add(100, self.ensure_keyboard_focus)
        
        # Add variable to track the previous widget
        self.previous_widget = 'active-event-box'
        
        # Connect signals for debugging size changes
        self.stack.connect("notify::visible-child", self.on_switch_child)
        self.stack.connect("notify::allocation", self.on_allocation_changed)

    def ensure_keyboard_focus(self):
        """Make sure we have keyboard focus"""
        self.grab_focus()
        return False  # Run once

    def update_time(self):
        """Update the time label every second"""
        self.time_label.set_text(f"{datetime.datetime.now():%H:%M:%S}")
        return True  # Continue calling

    def open_notch(self, widget):
        """
        Opens the specified widget in the notch, closing any currently active widget first.
        
        Parameters:
        widget (str): Widget to open ('dashboard', 'notification', or 'active-event-box')
        """
        current = self.stack.get_visible_child_name()
        if current == widget:
            return
            
        # Apply blur effect for 0.2 seconds on notch open
        self.get_style_context().add_class("blur")
        GLib.timeout_add(150, lambda: self.get_style_context().remove_class("blur") or False)
        
        if widget == 'notification':
            print(f"Saving previous widget: {current}")
            self.previous_widget = current
        
        # Close current widget
        if current == 'dashboard':
            self.stack.remove_css_class("dashboard")
            self.dashboard.remove_css_class("open")
        elif current == 'notification':
            self.stack.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
        
        # Open requested widget
        if widget == 'dashboard':
            self.stack.add_css_class("dashboard")
            self.dashboard.add_css_class("open")
        elif widget == 'notification':
            self.stack.add_css_class("notification")
            self.notification_center.notification_view.add_css_class("open")
        
        self.stack.set_visible_child_name(widget)
        self.stack.queue_resize()  # Force resize after switch
        
        # Focus handling
        if widget == 'dashboard':
            self.dashboard.grab_focus()
            for child in self.dashboard:
                if hasattr(child, 'grab_focus'):
                    child.grab_focus()
        elif widget == 'notification':
            self.notification_page.grab_focus()
            self.notification_center.notification_view.grab_focus()
        
        self.grab_focus()
        GLib.timeout_add(50, lambda: self.grab_focus() and False)

    def on_active_event_box_click(self, gesture, n_press, x, y):
        """Handle click on the active event box to show dashboard"""
        print("Notch clicked, showing dashboard")
        self.open_notch('dashboard')
        return True
    
    def show_notification(self):
        current = self.stack.get_visible_child_name()
        if current != 'notification':
            print(f"Before notification, saving current: {current}")
            self.previous_widget = current
        self.open_notch('notification')
    
    def collapse_notch(self):
        """Collapse the notch back to original size"""
        current = self.stack.get_visible_child_name()
        if current == 'dashboard':
            return False
            
        print(f"Collapsing from {current}, previous was {self.previous_widget}")
        
        if current == 'notification':
            self.stack.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
            if self.previous_widget == 'dashboard':
                self.stack.add_css_class("dashboard")
                self.dashboard.add_css_class("open")
            self.stack.set_visible_child_name(self.previous_widget)
        else:
            self.stack.remove_css_class("dashboard")
            self.stack.remove_css_class("notification")
            self.stack.set_visible_child_name('active-event-box')
        
        self.stack.queue_resize()  # Force resize after collapse
        self.left_corner.set_size_request(20, 30)
        self.right_corner.set_size_request(20, 30)
        return False

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keypress events, particularly ESC to close the notch"""
        print(f"Key pressed: {keyval}, ESC is {Gdk.KEY_Escape}")
        if keyval == Gdk.KEY_Escape or keyval == 65307:
            current = self.stack.get_visible_child_name()
            print(f"Current widget: {current}")
            if current == 'dashboard':
                print("Closing dashboard")
                self.stack.remove_css_class("dashboard")
                self.dashboard.remove_css_class("open")
                self.stack.set_visible_child_name('active-event-box')
                self.stack.queue_resize()  # Force resize
                GLib.timeout_add(10, self.collapse_notch)
                return True
            elif current == 'notification':
                print("Closing notification")
                self.collapse_notch()
                return True
        return False

    def on_switch_child(self, stack, pspec):
        """Debug size changes when visible child switches"""
        visible_child = stack.get_visible_child()
        if visible_child:
            minimum_size, natural_size = visible_child.get_preferred_size()
            min_width = minimum_size.width
            min_height = minimum_size.height
            natural_width = natural_size.width
            natural_height = natural_size.height
            classes = stack.get_css_classes()
            print(f"Visible child: {visible_child.get_name()}, min_size: {min_width}x{min_height}, natural_size: {natural_width}x{natural_height}, Stack classes: {classes}")

    def on_allocation_changed(self, widget, pspec):
        """Debug stack size allocation"""
        allocation = widget.get_allocation()
        print(f"Stack allocated size: {allocation.width}x{allocation.height}")

# CSS remains unchanged as provided
'''
#notch {
    background-color: transparent;
}

#notch-box {
  margin: 10px;
  margin-top: 10px;
  transition: all 0.5s cubic-bezier(0.5, 0.25, 0, 1.25);
}

#notch-content {
  background-color: black;
  min-height: 40px;
  margin-right: -4px;
  margin-left: -4px;
  min-width: 256px;
  border-radius: 0 0 16px 16px;
  transition: all 0.5s cubic-bezier(0.5, 0.25, 0, 1.25);
}

#notch-content.dashboard {
  padding: 16px;
  min-height: 358px;
  min-width: 820px;
  border-radius: 0 0 36px 36px;
}

#notch-content.notification {
  padding: 16px;
  min-height: 45px;
  min-width: 360px;
  border-radius: 0 0 36px 36px;
  opacity: 1;
}

#dashboard {
  opacity: 1;
  margin: 0px;
  transition: all 0.5s cubic-bezier(0.45, 0.25, 0, 1);
}

#dashboard.open {
  opacity: 1;
}
'''