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
from modules.dashboard import Dashboard
from modules.music import MusicPlayer
from modules.notifications import NotificationCenter

class Notch(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(name="notch-box")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)  # Always at top
        
        # Make sure the box receives events and can be focused
        self.set_can_target(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        
        # Track the original size
        self.normal_height = 30  # Default height for the notch
        
        # Pass self to Dashboard
        self.dashboard = Dashboard(notch=self)
        self.active_event_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="active-event-box")
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        self.active_event_box.set_margin_start(10)
        self.active_event_box.set_margin_end(10)
        self.active_event_box.set_margin_top(10)
        self.active_event_box.set_margin_bottom(10)
        self.active_event_box.set_vexpand(False)
        self.active_event_box.set_hexpand(False)
        
        
        # Add time label to active event box
        self.time_label = Gtk.Label(label=f"{datetime.datetime.now():%H:%M:%S}")
        self.active_event_box.append(self.time_label)

        # Create an Overlay to manage widgets
        self.overlay = Gtk.Overlay(name="notch-content")
        self.overlay.set_hexpand(True)
        self.overlay.set_vexpand(True)
        
        # Add widgets directly to the overlay
        self.overlay.add_overlay(self.active_event_box)
        self.dashboard.set_margin_start(10)
        self.dashboard.set_margin_end(10)
        self.dashboard.set_margin_top(10)
        self.dashboard.set_margin_bottom(10)
        self.dashboard.set_vexpand(False)
        self.dashboard.set_hexpand(False)
        self.overlay.add_overlay(self.dashboard)
        
        self.notification_center = NotificationCenter(self)
        self.notification_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-page")
        self.notification_page.append(self.notification_center.notification_view)
        self.notification_page.set_margin_start(10)
        self.notification_page.set_margin_end(10)
        self.notification_page.set_margin_top(10)
        self.notification_page.set_margin_bottom(10)
        self.notification_page.set_vexpand(False)
        self.notification_page.set_hexpand(False)
        self.overlay.add_overlay(self.notification_page)
        
        # Set initial visibility and opacity
        self.active_event_box.set_visible(True)
        self.active_event_box.set_opacity(1.0)
        self.dashboard.set_visible(False)
        self.dashboard.set_opacity(0.0)
        self.notification_page.set_visible(False)
        self.notification_page.set_opacity(0.0)
        
        self.append(self.overlay)
        
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
        
        # Add to each child widget to ensure we catch events
        for widget in [self.dashboard, self.notification_page, self.active_event_box, self.overlay]:
            key_controller = Gtk.EventControllerKey.new()
            key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            key_controller.connect("key-pressed", self.on_key_pressed)
            widget.add_controller(key_controller)
        
        # Start time updater
        GLib.timeout_add_seconds(1, self.update_time)
        
        # Add event after initialization to ensure focus
        GLib.timeout_add(100, self.ensure_keyboard_focus)
        
        # Track the previous widget
        self.previous_widget = 'active-event-box'

    def ensure_keyboard_focus(self):
        """Make sure we have keyboard focus"""
        self.grab_focus()
        return False  # Run once

    def update_time(self):
        """Update the time label every second"""
        self.time_label.set_text(f"{datetime.datetime.now():%H:%M:%S}")
        return True  # Continue calling

    def transition_to(self, new_widget):
        """Animate transition to a new widget with scaling and opacity effect"""
        print(f"Transitioning to widget: {new_widget.get_name() if hasattr(new_widget, 'get_name') else 'unknown'}")
        
        # Fade out all other widgets and clean up their classes
        for widget in [self.active_event_box, self.dashboard, self.notification_page]:
            if widget != new_widget and widget.get_visible():
                widget.set_opacity(0.0)
                widget.set_visible(False)
                # Force remove classes with check
                if widget.has_css_class("expanding"):
                    widget.remove_css_class("expanding")
                    print(f"Removed 'expanding' from {widget.get_name() if hasattr(widget, 'get_name') else 'widget'}")
                if widget.has_css_class("open"):
                    widget.remove_css_class("open")
                    print(f"Removed 'open' from {widget.get_name() if hasattr(widget, 'get_name') else 'widget'}")

        # Only add expanding class if this is not the active event box
        if new_widget != self.active_event_box:
            # Fade in and scale the new widget
            new_widget.set_visible(True)
            new_widget.set_opacity(0.0)
            
            steps = 20
            current_step = 0
            
            # Add CSS class to trigger scaling
            new_widget.add_css_class("expanding")
            print(f"Added 'expanding' class to new widget")

            def fade_in():
                nonlocal current_step
                if current_step < steps:
                    opacity = current_step / steps
                    new_widget.set_opacity(opacity)
                    current_step += 1
                    return True
                else:
                    new_widget.set_opacity(1.0)
                    # Remove expanding class when animation is complete
                    if new_widget.has_css_class("expanding"):
                        new_widget.remove_css_class("expanding")
                        print(f"Animation complete - removed 'expanding' class")
                    return False

            GLib.timeout_add(10, fade_in)
        else:
            # For active event box, just show it immediately
            new_widget.set_visible(True)
            new_widget.set_opacity(1.0)

        # Handle focus
        new_widget.grab_focus()
        self.grab_focus()
        GLib.timeout_add(50, lambda: self.grab_focus() and False)

    def collapse_notch(self):
        """Collapse the notch back to the active event box"""
        current = self.get_current_widget()
        if current != 'active-event-box':
            print(f"Collapsing from {current} to active-event-box")
            
            # Force immediate class removal with debugging
            def force_remove_classes():
                print("Force removing dashboard classes...")
                # Remove from dashboard widget
                if self.dashboard.has_css_class("expanding"):
                    self.dashboard.remove_css_class("expanding")
                    print("Removed 'expanding' from dashboard")
                if self.dashboard.has_css_class("open"):
                    self.dashboard.remove_css_class("open")
                    print("Removed 'open' from dashboard")
                
                # Remove from notification widget  
                if self.notification_page.has_css_class("expanding"):
                    self.notification_page.remove_css_class("expanding")
                    print("Removed 'expanding' from notification_page")
                if self.notification_page.has_css_class("open"):
                    self.notification_page.remove_css_class("open")
                    print("Removed 'open' from notification_page")
                    
                # Remove from notification view
                if self.notification_center.notification_view.has_css_class("open"):
                    self.notification_center.notification_view.remove_css_class("open")
                    print("Removed 'open' from notification_view")
                
                # Remove from overlay
                overlay_context = self.overlay.get_style_context()
                if overlay_context.has_class("dashboard"):
                    self.overlay.remove_css_class("dashboard")
                    print("Removed 'dashboard' from overlay")
                if overlay_context.has_class("notification"):
                    self.overlay.remove_css_class("notification")
                    print("Removed 'notification' from overlay")
                
                return False  # Don't repeat
            
            # Clean up all widget states and classes immediately
            for widget in [self.dashboard, self.notification_page]:
                widget.set_visible(False)
                widget.set_opacity(0.0)
            
            # Force class removal
            force_remove_classes()
            
            # Also schedule another cleanup slightly later to be sure
            GLib.timeout_add(50, force_remove_classes)
            
            # Transition to active event box
            self.transition_to(self.active_event_box)

    def open_notch(self, widget_name):
        """Open the specified widget with a transition"""
        if widget_name == 'dashboard':
            new_widget = self.dashboard
            self.previous_widget = self.get_current_widget()
        elif widget_name == 'notification':
            new_widget = self.notification_page
            self.previous_widget = self.get_current_widget()
        else:
            new_widget = self.active_event_box

        current = self.get_current_widget()
        if current == widget_name:
            print(f"Already on {widget_name}, skipping")
            return
            
        print(f"Opening {widget_name} from {current}")
        
        # Apply blur effect for 0.2 seconds on notch open
        self.overlay.get_style_context().add_class("blur")
        GLib.timeout_add(200, lambda: self.overlay.get_style_context().remove_class("blur") or False)
        
        # Clean up previous widget classes first
        if current == 'dashboard':
            self.overlay.remove_css_class("dashboard")
            self.dashboard.remove_css_class("open")
            self.dashboard.remove_css_class("expanding")
        elif current == 'notification':
            self.overlay.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
            self.notification_page.remove_css_class("expanding")
        
        # Apply new widget classes
        if widget_name == 'dashboard':
            self.overlay.add_css_class("dashboard")
            self.dashboard.add_css_class("open")
        elif widget_name == 'notification':
            self.overlay.add_css_class("notification")
            self.notification_center.notification_view.add_css_class("open")
        else:
            # Ensure all classes are removed when going to active event box
            self.overlay.remove_css_class("dashboard")
            self.overlay.remove_css_class("notification")
            self.dashboard.remove_css_class("open")
            self.dashboard.remove_css_class("expanding")
            self.notification_center.notification_view.remove_css_class("open")
            self.notification_page.remove_css_class("expanding")
        
        # Perform the transition
        self.transition_to(new_widget)
    def on_active_event_box_click(self, gesture, n_press, x, y):
        """Handle click on the active event box to show dashboard"""
        print("Notch clicked, showing dashboard")
        self.open_notch('dashboard')
        return True
    
    def show_notification(self):
        """Show the notification page and save the current widget"""
        current = self.get_current_widget()
        if current != 'notification':
            print(f"Before notification, saving current: {current}")
            self.previous_widget = current
        self.open_notch('notification')
    

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keypress events, particularly ESC to close the notch"""
        print(f"Key pressed: {keyval}, ESC is {Gdk.KEY_Escape}")
        if keyval == Gdk.KEY_Escape or keyval == 65307:
            current = self.get_current_widget()
            print(f"Current widget: {current}")
            if current in ('dashboard', 'notification'):
                print("Closing current widget")
                self.collapse_notch()
                return True
        return False

    def get_current_widget(self):
        """Helper method to get the current visible widget name"""
        if self.dashboard.get_visible():
            return 'dashboard'
        elif self.notification_page.get_visible():
            return 'notification'
        else:
            return 'active-event-box'

# Updated CSS with scaling animation
'''
#notch {
  background-color: transparent;
}

#notch-box {
margin: 10px;
margin-top: 10px;
transition: all 0.5s cubic-bezier(0.5, 0.25, 0, 1.5);
}

#notch-content {
background-color: black;
min-height: 40px;
margin-right: -4px;
margin-left: -4px;
min-width: 256px;
border-radius: 0 0 16px 16px;
transition: all 0.5s cubic-bezier(0.5, 0.25, 0, 1.5);
}

#notch-content.dashboard {
padding: 16px;
min-height: 480px;
min-width: 820px;
border-radius: 0 0 36px 36px;
}

#notch-content.notification {
padding: 16px;
min-height: 100px;
min-width: 360px;
border-radius: 0 0 36px 36px;
opacity: 1;
}

#dashboard {
opacity: 1;
transform: scale(0.1);
transition: all 0.45s cubic-bezier(0.45, 0.25, 0, 1);
}

#dashboard.open {
opacity: 1;
transform: scale(1);
}
'''