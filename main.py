import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

# Import the GTK modules for notch and bar.
import modules.notch as notch
import modules.bar as bar

def on_activate(app):
    # Create and show the notch window.
    notch.on_activate(app)
    # Create and show the bar window.
    bar.on_activate(app)

app = Gtk.Application(application_id='com.example.gtk4.main')
app.connect("activate", on_activate)
app.run(None)
