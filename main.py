from ctypes import CDLL
import gi

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

def load_css():
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path('main.css')
    except GLib.Error as e:
        print(f"Error loading CSS: {e}")
        return None
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    return css_provider


def reload_css(css_provider, window, css_path):
    if not css_provider:
        return
    try:
        css_provider.load_from_path(css_path)
        print("CSS reloaded")
    except GLib.Error as e:
        print(f"Error reloading CSS: {e}")
        return
    Gtk.StyleContext.add_provider_for_display(
        window.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def on_activate(app):
    window = Gtk.Window(application=app, name="notch")
    window.set_resizable(False)
    window.set_decorated(False)  # Remove window decorations

    # Initialize LayerShell for Wayland compositor compatibility
    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)  # Place it at the top layer
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)  # Anchor to top edge
    LayerShell.set_anchor(window, LayerShell.Edge.LEFT, True)  # Span full width
    LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)
    notch = Notch()
    window.set_child(notch)
    bar_height = 50

    # Set fixed exclusive zone for the bar only
    LayerShell.set_exclusive_zone(window, bar_height)

    # Get screen width from the first monitor
    display = Gdk.Display.get_default()
    monitors = display.get_monitors()  # Returns a GList of monitors
    if monitors:
        monitor = monitors[0]  # Use the first monitor
        screen_width = monitor.get_geometry().width
    else:
        screen_width = 1920  # Fallback width
        print("Warning: No monitors detected, using fallback width of 1920")

    window.set_size_request(screen_width, bar_height)



    css_provider = load_css()
    if not css_provider:
        return

    css_file = Gio.File.new_for_path('main.css')
    monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    monitor.connect("changed", lambda *args: reload_css(css_provider, window, 'main.css'))
    window.css_monitor = monitor

    window.present()

app = Gtk.Application(application_id='com.example.gtk4.bar')
app.connect('activate', on_activate)
app.run(None)