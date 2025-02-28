import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

from service.hyprland import HyprlandService

class WorkspaceIndicator(Gtk.Box):
    """
    A widget that displays Hyprland workspaces as a row of indicators.
    
    Dynamically shows workspaces in ranges of 10:
    - 1-10 when active workspace is in that range
    - 11-20 when active workspace is in that range
    - 21-30 when active workspace is in that range
    And so on...
    
    With styling:
    - Active workspace: White background with black text
    - Inactive workspace with windows: White text
    - Empty workspace: Gray text
    """
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)  # Reduced spacing
        
        self.set_name("workspace-indicator")
        self.set_margin_start(4)  # Reduced margins
        self.set_margin_end(4)
        self.set_margin_top(2)    # Smaller vertical margins
        self.set_margin_bottom(2)
        
        # Get hyprland service
        self.hyprland = HyprlandService.get_default()
        
        # Current displayed range (start, end)
        self.current_range = (1, 10)
        
        # Create workspace indicators for initial range
        self.workspace_buttons = {}
        self.setup_workspace_indicators()
        
        # Connect signals to update UI
        self.hyprland.connect("workspaces-changed", self.update_workspaces)
        self.hyprland.connect("active-workspace-changed", self.update_workspaces)
        
        # Add scroll controller for workspace switching
        scroll_controller = Gtk.EventControllerScroll()
        # Use proper flags enum instead of integer
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.on_scroll)
        self.add_controller(scroll_controller)
        
        # Initial update
        self.update_workspaces()
    
    def get_workspace_range(self, workspace_id):
        """Determine the range (start, end) for a given workspace ID"""
        # Calculate range based on workspace_id
        # For workspace 1-10: range is (1, 10)
        # For workspace 11-20: range is (11, 20)
        # And so on...
        start = ((workspace_id - 1) // 10) * 10 + 1
        end = start + 9
        return (start, end)
    
    def on_scroll(self, controller, dx, dy):
        """Handle scroll events to switch workspaces"""
        # Get current active workspace
        active_workspace = self.hyprland.get_active_workspace()
        if not active_workspace:
            return False
            
        current_id = active_workspace.get("id")
        if current_id is None:
            return False
            
        # Determine direction based on vertical scroll (dy)
        # Scrolling up (negative dy) = previous workspace
        # Scrolling down (positive dy) = next workspace
        if dy < 0:
            # Scroll up, go to previous workspace
            target_id = max(1, current_id - 1)
        else:
            # Scroll down, go to next workspace
            target_id = current_id + 1
        
        # Only switch if the target is different
        if target_id != current_id:
            print(f"Scrolling to workspace {target_id}")
            self.hyprland.switch_to_workspace(target_id)
            
        # Return True to mark the event as handled
        return True
        
    def setup_workspace_indicators(self):
        """Create buttons for the current range of workspaces"""
        # Clear existing buttons
        # GTK 4 pattern: get first child, then iterate through siblings
        child = self.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.remove(child)
            child = next_child
        
        self.workspace_buttons = {}
        
        # Create buttons for current range
        start, end = self.current_range
        for i in range(start, end + 1):
            button = Gtk.Button(label=str(i))
            button.set_size_request(18, 18)  # Smaller button size
            
            # Add CSS classes for styling
            button.add_css_class("workspace-button")
            button.add_css_class(f"workspace-{i}")
            
            # Connect click handler
            button.connect("clicked", self.on_workspace_clicked, i)
            
            # Add to container
            self.append(button)
            self.workspace_buttons[i] = button
            
            # Add basic styling to button
            context = button.get_style_context()
            css_provider = Gtk.CssProvider()
            css = """
            .workspace-button {
                border-radius: 3px;  /* Smaller radius */
                font-weight: bold;
                font-size: 10px;     /* Smaller font */
                padding: 2px;        /* Reduced padding */
                background: transparent;
                color: gray;
                min-width: 0;        /* Allow button to shrink */
                min-height: 0;
            }
            
            .workspace-button.active {
                color: black;
                background-color: white;
            }
            
            .workspace-button.has-windows {
                color: white;
            }
            
            .workspace-button.active.has-windows {
                color: black;
            }
            """
            css_provider.load_from_data(css.encode())
            context.add_provider(css_provider, 600)  # Priority
    
    def update_workspaces(self, *args):
        """Update workspace indicators based on Hyprland state"""
        workspaces = self.hyprland.get_workspaces()
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        # Check if we need to change the displayed range
        if active_id:
            new_range = self.get_workspace_range(active_id)
            if new_range != self.current_range:
                self.current_range = new_range
                self.setup_workspace_indicators()
        
        # Create lookup dict for workspaces with window counts
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in workspaces}
        
        # Update each workspace button
        for i, button in self.workspace_buttons.items():
            # Remove existing state classes
            button.remove_css_class("active")
            button.remove_css_class("has-windows")
            
            # Set active state
            if i == active_id:
                button.add_css_class("active")
            
            # Set has-windows state
            if workspace_dict.get(i, 0) > 0:
                button.add_css_class("has-windows")
    
    def on_workspace_clicked(self, button, workspace_id):
        """Switch to the clicked workspace"""
        self.hyprland.switch_to_workspace(workspace_id)


class WorkspacePanel(Gtk.Box):
    """A container for the workspace indicator with styling"""
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.set_name("workspace-panel")
        self.add_css_class("panel")
        
        # Create frame for the workspace indicator
        frame = Gtk.Frame()
        frame.set_margin_start(2)  # Reduced margins
        frame.set_margin_end(2)
        frame.set_margin_top(2)
        frame.set_margin_bottom(2)
        
        # Add workspace indicator to frame
        self.workspace_indicator = WorkspaceIndicator()
        frame.set_child(self.workspace_indicator)
        
        # Add frame to this container
        self.append(frame)
        
        # Also add scroll handling to the panel itself
        scroll_controller = Gtk.EventControllerScroll()
        # Use proper flags enum instead of integer
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.workspace_indicator.on_scroll)
        self.add_controller(scroll_controller)
        
        # Apply styling
        context = self.get_style_context()
        css_provider = Gtk.CssProvider()
        css = """
        .panel {
            background-color: rgba(30, 30, 30, 0.7);
            border-radius: 4px;  /* Smaller radius */
            padding: 2px;        /* Reduced padding */
        }
        """
        css_provider.load_from_data(css.encode())
        context.add_provider(css_provider, 600)


# For testing the module individually
if __name__ == "__main__":
    def on_activate(app):
        window = Gtk.ApplicationWindow(application=app, title="Workspace Test")
        window.set_default_size(600, 100)
        
        # Create workspace panel
        workspace_panel = WorkspacePanel()
        
        # Add to window with some margin
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.append(workspace_panel)
        
        window.set_child(box)
        window.present()
    
    # Create and run app
    app = Gtk.Application(application_id="com.example.workspace")
    app.connect("activate", on_activate)
    app.run(None)
