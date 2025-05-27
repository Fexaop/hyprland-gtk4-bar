import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Gio
import datetime

class Dashboard(Gtk.Box):
    def __init__(self, notch, **kwargs):
        super().__init__(
            name="dashboard",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL
        )
        self.notch = notch  # store reference to Notch
        
        # Create a time button instead of back button
        self.time_button = Gtk.Button(name="time-button")
        self.update_time()  # Set initial time
        
        # Connect the click handler
        self.time_button.connect("clicked", self.on_back_button_clicked)
        self.append(self.time_button)
        
        # Set up a timer to update the time every second
        GLib.timeout_add_seconds(1, self.update_time)
        
        # Create expanded content box
        expanded_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, name="expanded-content")
        
        # Create right side container
        right_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        calendar = Gtk.Calendar(name="calendar")
        right_side.append(calendar)
        
        # Add right side to expanded box
        expanded_box.append(right_side)
        
        # Add expanded box to dashboard
        self.append(expanded_box)

    def update_time(self):
        """Update the time display on the button"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.time_button.set_label(current_time)
        return True  # Return True to keep the timer running

    def on_back_button_clicked(self, button):
        # Remove CSS classes from stack and dashboard, then show not active event box.
        self.notch.collapse_notch()