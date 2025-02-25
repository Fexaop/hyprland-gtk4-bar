import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Gio
from modules.music import MusicPlayer

class Dashboard(Gtk.Box):
    def __init__(self, notch, **kwargs):
        super().__init__(
            name="dashboard",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL
        )
        self.notch = notch  # store reference to Notch
        # Add a Back button at the top
        back_button = Gtk.Button(label="Back", name="back-button")
        back_button.connect("clicked", self.on_back_button_clicked)
        self.append(back_button)
        # Create expanded content box
        expanded_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, name="expanded-content")
        
        # Create right side container
        right_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        calendar = Gtk.Calendar(name="calendar")
        right_side.append(calendar)
        
        # Import and add the music player
        music_player = MusicPlayer()
        right_side.append(music_player)
        
        # Add right side to expanded box
        expanded_box.append(right_side)
        
        # Add expanded box to dashboard
        self.append(expanded_box)

    def on_back_button_clicked(self, button):
        # Remove CSS classes from stack and dashboard, then show not active event box.
        self.notch.stack.remove_css_class("dashboard")
        self.remove_css_class("open")
        self.notch.stack.set_visible_child_name('active-event-box')
