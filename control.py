import sys
import gi
from gi.repository import Gio, GLib

if len(sys.argv) != 2:
    print("Usage: python control.py <widget_name>")
    sys.exit(1)

widget_name = sys.argv[1]

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
bus.call_sync(
    'com.example.gtk4.bar',           # Bus name
    '/com/example/gtk4/bar',          # Object path
    'org.gtk.Actions',                # Interface
    'Activate',                       # Method
    GLib.Variant('(sava{sv})', (
        'open_notch',                 # Action name
        [GLib.Variant('s', widget_name)],  # Parameter
        {}                            # Platform data
    )),
    None,
    Gio.DBusCallFlags.NONE,
    -1,
    None
)