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
gi.require_version('AstalTray', '0.1')
from gi.repository import Gtk, GLib, Gdk, GObject, Gio
from gi.repository import AstalTray as Tray

# Define SYNC constant
SYNC = GObject.BindingFlags.SYNC_CREATE

# Add CSS provider for styling
def setup_css():
    css_provider = Gtk.CssProvider()
    # CSS now defined in main.css file
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    return css_provider

class SysTray(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(spacing=5)  # No spacing between icons
        self.set_css_classes(["SysTray"])
        self.items = {}
        self.current_popover = None
        self.switch_pending = False  # Flag to track menu switching
        
        # Make the tray focusable
        self.set_can_focus(True)
        
        # Add key controller to the tray
        key_controller = Gtk.EventControllerKey.new()
        self.add_controller(key_controller)
        
        def on_key_pressed(controller, keyval, keycode, state):
            if keyval == Gdk.KEY_Escape and self.current_popover:
                self.current_popover.popdown()
                return True
            return False
        
        key_controller.connect("key-pressed", on_key_pressed)
        
        tray = Tray.get_default()
        tray.connect("item_added", self.add_item)
        tray.connect("item_removed", self.remove_item)

    def add_item(self, _: Tray.Tray, id: str):
        if id in self.items:
            return

        item = Tray.get_default().get_item(id)
        
        btn = Gtk.Button()
        btn.set_visible(True)
        btn.set_has_frame(False)
        btn.set_can_focus(True)
        
        icon = Gtk.Image()
        icon.set_visible(True)
        icon.set_size_request(22, 22)

        item.bind_property("tooltip-markup", btn, "tooltip-markup", SYNC)
        item.bind_property("gicon", icon, "gicon", SYNC)
        
        btn.menu_model = None
        
        def on_menu_model_changed(*args):
            btn.menu_model = item.get_property("menu-model")
            
        item.connect("notify::menu-model", on_menu_model_changed)
        btn.menu_model = item.get_property("menu-model")
        
        btn.insert_action_group("dbusmenu", item.get_action_group())
        
        def on_action_group(*args):
            btn.insert_action_group("dbusmenu", item.get_action_group())

        item.connect("notify::action-group", on_action_group)
        
        # Override button click handler instead of using a gesture
        # This is more reliable for repeated clicks
        btn.connect("clicked", lambda button: GLib.idle_add(self._activate_tray_item, item))
        
        # Store a reference to the item in the button for later use
        btn.tray_item = item
        
        # Right-click gesture 
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(3)
        
        def on_right_click(gesture, n_press, x, y):
            if btn.menu_model:
                # Store reference to previous popover and button
                prev_popover = self.current_popover
                
                # Set switching flag to true
                self.switch_pending = True
                
                # Reset current_popover first to avoid conflicts
                self.current_popover = None
                
                # Function to open the new popover after delay
                def open_new_popover():
                    if not self.switch_pending:
                        return False  # Operation was cancelled
                    
                    # Create the new popover
                    popover = Gtk.PopoverMenu.new_from_model(btn.menu_model)
                    popover.set_parent(btn)
                    popover.set_css_classes(["dark-menu","pop-box"])
                    popover.set_offset(0, 5)
                    popover.set_position(Gtk.PositionType.BOTTOM)
                    popover.set_autohide(True)
                    popover.set_has_arrow(False)
                    popover.set_can_focus(True)
                    
                    # Ensure we have no padding from the popover itself
                    popover.set_size_request(0, 0)
                    popover.set_vexpand(False)
                    popover.set_valign(Gtk.Align.START)
                    
                    # Apply more adjustments when content is available
                    def modify_popover_content():
                        content = popover.get_child()
                        if content:
                            # Remove any padding/borders from content elements
                            content.set_margin_start(0)
                            content.set_margin_end(0)
                            content.set_margin_top(0)
                            content.set_margin_bottom(0)
                            content.set_css_classes(["dark-menu"])
                            
                            # Try to find subchildren that might have padding
                            if isinstance(content, Gtk.Box):
                                for child in content:
                                    child.set_margin_start(0)
                                    child.set_margin_end(0)
                                    child.set_margin_top(0)
                                    child.set_margin_bottom(0)
                        return False
                    
                    # Add hook to modify content after popover is created
                    GObject.timeout_add(10, modify_popover_content)
                    
                    # Add key controller to the popover
                    popover_key_controller = Gtk.EventControllerKey.new()
                    popover.add_controller(popover_key_controller)
                    
                    def on_popover_key_pressed(controller, keyval, keycode, state):
                        if keyval == Gdk.KEY_Escape:
                            popover.popdown()
                            return True
                        return False
                    
                    popover_key_controller.connect("key-pressed", on_popover_key_pressed)
                    
                    # Set as current popover before displaying
                    self.current_popover = popover
                    self.switch_pending = False  # Reset the switching flag
                    
                    # Show the popover
                    popover.popup()
                    popover.present()
                    popover.grab_focus()
                    
                    # Improved sizing approach
                    def on_map(widget):
                        # Wait for content to be fully realized
                        GObject.timeout_add(50, adjust_popover_size)
                    
                    def adjust_popover_size():
                        content = popover.get_child()
                        if content:
                            # Get all menu items and calculate total height
                            # Try to count actual menu items
                            menu_item_count = 0
                            if hasattr(btn.menu_model, 'get_n_items'):
                                menu_item_count = btn.menu_model.get_n_items()
                            
                            # If we have menu items, calculate a height based on reasonable estimates
                            if menu_item_count > 0:
                                # Each menu item is approximately 24px high (adjust if needed)
                                item_height = 24
                                total_height = menu_item_count * item_height
                                popover.set_size_request(-1, total_height)
                            else:
                                # Fallback to measuring content
                                min_size, nat_size = content.measure(Gtk.Orientation.VERTICAL, -1)
                                if nat_size > 0:
                                    popover.set_size_request(-1, nat_size)
                            
                            # Apply zero margins again after sizing
                            modify_popover_content()
                        return False  # Don't call again
                    
                    popover.connect("map", on_map)
                    
                    def on_popup_closed(*args):
                        if self.current_popover == popover:
                            self.current_popover = None
                        popover.popdown()
                    
                    popover.connect("closed", on_popup_closed)
                    return False
                
                # Close previous popover if it exists
                if prev_popover:
                    prev_popover.popdown()
                    # Increase the delay to ensure proper event handling
                    GObject.timeout_add(150, open_new_popover)
                else:
                    # No previous popover, can open immediately
                    GObject.timeout_add(10, open_new_popover)
                    
        click_gesture.connect("pressed", on_right_click)
        btn.add_controller(click_gesture)

        btn.set_child(icon)
        self.append(btn)
        self.items[id] = btn

    def remove_item(self, _: Tray.Tray, id: str):
        if id in self.items:
            btn = self.items[id]
            self.remove(btn)
            del self.items[id]
    
    def _activate_tray_item(self, item):
        """Activate tray item with current pointer position."""
        try:
            # Get the current pointer position relative to screen
            display = Gdk.Display.get_default()
            seat = display.get_default_seat()
            pointer = seat.get_pointer()
            
            # For Wayland compatibility, use 0,0 which lets the item
            # determine proper coordinates internally
            x, y = 0, 0
            
            # Activate using these coordinates
            print(f"Activating tray item at ({x}, {y})")
            item.activate(x, y)
            
        except Exception as e:
            print(f"Error activating tray item: {e}")
        
        return False  # Don't call again
