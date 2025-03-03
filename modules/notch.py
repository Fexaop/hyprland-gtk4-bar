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
        
        # Remove the self_gesture that made the entire notch clickable
        # self_gesture = Gtk.GestureClick()
        # self_gesture.connect("pressed", self.on_active_event_box_click)
        # self.add_controller(self_gesture)
        
        # Keep only the gesture on the active event box (time display)
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
        
        # Replace previous key controller approach with a more aggressive one
        # Add a key event controller to the entire notch
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
        
        # Add a variable to track the previous widget
        self.previous_widget = 'active-event-box'

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
        # Get currently visible widget
        current = self.stack.get_visible_child_name()
        
        # Skip if trying to open the widget that's already open
        if current == widget:
            return
            
        # Save the current widget as previous, but only for notifications
        if widget == 'notification':
            print(f"Saving previous widget: {current}")  # Debug print
            self.previous_widget = current
        
        # First close any currently active widget
        if current == 'dashboard':
            self.stack.remove_css_class("dashboard")
            self.dashboard.remove_css_class("open")
        elif current == 'notification':
            self.stack.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
        
        # Now open the requested widget
        if widget == 'dashboard':
            self.stack.add_css_class("dashboard")
            self.dashboard.add_css_class("open")
        elif widget == 'notification':
            self.stack.add_css_class("notification")
            self.notification_center.notification_view.add_css_class("open")
        
        # Set visible child
        self.stack.set_visible_child_name(widget)
        
        # More aggressive focus handling
        if widget == 'dashboard':
            self.dashboard.grab_focus()
            # Force focus on each child widget too
            for child in self.dashboard:
                if hasattr(child, 'grab_focus'):
                    child.grab_focus()
        elif widget == 'notification':
            self.notification_page.grab_focus()
            self.notification_center.notification_view.grab_focus()
        
        # Also set focus on the parent widget
        self.grab_focus()
        
        # Add a small delay and try focus again (sometimes needed in GTK)
        GLib.timeout_add(50, lambda: self.grab_focus() and False)
        
    def on_active_event_box_click(self, gesture, n_press, x, y):
        """Handle click on the active event box to show dashboard"""
        print("Notch clicked, showing dashboard")  # Debug message
        self.open_notch('dashboard')
        return True
    
    def show_notification(self):
        # Explicitly save the current widget before showing notification
        current = self.stack.get_visible_child_name()
        if current != 'notification':
            print(f"Before notification, saving current: {current}")  # Debug print
            self.previous_widget = current
        self.open_notch('notification')
    
    def collapse_notch(self):
        """Collapse the notch back to original size"""
        # Only collapse if we're not showing the dashboard
        if self.stack.get_visible_child_name() == 'dashboard':
            return False
            
        # Get the current visible widget
        current = self.stack.get_visible_child_name()
        
        print(f"Collapsing from {current}, previous was {self.previous_widget}")  # Debug print
        
        # If we're closing a notification, go back to the previous widget
        if current == 'notification':
            # Remove notification styling
            self.stack.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
            
            # If the previous widget was the dashboard, restore its styling
            if self.previous_widget == 'dashboard':
                self.stack.add_css_class("dashboard")
                self.dashboard.add_css_class("open")
            
            # Switch to the previous widget
            print(f"Restoring to previous widget: {self.previous_widget}")  # Debug print
            self.stack.set_visible_child_name(self.previous_widget)
        else:
            # For non-notification widgets (like dashboard), go back to active-event-box
            self.stack.set_visible_child_name('active-event-box')
        
        # Reset corner heights to normal
        self.left_corner.set_size_request(20, 30)
        self.right_corner.set_size_request(20, 30)
        
        return False  # for GLib.timeout_add

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keypress events, particularly ESC to close the notch"""
        print(f"Key pressed: {keyval}, ESC is {Gdk.KEY_Escape}")  # More detailed debug
        
        # Use explicit numeric value for Escape key as a fallback
        if keyval == Gdk.KEY_Escape or keyval == 65307:  # 65307 is the keyval for Escape
            print("ESC key detected")  # Debug output
            # Get currently visible widget
            current = self.stack.get_visible_child_name()
            print(f"Current widget: {current}")  # Debug output
            
            # If dashboard or notification is open, close it
            if current == 'dashboard':
                print("Closing dashboard")  # Debug output
                self.stack.remove_css_class("dashboard")
                self.dashboard.remove_css_class("open")
                self.stack.set_visible_child_name('active-event-box')
                GLib.timeout_add(10, self.collapse_notch)  # Use shorter timeout
                return True
            elif current == 'notification':
                print("Closing notification")  # Debug output
                # Call collapse_notch directly which will handle returning to previous widget
                self.collapse_notch()
                return True
                
        return False  # Let other handlers process the key

