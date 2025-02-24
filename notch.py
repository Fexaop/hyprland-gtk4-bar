from ctypes import CDLL
import gi

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
from music import MusicPlayer
from noti import NotificationManager

# For DBus example (optional, remove if not needed)
try:
    gi.require_version('Gio', '2.0')
    from dbus import SessionBus
    from dbus.mainloop.glib import DBusGMainLoop
except ImportError:
    pass

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

def create_bar_content(window):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, name="bar-window")
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)

    left_corner = Corner("top-right")
    left_corner.set_size_request(20, 30)
    left_corner.set_valign(Gtk.Align.START)
    left_corner.set_vexpand(False)
    left_corner.add_css_class("corner")
    box.append(left_corner)

    notch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, name="notch-box")
    notch_box.add_css_class("transparent-background")
    notch_box.set_size_request(200, 30)

    time_button = Gtk.Button()
    time_label = Gtk.Label(label="")
    time_button.set_child(time_label)
    time_button.set_hexpand(True)
    notch_box.append(time_button)

    notifications_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, name="notifications-box")
    notch_box.append(notifications_box)

    def resize_notch(num_notifications):
        base_height = 30
        notif_height = 80 * min(num_notifications, 3)
        new_height = base_height + notif_height
        notch_box.set_size_request(200, new_height)
        notifications_box.set_size_request(200, notif_height)
        window.set_size_request(window.get_allocated_width(), new_height)
        window.queue_resize()

    notif_manager = NotificationManager(notifications_box, resize_notch)
    window.notif_manager = notif_manager  # Make globally accessible

    expanded_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, name="expanded-content")
    expanded_content.set_visible(False)

    right_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    calendar = Gtk.Calendar(name="calendar")
    right_side.append(calendar)
    
    music_player = MusicPlayer()
    right_side.append(music_player)
    
    expanded_content.append(right_side)
    notch_box.append(expanded_content)
    box.append(notch_box)

    right_corner = Corner("top-left")
    right_corner.set_size_request(20, 30)
    right_corner.set_valign(Gtk.Align.START)
    right_corner.set_vexpand(False)
    right_corner.add_css_class("corner")
    box.append(right_corner)

    def update_time():
        time_label.set_label(datetime.datetime.now().strftime("%I:%M %p"))
        return True

    GLib.timeout_add_seconds(1, update_time)
    update_time()

    return box, time_button, expanded_content, notch_box, notif_manager

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

def setup_dbus_notifications(window):
    try:
        DBusGMainLoop(set_as_default=True)
        bus = SessionBus()
        bus.add_match_string(
            "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
        )
        def on_notify(*args, **kwargs):
            if len(args) >= 7:
                app_name = args[0]
                summary = args[3]  # Title
                body = args[4]     # Message
                if summary or body:
                    window.notif_manager.add_notification(
                        summary or "Notification",
                        body or "No message"
                    )
        bus.add_message_filter(on_notify)
    except Exception as e:
        print(f"Failed to set up DBus notifications: {e}")

def on_activate(app):
    window = Gtk.Window(application=app)
    window.set_resizable(False)
    window.set_decorated(False)

    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_anchor(window, LayerShell.Edge.LEFT, True)
    LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)

    bar_content, time_button, expanded_content, notch_box, notif_manager = create_bar_content(window)
    window.set_child(bar_content)

    bar_height = 30
    expanded_height = 300
    notch_width = 200

    LayerShell.set_exclusive_zone(window, bar_height)

    display = Gdk.Display.get_default()
    monitors = display.get_monitors()
    if monitors:
        monitor = monitors[0]
        screen_width = monitor.get_geometry().width
    else:
        screen_width = 1920
        print("Warning: No monitors detected, using fallback width of 1920")

    window.set_size_request(screen_width, bar_height)

    is_expanded = False

    def toggle_expansion(button):
        nonlocal is_expanded
        if is_expanded:
            expanded_content.set_visible(False)
            notch_box.set_size_request(notch_width, bar_height)
            window.set_size_request(screen_width, bar_height)
            GLib.timeout_add(50, lambda: window.queue_resize())
        else:
            notch_box.set_size_request(notch_width, expanded_height)
            window.set_size_request(screen_width, expanded_height)
            expanded_content.set_visible(True)
            GLib.timeout_add(50, lambda: window.queue_resize())
        
        is_expanded = not is_expanded

    time_button.connect("clicked", toggle_expansion)

    css_provider = load_css()
    if not css_provider:
        return

    css_file = Gio.File.new_for_path('main.css')
    monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    monitor.connect("changed", lambda *args: reload_css(css_provider, window, 'main.css'))
    window.css_monitor = monitor

    # Test notifications
    GLib.timeout_add(2000, lambda: notif_manager.add_notification("Test 1", "First notification"))
    GLib.timeout_add(4000, lambda: notif_manager.add_notification("Test 2", "Second notification"))
    GLib.timeout_add(6000, lambda: notif_manager.add_notification("Test 3", "Third notification"))

    # Setup DBus for real notifications
    setup_dbus_notifications(window)

    window.present()

app = Gtk.Application(application_id='com.example.gtk4.bar')
app.connect('activate', on_activate)
app.run(None)