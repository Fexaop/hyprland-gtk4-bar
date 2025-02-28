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
from modules.bar import WorkspaceBar

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


def reload_css(css_provider, windows, css_path):
    if not css_provider:
        return
    try:
        css_provider.load_from_path(css_path)
        print("CSS reloaded")
        
        # Apply to all windows
        display = Gdk.Display.get_default()
        Gtk.StyleContext.remove_provider_for_display(display, css_provider)
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
    except GLib.Error as e:
        print(f"Error reloading CSS: {e}")

def on_activate(app):
    # Create notch window (overlay)
    notch_window = Gtk.Window(application=app, name="notch")
    notch_window.set_resizable(False)
    notch_window.set_decorated(False)
    
    # Initialize LayerShell for notch
    LayerShell.init_for_window(notch_window)
    LayerShell.set_layer(notch_window, LayerShell.Layer.TOP)  # Use overlay layer
    LayerShell.set_anchor(notch_window, LayerShell.Edge.TOP, True)  # Anchor only to top edge
    
    # Position the notch in the center horizontally
    LayerShell.set_anchor(notch_window, LayerShell.Edge.LEFT, False)
    LayerShell.set_anchor(notch_window, LayerShell.Edge.RIGHT, False)
    LayerShell.set_margin(notch_window, LayerShell.Edge.LEFT, 0)
    LayerShell.set_margin(notch_window, LayerShell.Edge.RIGHT, 0)
    LayerShell.set_margin(notch_window, LayerShell.Edge.TOP, -40)  # Adjusted for smaller bar height

    # Create a box for the notch
    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    center_box.set_name("center-box")
    center_box.set_halign(Gtk.Align.CENTER)
    
    # Add notch to center box
    notch = Notch()
    center_box.append(notch)
    
    # Set the box as notch window's child
    notch_window.set_child(center_box)
    
    # Set notch size - only specifying height, letting width adjust to content
    bar_height = 30  # Reduced from 45px to 30px
    notch_window.set_size_request(-1, bar_height)  # Auto width, fixed height
    
    # The next step is to center the window on screen
    display = Gdk.Display.get_default()
    if display:
        monitor = display.get_monitors()[0] if display.get_monitors() else None
        if monitor:
            screen_width = monitor.get_geometry().width
            # Calculate the position to center the window
            # This is handled by LayerShell automatically when we don't anchor to left/right
            pass
    
    # Create workspace bar (separate window)
    workspace_bar = WorkspaceBar(app)
    
    # Load CSS for styling
    css_provider = load_css()
    
    # Apply CSS to workspace bar
    workspace_bar.load_css(css_provider)
    
    # Monitor CSS file for changes
    if css_provider:
        css_file = Gio.File.new_for_path('main.css')
        monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        windows = [notch_window, workspace_bar]
        monitor.connect("changed", lambda *args: reload_css(css_provider, windows, 'main.css'))
        notch_window.css_monitor = monitor  # Keep a reference to prevent garbage collection
    
    # Show both windows
    notch_window.present()
    workspace_bar.present()

app = Gtk.Application(application_id='com.example.gtk4.bar')
app.connect('activate', on_activate)

try:
    app.run(None)
except KeyboardInterrupt:
    print("Application interrupted by user, exiting...")