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
from widgets.corner import Corner

def create_bar_content():
    # Create the main horizontal container.
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, name="bar-window")
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)

    # Create a left Corner widget
    left_corner = Corner("top-right")
    left_corner.set_size_request(20, 30)
    left_corner.set_valign(Gtk.Align.START)  # Align to top
    left_corner.set_vexpand(False)  # Don't expand vertically
    box.append(left_corner)

    # Center section (Time Button) inside a box named notch-box
    notch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5, name="notch-box")
    time_button = Gtk.Button()
    time_label = Gtk.Label(label="")
    time_button.set_child(time_label)
    time_button.set_hexpand(True)
    notch_box.append(time_button)
    box.append(notch_box)

    # Create a right Corner widget
    right_corner = Corner("top-left")
    right_corner.set_size_request(20, 30)
    right_corner.set_valign(Gtk.Align.START)  # Align to top
    right_corner.set_vexpand(False)  # Don't expand vertically
    box.append(right_corner)

    # Update the time label every second.
    def update_time():
        now = datetime.datetime.now()
        time_label.set_label(now.strftime("%I:%M %p"))
        return True

    GLib.timeout_add_seconds(1, update_time)
    update_time()

    # Define click behavior for the time button.
    def on_time_clicked(button):
        popover = Gtk.Popover()
        popover.set_parent(button)
        popover.add_css_class("time-popover")
        label = Gtk.Label(label="gunit is gay")
        label.add_css_class("time-popover-label")
        popover.set_child(label)
        popover.popup()

    time_button.connect("clicked", on_time_clicked)

    # Optionally, add hover event controllers if desired.
    def on_enter_notify(event_controller, x, y, widget):
        widget.add_css_class("hovered")

    def on_leave_notify(event_controller, widget):
        widget.remove_css_class("hovered")

    enter_controller = Gtk.EventControllerMotion()
    enter_controller.connect("enter", on_enter_notify, time_button)
    leave_controller = Gtk.EventControllerMotion()
    leave_controller.connect("leave", on_leave_notify, time_button)
    time_button.add_controller(enter_controller)
    time_button.add_controller(leave_controller)

    return box


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

def on_activate(app):
    window = Gtk.Window(application=app)
    window.set_default_size(200, 30)

    # Use LayerShell for Wayland overlay behavior
    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_margin(window, LayerShell.Edge.TOP, 0)
    LayerShell.set_margin(window, LayerShell.Edge.LEFT, 0)
    LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 0)
    #LayerShell.auto_exclusive_zone_enable(window)
    

    bar_content = create_bar_content()
    window.set_child(bar_content)

    window.set_name("bar-window")
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path('styles/notch.css')
    except GLib.Error as e:
        print(f"Error loading CSS: {e}")
        return

    Gtk.StyleContext.add_provider_for_display(
        window.get_display(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    css_file = Gio.File.new_for_path('styles/notch.css')
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