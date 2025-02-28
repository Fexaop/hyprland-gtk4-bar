import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from service.hyprland import HyprlandService

 # Create a simple GTK application to test the service
class HyprlandTestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.hyprlandtest")
        self.connect("activate", self.on_activate)
        
    def on_activate(self, app):
        window = Gtk.ApplicationWindow(application=app, title="Hyprland Service Test")
        window.set_default_size(600, 400)
        
        # Create a box for layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # Get the hyprland service
        self.hyprland = HyprlandService.get_default()
        
        # Add labels to display info
        self.layout_label = Gtk.Label(label=f"Keyboard Layout: {self.hyprland.get_kb_layout()}")
        box.append(self.layout_label)
        
        self.workspace_label = Gtk.Label(label="Active Workspace: Loading...")
        box.append(self.workspace_label)
        
        self.window_label = Gtk.Label(label="Active Window: Loading...")
        box.append(self.window_label)
        
        # Create a list box to display all workspaces
        workspaces_frame = Gtk.Frame(label="Workspaces")
        workspaces_scroll = Gtk.ScrolledWindow()
        workspaces_scroll.set_vexpand(True)
        workspaces_scroll.set_min_content_height(150)
        
        self.workspaces_list = Gtk.ListBox()
        self.workspaces_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.workspaces_list.connect("row-activated", self.on_workspace_selected)
        
        workspaces_scroll.set_child(self.workspaces_list)
        workspaces_frame.set_child(workspaces_scroll)
        box.append(workspaces_frame)
        
        # Buttons for actions
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        buttons_box.set_homogeneous(True)
        
        switch_button = Gtk.Button(label="Switch Keyboard Layout")
        switch_button.connect("clicked", self.on_switch_clicked)
        buttons_box.append(switch_button)
        
        sync_windows_button = Gtk.Button(label="Sync Active Window")
        sync_windows_button.connect("clicked", self.on_sync_window_clicked)
        buttons_box.append(sync_windows_button)
        
        sync_workspaces_button = Gtk.Button(label="Sync Workspaces")
        sync_workspaces_button.connect("clicked", self.on_sync_workspaces_clicked)
        buttons_box.append(sync_workspaces_button)
        
        # Add toggle button for auto-sync
        auto_sync_button = Gtk.ToggleButton(label="Auto Sync")
        auto_sync_button.set_active(True)
        auto_sync_button.connect("toggled", self.on_auto_sync_toggled)
        buttons_box.append(auto_sync_button)
        
        box.append(buttons_box)
        
        # Connect signals to update the UI
        self.hyprland.connect("notify::kb-layout", self.on_layout_changed)
        self.hyprland.connect("notify::active-workspace", self.on_workspace_changed)
        self.hyprland.connect("notify::active-window", self.on_window_changed)
        
        # Connect to both signals for workspace updates
        self.hyprland.connect("workspaces-changed", self.update_workspaces_list)
        self.hyprland.connect("active-workspace-changed", self.update_workspaces_list)
        
        # Update labels with current info
        self.update_workspace_label()
        self.update_window_label()
        self.update_workspaces_list()
        
        # Handle application shutdown
        window.connect("close-request", self.on_window_close)
        
        window.set_child(box)
        window.present()
    
    def on_layout_changed(self, obj, pspec):
        self.layout_label.set_label(f"Keyboard Layout: {self.hyprland.get_kb_layout()}")
    
    def on_workspace_changed(self, obj, pspec):
        self.update_workspace_label()
        # Highlight the active workspace in the list
        self.update_workspaces_list()
    
    def on_window_changed(self, obj, pspec):
        self.update_window_label()
    
    def update_workspace_label(self):
        workspace = self.hyprland.get_active_workspace()
        if workspace:
            name = workspace.get("name", "Unknown")
            self.workspace_label.set_label(f"Active Workspace: {name}")
    
    def update_window_label(self):
        window = self.hyprland.get_active_window()
        if window:
            title = window.get("title", "Unknown")
            window_class = window.get("class", "Unknown")
            self.window_label.set_label(f"Active Window: {title} ({window_class})")
        else:
            self.window_label.set_label("Active Window: None")
    
    def update_workspaces_list(self, *args):
        """Update the list of workspaces in the UI"""
        print("Updating workspaces list...")  # Debug print
        
        # Clear the list
        while True:
            row = self.workspaces_list.get_row_at_index(0)
            if row is None:
                break
            self.workspaces_list.remove(row)
        
        # Get all workspaces
        workspaces = self.hyprland.get_workspaces()
        print(f"Current workspaces: {[{'id': ws.get('id'), 'windows': ws.get('windows')} for ws in workspaces]}")  # More compact debug
        
        active_ws = self.hyprland.get_active_workspace()
        active_id = active_ws.get("id") if active_ws else None
        
        # Add each workspace to the list
        for ws in workspaces:
            ws_id = ws.get("id")
            name = ws.get("name", "Unknown")
            monitor = ws.get("monitor", "Unknown")
            windows = ws.get("windows", 0)
            
            # Create a row for the workspace
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            box.set_margin_start(5)
            box.set_margin_end(5)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            
            # Indicate active workspace with an arrow
            if ws_id == active_id:
                active_indicator = Gtk.Label(label="➤")
                box.append(active_indicator)
            
            # Add window count indicator with color based on count
            window_count = Gtk.Label(label=f"[{windows}]")
            if windows > 0:
                window_count.add_css_class("warning")  # Add CSS class for styling
            box.append(window_count)
            
            # Add main workspace information
            label = Gtk.Label(label=f"ID: {ws_id} | Name: {name} | Monitor: {monitor}")
            label.set_halign(Gtk.Align.START)
            box.append(label)
            
            # Store workspace ID as a Python attribute instead of using set_data
            row = Gtk.ListBoxRow()
            row.set_child(box)
            row.workspace_id = ws_id  # Use Python attribute instead of set_data
            
            self.workspaces_list.append(row)
    
    def on_workspace_selected(self, list_box, row):
        # Use the Python attribute instead of get_data
        ws_id = getattr(row, 'workspace_id', None)
        if ws_id is not None:
            self.hyprland.switch_to_workspace(ws_id)
    
    def on_switch_clicked(self, button):
        self.hyprland.switch_kb_layout()
    
    def on_sync_window_clicked(self, button):
        # Call the private method using name mangling syntax
        self.hyprland._sync_active_window()
    
    def on_sync_workspaces_clicked(self, button):
        # Call the private method using name mangling syntax
        self.hyprland._sync_workspaces()
    
    def on_auto_sync_toggled(self, button):
        """Toggle auto-sync feature."""
        is_active = button.get_active()
        self.hyprland.enable_auto_sync(is_active)
        if is_active:
            print("Auto sync enabled")
        else:
            print("Auto sync disabled")
    
    def on_window_close(self, window):
        """Clean up resources when window is closed."""
        hyprland = HyprlandService.get_default()
        hyprland.cleanup()

# Run the application
app = HyprlandTestApp()
app.run(None)