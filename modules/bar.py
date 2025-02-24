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


def reload_css(css_provider, window, css_path):
    try:
        css_provider.load_from_path(css_path)
        print("CSS reloaded")
    except GLib.Error as e:
        print(f"Error reloading CSS: {e}")
    Gtk.StyleContext.add_provider_for_display(
        window.get_display(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def update_size(window):
    surface = window.get_surface()
    if surface:
        monitor = window.get_display().get_monitor_at_surface(surface)
        geometry = monitor.get_geometry()
        window.set_default_size(geometry.width, 30)
        return False  # stop the idle loop
    return True  # try again

def on_activate(app):
    window = Gtk.Window(application=app)
    display = window.get_display()
    # Removed immediate monitor/geometry calls
    # Instead, schedule update_size to run when window's surface is available
    GLib.idle_add(update_size, window)

    # Use LayerShell for Wayland overlay behavior
    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_margin(window, LayerShell.Edge.TOP, 0)
    LayerShell.set_margin(window, LayerShell.Edge.LEFT, 0)
    LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 0)
    LayerShell.auto_exclusive_zone_enable(window)
    


    window.set_name("bar-window")
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path('notch.css')
    except GLib.Error as e:
        print(f"Error loading CSS: {e}")
        return

    Gtk.StyleContext.add_provider_for_display(
        window.get_display(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    css_file = Gio.File.new_for_path('notch.css')
    monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    monitor.connect("changed", lambda monitor, file, other_file, event: reload_css(css_provider, window, 'notch.css'))
    window.css_monitor = monitor

    window.present()

def signal_handler(signum, frame):
    print("\nExiting gracefully...")
    app.quit()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    app = Gtk.Application(application_id='com.example.gtk4.bar')
    app.connect('activate', on_activate)
    try:
        app.run(None)
    except KeyboardInterrupt:
        app.quit()