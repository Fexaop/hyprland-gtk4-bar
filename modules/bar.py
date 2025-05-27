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
from widgets.corner import Corner
from modules.workspace import WorkspaceBar
from modules.systray import SysTray, setup_css
from service.audio import Audio  # Import the Audio service
from service.backlight import BacklightService  # Import the Backlight service

class Bar(Gtk.ApplicationWindow):
    """A LayerShell window that contains the workspace bar with colored backgrounds and scroll logging."""
    
    def __init__(self, application):
        super().__init__(application=application)
        
        # Set up the window
        self.set_name("bar")
        self.set_resizable(True)
        self.set_decorated(False)
        
        # Initialize LayerShell
        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, LayerShell.Layer.BOTTOM)
        LayerShell.set_namespace(self, "bar")
        
        # Anchor to top, left, and right for full width
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
        
        # Set zero margins on left and right
        LayerShell.set_margin(self, LayerShell.Edge.LEFT, 0)
        LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 0)
        LayerShell.set_margin(self, LayerShell.Edge.TOP, 0)
        
        # Set height and exclusive zone
        bar_height = 40
        LayerShell.set_exclusive_zone(self, bar_height)
        
        # Set size based on monitor width
        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else []
        monitor = monitors[0] if len(monitors) > 0 else None
        screen_width = monitor.get_geometry().width if monitor else -1
        self.set_size_request(screen_width, bar_height)
        
        # Initialize services
        self._init_services()
        
        # Create main horizontal box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_name("bar-box")
        main_box.set_valign(Gtk.Align.CENTER)
        main_box.set_vexpand(True)
        main_box.set_hexpand(True)
        
        # Create left box (blue background)
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.set_name("left-box")
        left_box.set_hexpand(True)
        left_box.set_vexpand(True)
        
        # Add scroll controller for left box (brightness control)
        left_scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        left_scroll_controller.connect("scroll", self.on_brightness_scroll)
        left_box.add_controller(left_scroll_controller)
        
        # Add workspace bar
        workspace_bar = WorkspaceBar()
        workspace_bar.set_size_request(-1, bar_height)
        workspace_bar.set_valign(Gtk.Align.CENTER)
        left_box.append(workspace_bar)
        
        # Add left corner
        self.left_corner = Corner("top-left")
        self.left_corner.set_size_request(20, 30)
        self.left_corner.set_halign(Gtk.Align.START)
        self.left_corner.set_valign(Gtk.Align.START)
        left_box.append(self.left_corner)
        
        # Create right box (red background)
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        right_box.set_name("right-box")
        right_box.set_hexpand(True)
        right_box.set_vexpand(True)
        
        # Add scroll controller for right box (volume control)
        right_scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        right_scroll_controller.connect("scroll", self.on_volume_scroll)
        right_box.add_controller(right_scroll_controller)
        
        # Add expanding spacer to push content right
        right_spacer = Gtk.Box()
        right_spacer.set_hexpand(True)
        right_box.append(right_spacer)
        
        # Add right corner
        self.right_corner = Corner("top-right")
        self.right_corner.set_size_request(20, 30)
        self.right_corner.set_halign(Gtk.Align.END)
        self.right_corner.set_valign(Gtk.Align.START)
        right_box.append(self.right_corner)
        
        # Add system tray
        systray = SysTray()
        systray.set_size_request(-1, bar_height)
        systray.set_valign(Gtk.Align.CENTER)
        right_box.append(systray)
        
        # Add boxes to main box
        main_box.append(left_box)
        main_box.append(right_box)
        
        # Set main box as window's child
        self.set_child(main_box)
    
    def _init_services(self):
        """Initialize backlight and audio services"""
        # Initialize Backlight Service
        try:
            self.backlight_service = BacklightService.get_default()
        except Exception as e:
            print(f"Failed to initialize backlight service: {e}")
            self.backlight_service = None
        
        # Initialize Audio Service
        try:
            self.audio_service = Audio()
        except Exception as e:
            print(f"Failed to initialize audio service: {e}")
            self.audio_service = None
    
    def on_brightness_scroll(self, controller, dx, dy):
        """Handle scroll events for brightness control on left box."""
        if not self.backlight_service or not self.backlight_service.available:
            print("Brightness control not available")
            return
        
        # Determine scroll direction and calculate brightness change
        direction = "up" if dy < 0 else "down"
        delta = abs(dy)
        
        # Calculate brightness step (5% per scroll step)
        max_brightness = self.backlight_service.max_brightness
        current_brightness = self.backlight_service.brightness
        step = max(1, int(max_brightness * 0.05))  # 5% step, minimum 1
        
        if direction == "up":
            new_brightness = min(max_brightness, current_brightness + step)
        else:
            new_brightness = max(0, current_brightness - step)
        
        # Set the new brightness
        self.backlight_service.set_brightness(new_brightness)
        
        # Calculate percentage for logging
        percentage = int((new_brightness / max_brightness) * 100) if max_brightness > 0 else 0
    
    def on_volume_scroll(self, controller, dx, dy):
        """Handle scroll events for volume control on right box."""
        if not self.audio_service or not self.audio_service.speaker:
            print("Volume control not available")
            return
        
        # Determine scroll direction and calculate volume change
        direction = "up" if dy < 0 else "down"
        delta = abs(dy)
        
        # Calculate volume step (5% per scroll step)
        current_volume = self.audio_service.speaker.volume  # 0-100 float
        step = 5.0  # 5% step
        
        if direction == "up":
            new_volume = min(100.0, current_volume + step)
        else:
            new_volume = max(0.0, current_volume - step)
        
        # Set the new volume
        self.audio_service.speaker.volume = new_volume
        
        # If volume is being changed and currently muted, unmute
        if self.audio_service.speaker.muted and new_volume > 0:
            self.audio_service.speaker.muted = False
        

# For testing
if __name__ == "__main__":
    app = Gtk.Application(application_id="com.example.bar")
    
    def on_activate(app):
        bar = Bar(app)
        bar.present()
    
    app.connect("activate", on_activate)
    app.run(None)