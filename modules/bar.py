import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, GLib, Gdk
from gi.repository import Gtk4LayerShell as LayerShell

from modules.workspace import WorkspacePanel

class WorkspaceBar(Gtk.ApplicationWindow):
    """A LayerShell window that contains the workspace panel."""
    
    def __init__(self, application):
        super().__init__(application=application)
        
        # Set up the window
        self.set_name("workspace-bar")
        self.set_resizable(False)
        self.set_decorated(False)
        
        # Initialize LayerShell
        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, LayerShell.Layer.TOP)
        
        # Anchor to top, left AND right for full width
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
        
        # Set height and exclusive zone to 30px (reduced from 45px)
        bar_height = 30
        LayerShell.set_exclusive_zone(self, bar_height)
        self.set_size_request(-1, bar_height)  # Full width, fixed height
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_name("workspace-bar-box")
        
        # Add workspace panel (left-aligned)
        workspace_panel = WorkspacePanel()
        main_box.append(workspace_panel)
        
        # Add an empty expanding spacer to push workspace panel to left
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        main_box.append(spacer)
        
        # Set as window child
        self.set_child(main_box)
        
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
    app = Gtk.Application(application_id="com.example.workspace_bar")
    
    def on_activate(app):
        bar = WorkspaceBar(app)
        bar.present()
    
    app.connect("activate", on_activate)
    app.run(None)
