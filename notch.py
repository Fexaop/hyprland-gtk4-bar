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
from widgets.corner import Corner
from modules.music import MusicPlayer

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

def create_notification_center():
    notif_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, name="notification-center")
    
    dnd_button = Gtk.Button(label="Do Not Disturb", name="dnd-button")
    notif_box.append(dnd_button)
    
    notifications_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, name="notifications-box")
    notif_box.append(notifications_box)
    
    clear_button = Gtk.Button(label="Clear All", name="clear-button")
    notif_box.append(clear_button)
    
    return notif_box

def create_bar_content():
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, name="bar-window")
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)

    left_corner = Corner("top-right")
    left_corner.set_size_request(20, 30)
    left_corner.set_valign(Gtk.Align.START)
    left_corner.set_vexpand(False)
    left_corner.get_style_context().add_class("corner")
    box.append(left_corner)

    notch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, name="notch-box")
    notch_box.add_css_class("transparent-background")

    # Create time button
    time_button = Gtk.Button()
    time_label = Gtk.Label(label="")
    time_button.set_child(time_label)
    time_button.set_hexpand(True)
    
    # Create a Gtk.Stack and add time_button as the first page
    stack = Gtk.Stack()
    stack.add_named(time_button, "time")
    
    # Create a container for expanded content with overflow hidden
    expanded_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    expanded_container.set_overflow(Gtk.Overflow.HIDDEN)
    
    expanded_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, name="expanded-content")
    
    # Create a duplicate time button for the expanded view
    expanded_time_button = Gtk.Button()
    expanded_time_label = Gtk.Label(label="")
    expanded_time_button.set_child(expanded_time_label)
    
    notification_center = create_notification_center()
    right_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    
    # Add the expanded time button at the top of the right side
    right_side.append(expanded_time_button)
    
    calendar = Gtk.Calendar(name="calendar")
    right_side.append(calendar)
    music_player = MusicPlayer()
    right_side.append(music_player)
    
    expanded_box.append(notification_center)
    expanded_box.append(right_side)
    
    # Add expanded_box to the container
    expanded_container.append(expanded_box)
    stack.add_named(expanded_container, "expanded")
    
    # Set the visible child to time
    stack.set_visible_child_name("time")
    
    notch_box.append(stack)
    
    box.append(notch_box)

    right_corner = Corner("top-left")
    right_corner.set_size_request(20, 30)
    right_corner.set_valign(Gtk.Align.START)
    right_corner.set_vexpand(False)
    right_corner.get_style_context().add_class("corner")
    box.append(right_corner)

    def update_time():
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        time_label.set_label(current_time)
        expanded_time_label.set_label(current_time)
        return True
    
    is_expanded = False
    GLib.timeout_add_seconds(1, update_time)
    update_time()

    def toggle_expansion(button):
        nonlocal is_expanded
        if is_expanded:
            expanded_box.get_style_context().remove_class("open")
            stack.set_visible_child_name("time")
        else:
            expanded_box.get_style_context().add_class("open")
            stack.set_visible_child_name("expanded")
        is_expanded = not is_expanded
    
    # Connect both time buttons to the toggle function
    time_button.connect("clicked", toggle_expansion)
    expanded_time_button.connect("clicked", toggle_expansion)
    
    return box, time_button, notch_box

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
    window = Gtk.Window(application=app)
    window.set_resizable(False)
    window.set_decorated(False)  # Remove window decorations

    # Initialize LayerShell for Wayland compositor compatibility
    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)  # Place it at the top layer
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)  # Anchor to top edge
    LayerShell.set_anchor(window, LayerShell.Edge.LEFT, True)  # Span full width
    LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)

    bar_content, time_button, notch_box = create_bar_content()
    window.set_child(bar_content)

    bar_height = 30
    expanded_height = 300
    notch_width = 200
    
    notch_box.set_size_request(notch_width, bar_height)

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