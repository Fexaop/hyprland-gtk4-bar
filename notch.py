# notch.py
from ctypes import CDLL

CDLL('libgtk4-layer-shell.so')

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('GLib', '2.0')

from gi.repository import Gtk, GLib, Gdk
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
from dash import create_dashboard_content  # Import the dashboard function


def create_bar_content():
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)

    time_button = Gtk.Button()
    time_label = Gtk.Label(label="")
    time_button.set_child(time_label)
    time_button.set_hexpand(True)
    box.append(time_button)

    def update_time():
        now = datetime.datetime.now()
        time_label.set_label(now.strftime("%I:%M %p"))
        return True

    GLib.timeout_add_seconds(1, update_time)
    update_time()

    def on_time_clicked(button):
        popover = Gtk.Popover()
        popover.set_parent(button)
        popover.add_css_class("time-popover")

        # Load CSS *specifically* for the popover
        popover_css_provider = Gtk.CssProvider()
        try:
            popover_css_provider.load_from_path('dash.css')  # Load from dash.css
        except GLib.Error as e:
            print(f"Error loading popover CSS: {e}")
            return

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            popover_css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        dashboard_grid = create_dashboard_content()
        popover.set_child(dashboard_grid)
        popover.popup()

    time_button.connect("clicked", on_time_clicked)
    return box



def on_activate(app):
    window = Gtk.Window(application=app)
    window.set_default_size(600, 30)

    LayerShell.init_for_window(window)
    LayerShell.set_layer(window, LayerShell.Layer.TOP)
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_margin(window, LayerShell.Edge.TOP, 5)
    LayerShell.set_margin(window, LayerShell.Edge.LEFT, 5)
    LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 5)
    LayerShell.auto_exclusive_zone_enable(window)

    bar_content = create_bar_content()
    window.set_child(bar_content)

    window.set_name("bar-window")

    # Load CSS for the main bar window from notch.css
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path('notch.css')
    except GLib.Error as e:
        print(f"Error loading bar CSS: {e}")
        return

    Gtk.StyleContext.add_provider_for_display(
        window.get_display(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    window.present()

app = Gtk.Application(application_id='com.example.gtk4.bar')
app.connect('activate', on_activate)
app.run(None)