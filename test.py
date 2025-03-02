#!/usr/bin/env python3

from ctypes import CDLL
import gi

# Load GTK4 Layer Shell
try:
    CDLL('libgtk4-layer-shell.so')
except OSError:
    print("Error: Could not load libgtk4-layer-shell.so. Please ensure gtk4-layer-shell is installed.")
    exit(1)

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('AstalTray', '0.1')
from gi.repository import Gtk, Gio, GObject, Gdk
from gi.repository import Gtk4LayerShell as LayerShell
from gi.repository import AstalTray as Tray

# Define SYNC constant
SYNC = GObject.BindingFlags.SYNC_CREATE

# Add CSS provider for styling the menu with dark theme
def setup_css():
    css_provider = Gtk.CssProvider()
    css_str = """
    window {
        background-color: #000000;
    }
    
    .SysTray {
        background-color: #000000;
        padding: 0;
    }
    
    .SysTray button {
        background: none;
        border: none;
        padding: 0px;
        margin: 0;
        min-height: 22px;
        min-width: 22px;
    }
    
    .SysTray button:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Target specific elements in popovers that might add padding */
    popover {
        color: #ffffff;
        padding: 0;
        margin: 0;
        min-height: 0;
        min-width: 0;
        border: none;
    }
    
    popover contents {
        padding: 0;
        margin: 0;
        min-height: 0;
        border: none;
    }
    
    popover box {
        padding: 0;
        margin: 0;
        min-height: 0;
    }
    
    popover menu {
        padding: 0;
        margin: 0;
        min-height: 0;
        border: none;
    }
    
    popover menuitem {
        padding: 4px 8px;
        margin: 0;
        min-height: 0;
    }
    
    /* Hide arrow */
    popover arrow {
        background-color: black;
    }
    
    /* Extra specificity for the dark menu class */
    .dark-menu, .dark-menu * {
        padding: 0;
        margin: 0;
        min-height: 0;
        border: none;
    }
    
    /* Target GTK's internal menu structure */
    .dark-menu contents {
        padding: 0px;
        background-color: #000000;
        margin: 0;
        color: #ffffff;
        border-radius: 16px;
    }
    .dark-menu box {
        padding: 4px;
    }
    """
    
    css_provider.load_from_string(css_str)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    return css_provider

class SysTray(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(spacing=0)  # No spacing between icons
        self.set_css_classes(["SysTray"])
        self.items = {}
        self.current_popover = None
        
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
        
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(3)
        
        def on_right_click(gesture, n_press, x, y):
            if btn.menu_model:
                if self.current_popover and self.current_popover != None:
                    self.current_popover.popdown()
                    self.current_popover = None

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
                
                # Show the popover
                popover.popup()
                self.current_popover = popover
                
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
                popover.present()
                popover.grab_focus()
                
                def on_popup_closed(*args):
                    if self.current_popover == popover:
                        self.current_popover = None
                    popover.popdown()
                
                popover.connect("closed", on_popup_closed)
                
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

def main():
    app = Gtk.Application(application_id="com.example.SystemTray")
    
    def on_activate(app):
        css_provider = setup_css()
        
        window = Gtk.Window(application=app)
        window.set_title("System Tray Example")
        window.set_can_focus(True)
        
        LayerShell.init_for_window(window)
        LayerShell.set_layer(window, LayerShell.Layer.TOP)
        LayerShell.set_keyboard_mode(window, LayerShell.KeyboardMode.ON_DEMAND)
        
        LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_anchor(window, LayerShell.Edge.LEFT, False)
        LayerShell.set_anchor(window, LayerShell.Edge.BOTTOM, False)
        
        LayerShell.set_margin(window, LayerShell.Edge.TOP, 0)
        LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 0)
        LayerShell.set_exclusive_zone(window, 30)
        
        systray = SysTray()
        systray.set_size_request(-1, 30)
        
        systray.set_margin_start(4)
        systray.set_margin_end(4)
        systray.set_margin_top(4)
        systray.set_margin_bottom(4)
        
        window.set_child(systray)
        window.present()
        window.grab_focus()
    
    app.connect('activate', on_activate)
    app.run(None)

if __name__ == "__main__":
    main()