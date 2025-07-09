import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Gio
import datetime
from modules.bluetooth import BluetoothStack
from modules.network import NetworkStack
from modules.audio import AudioStack
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

        # Create a stack for network and bluetooth
        self.info_stack = Gtk.Stack()
        self.info_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        self.bluetooth_stack = BluetoothStack(self.notch)
        self.network_stack = NetworkStack(self.notch)
        self.audio_stack = AudioStack()
        
        self.info_stack.add_named(self.network_stack, "network")
        self.info_stack.add_named(self.bluetooth_stack, "bluetooth")
        self.info_stack.add_named(self.audio_stack, "audio")
        
        self.stack_pages = ["network", "bluetooth", "audio"]
        self.current_stack_page = 0

        # Add a shuffle button
        shuffle_button = Gtk.Button.new_with_label("Switch")
        shuffle_button.connect("clicked", self.shuffle_stack)
        right_side.append(shuffle_button)

        expanded_box.append(self.info_stack)
        expanded_box.append(right_side)
        
        # Add expanded box to dashboard
        self.append(expanded_box)

    def shuffle_stack(self, button):
        self.current_stack_page = (self.current_stack_page + 1) % len(self.stack_pages)
        page_name = self.stack_pages[self.current_stack_page]
        self.info_stack.set_visible_child_name(page_name)

    def update_time(self):
        """Update the time display on the button"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.time_button.set_label(current_time)
        return True  # Return True to keep the timer running

    def on_back_button_clicked(self, button):
        # Remove CSS classes from stack and dashboard, then show not active event box.
        self.notch.collapse_notch()