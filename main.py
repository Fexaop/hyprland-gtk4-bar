from ctypes import CDLL
import gi
import os
import logging
# Load GTK4 Layer Shell
try:
    CDLL('libgtk4-layer-shell.so')
except OSError:
    print("Error: Could not load libgtk4-layer-shell.so. Please ensure gtk4-layer-shell is installed.")
    exit(1)

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')

from gi.repository import Gtk, GLib, Gdk, Gio
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
from modules.notch import Notch
from modules.bar import Bar

class MyApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.notch = None  # To store the Notch instance
        self.notch_window = None  
        self.css_monitors = []  # To store CSS file monitors

    def do_activate(self):
        # Create notch window (overlay)
        self.notch_window = Gtk.Window(application=self, name="notch")
        self.notch_window.set_resizable(False)
        self.notch_window.set_decorated(False)

        # Initialize LayerShell for notch
        LayerShell.init_for_window(self.notch_window)
        LayerShell.set_layer(self.notch_window, LayerShell.Layer.TOP)
        LayerShell.set_anchor(self.notch_window, LayerShell.Edge.TOP, True)
        LayerShell.set_keyboard_mode(self.notch_window, LayerShell.KeyboardMode.ON_DEMAND)
        LayerShell.set_namespace(self.notch_window, "notch")

        # Position the notch
        LayerShell.set_anchor(self.notch_window, LayerShell.Edge.LEFT, False)
        LayerShell.set_anchor(self.notch_window, LayerShell.Edge.RIGHT, False)
        LayerShell.set_margin(self.notch_window, LayerShell.Edge.LEFT, 0)
        LayerShell.set_margin(self.notch_window, LayerShell.Edge.RIGHT, 0)
        LayerShell.set_margin(self.notch_window, LayerShell.Edge.TOP, -40)

        # Create a box for the notch
        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        center_box.set_name("center-box")
        center_box.set_halign(Gtk.Align.CENTER)

        # Add notch to center box
        self.notch = Notch(notch_window=self.notch_window)
        center_box.append(self.notch)

        # Set the box as notch window's child
        self.notch_window.set_child(center_box)

        # Set notch size
        bar_height = 40
        self.notch_window.set_size_request(-1, bar_height)

        # Create workspace bar
        bar = Bar(self)

        # Load CSS
        css_provider = load_css()

        # Monitor CSS files for changes
        if css_provider:
            css_files = [
                'main.css',
                'styles/notch.css',
                'styles/notification.css',
                'styles/workspace.css',
                'styles/systray.css'
            ]
            os.makedirs('styles', exist_ok=True)
            windows = [self.notch_window, bar]
            
            for css_file_path in css_files:
                css_file = Gio.File.new_for_path(css_file_path)
                monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
                monitor.connect("changed", lambda m, f, of, evt: reload_css(css_provider, windows, 'main.css'))
                self.css_monitors.append(monitor)  # Store monitors to prevent garbage collection

        # Define the 'open_notch' action with a string parameter
        action = Gio.SimpleAction.new("open_notch", GLib.VariantType.new("s"))
        action.connect("activate", self.on_open_notch)
        self.add_action(action)

        # Show windows
        bar.present()
        self.notch_window.present()

    def on_open_notch(self, action, parameter):
        """Handler for the 'open_notch' action."""
        if self.notch:
            widget_name = parameter.get_string()
            self.notch.open_notch(widget_name)

def load_css():
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path('main.css')
        print("CSS loaded from main.css")
    except GLib.Error as e:
        print(f"Error loading CSS: {e}")
        return None
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    return css_provider

def reload_css(css_provider, windows, css_path):
    if not css_provider:
        return
    try:
        css_provider.load_from_path(css_path)
        print(f"CSS reloaded from {css_path}")
        display = Gdk.Display.get_default()
        Gtk.StyleContext.remove_provider_for_display(display, css_provider)
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    except GLib.Error as e:
        print(f"Error reloading CSS: {e}")

# Run the application
app = MyApp(application_id='com.example.gtk4.bar')
try:
    app.run(None)
except KeyboardInterrupt:
    print("Application interrupted by user, exiting...")