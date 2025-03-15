from ctypes import CDLL
import gi
import os

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
    LayerShell.set_layer(notch_window, LayerShell.Layer.TOP)  # Changed back to TOP layer
    LayerShell.set_anchor(notch_window, LayerShell.Edge.TOP, True)  # Anchor only to top edge
    
    # Ensure the notch window receives keyboard/mouse input
    LayerShell.set_keyboard_mode(notch_window, LayerShell.KeyboardMode.ON_DEMAND)
    
    # Increase the z-index of the notch to ensure it's above everything else
    LayerShell.set_namespace(notch_window, "notch")  # Use a custom namespace for higher precedence
    
    # Position the notch in the center horizontally
    LayerShell.set_anchor(notch_window, LayerShell.Edge.LEFT, False)
    LayerShell.set_anchor(notch_window, LayerShell.Edge.RIGHT, False)
    LayerShell.set_margin(notch_window, LayerShell.Edge.LEFT, 0)
    LayerShell.set_margin(notch_window, LayerShell.Edge.RIGHT, 0)
    LayerShell.set_margin(notch_window, LayerShell.Edge.TOP, -55)  # Reduced negative margin

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
    bar_height = 50  # Reduced from 45px to 30px
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
    bar = Bar(app)
    
    # Load CSS for styling
    css_provider = load_css()
    
    # Apply CSS to workspace bar
    bar.load_css(css_provider)
    
    # Monitor all CSS files for changes
    if css_provider:
        css_files = [
            'main.css',
            'styles/notch.css',
            'styles/notification.css',
            'styles/workspace.css',
            'styles/systray.css'
        ]
        
        # Create styles directory if it doesn't exist
        os.makedirs('styles', exist_ok=True)
        
        windows = [notch_window, bar]
        monitors = []
        
        for css_file_path in css_files:
            css_file = Gio.File.new_for_path(css_file_path)
            monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", lambda m, f, of, evt, fp=css_file_path: reload_css(css_provider, windows, 'main.css'))
            monitors.append(monitor)  # Keep references to prevent garbage collection
        
        # Store monitors as an attribute of the window to prevent garbage collection
        notch_window.css_monitors = monitors
    
    # Show both windows
    notch_window.present()
    bar.present()

app = Gtk.Application(application_id='com.example.gtk4.bar')
app.connect('activate', on_activate)

try:
    app.run(None)
except KeyboardInterrupt:
    print("Application interrupted by user, exiting...")