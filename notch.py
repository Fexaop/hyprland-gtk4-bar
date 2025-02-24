from ctypes import CDLL
import gi

CDLL('libgtk4-layer-shell.so')

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')

from gi.repository import Gtk, GLib, Gdk, Gio
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
from widgets.corner import Corner
from music import MusicPlayer

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
    left_corner.add_css_class("corner")
    box.append(left_corner)

    notch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, name="notch-box")
    notch_box.add_css_class("transparent-background")

    time_button = Gtk.Button()
    time_label = Gtk.Label(label="")
    time_button.set_child(time_label)
    time_button.set_hexpand(True)
    notch_box.append(time_button)
    
    expanded_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, name="expanded-content")
    expanded_content.set_visible(False)  # Initially hidden
    
    notification_center = create_notification_center()
    expanded_content.append(notification_center)
    
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
    
    return box, time_button, expanded_content, notch_box

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

    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_margin(window, LayerShell.Edge.TOP, 0)
    LayerShell.set_margin(window, LayerShell.Edge.LEFT, 0)
    LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 0)

    bar_content, time_button, expanded_content, notch_box = create_bar_content()
    window.set_child(bar_content)

    bar_height = 30
    expanded_height = 300
    notch_width = 200
    
    notch_box.set_size_request(notch_width, bar_height)

    is_expanded = False

    def toggle_expansion(button):
        nonlocal is_expanded
        if is_expanded:
            # Collapse
            expanded_content.set_visible(False)
            notch_box.set_size_request(notch_width, bar_height)
            GLib.timeout_add(50, lambda: notch_box.queue_resize())
        else:
            # Expand
            notch_box.set_size_request(notch_width, expanded_height)
            expanded_content.set_visible(True)
            GLib.timeout_add(50, lambda: notch_box.queue_resize())
        
        is_expanded = not is_expanded

    time_button.connect("clicked", toggle_expansion)

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