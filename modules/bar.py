import gi
from ctypes import CDLL

# Load GTK4 Layer Shell
try:
    CDLL('libgtk4-layer-shell.so')
except OSError:
    print("Error: Could not load libgtk4-layer-shell.so. Please ensure gtk4-layer-shell is installed.")
    exit(1)

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, GLib, Gdk
from gi.repository import Gtk4LayerShell as LayerShell

from modules.workspace import WorkspaceBar
from modules.systray import SysTray, setup_css

class Bar(Gtk.ApplicationWindow):
    """A LayerShell window that contains the workspace bar."""
    
    def __init__(self, application):
        super().__init__(application=application)
        
        # Set up the window
        self.set_name("bar")
        self.set_resizable(True)  # Allow resizing
        self.set_decorated(False)
        
        # Initialize LayerShell
        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, LayerShell.Layer.BOTTOM)  # Keep as BOTTOM to ensure notch is above
        LayerShell.set_namespace(self, "bar")  # Use a different namespace
        
        # Anchor to top, left AND right for full width
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
        
        # Set zero margins on left and right to ensure full width
        LayerShell.set_margin(self, LayerShell.Edge.LEFT, 0)
        LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 0)
        LayerShell.set_margin(self, LayerShell.Edge.TOP, 0)  # Ensure no gap at the top
        
        # Set height and exclusive zone to 30px
        bar_height = 30
        # Add 10px for the margins (5px top + 5px bottom)
        LayerShell.set_exclusive_zone(self, bar_height + 10)
        
        # Set explicit width to maximum possible and fixed height with margins
        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else []
        monitor = monitors[0] if len(monitors) > 0 else None
        screen_width = monitor.get_geometry().width if monitor else -1
        self.set_size_request(screen_width, bar_height + 10)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_name("bar-box")
        main_box.set_valign(Gtk.Align.CENTER)  # Center content vertically
        main_box.set_vexpand(True)  # Allow box to expand vertically
        main_box.set_hexpand(True)  # Allow box to expand horizontally
        main_box.set_margin_bottom(5)  # 5px margin at the bottom
        
        # Add workspace bar (left-aligned)
        workspace_bar = WorkspaceBar()
        workspace_bar.set_valign(Gtk.Align.CENTER)  # Center workspace bar vertically
        workspace_bar.set_vexpand(True)  # Allow bar to expand vertically
        main_box.append(workspace_bar)
        
        # Add an empty expanding spacer to push workspace bar to left and system tray to right
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        spacer.set_valign(Gtk.Align.CENTER)  # Center spacer vertically
        main_box.append(spacer)
        
        # Add system tray (right-aligned)
        systray = SysTray()
        systray.set_size_request(-1, bar_height)
        systray.set_valign(Gtk.Align.CENTER)  # Center systray vertically
        systray.set_margin_start(4)
        systray.set_margin_end(4)
        main_box.append(systray)
        
        # Set as window child
        self.set_child(main_box)
        
        # Apply CSS
        self.css_provider = setup_css()
        self.load_css(self.css_provider)
        
    def load_css(self, css_provider):
        """Apply the provided CSS provider to this window"""
        if css_provider:
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), 
                css_provider, 
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

# For testing individually
if __name__ == "__main__":
    app = Gtk.Application(application_id="com.example.bar")
    
    def on_activate(app):
        bar = Bar(app)
        bar.present()
    
    app.connect("activate", on_activate)
    app.run(None)
