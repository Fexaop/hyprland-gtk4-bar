import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GObject, GLib
import math

class CustomProgressBar(Gtk.Box):
    __gsignals__ = {
        'value-changed': (GObject.SIGNAL_RUN_FIRST, None, (float,)),
    }
    
    def __init__(self, name, initial_fraction=0.0, width=150, height=10):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_name(name)
        self._fraction = initial_fraction
        self._target_fraction = initial_fraction
        self._animation_start_fraction = initial_fraction
        self._animation_start_time = 0
        self._animation_duration = 200  # milliseconds
        self._animation_timeout_id = None
        self._width = width  # Store custom width
        self._height = height  # Store custom height
        
        # Create inner box for progress
        self.inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.inner_box.set_name(f"{name}-inner")
        self.append(self.inner_box)
        
        # Set up event controllers on the outer box
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self.on_drag_begin)
        drag.connect("drag-update", self.on_drag_update)
        self.add_controller(drag)
        
        click = Gtk.GestureClick()
        click.connect("pressed", self.on_click_pressed)
        self.add_controller(click)
        
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self.on_scroll)
        self.add_controller(scroll)
        
        # Initialize size with custom width and height
        self.set_size_request(self._width, self._height)
        self.update_size()
    
    def _ease_out_cubic(self, t):
        """Cubic ease-out animation curve for smooth deceleration"""
        return 1 - math.pow(1 - t, 3)
    
    def _animate_step(self):
        """Single step of the animation"""
        current_time = GLib.get_monotonic_time() / 1000  # Convert to milliseconds
        elapsed = current_time - self._animation_start_time
        
        if elapsed >= self._animation_duration:
            # Animation complete
            self._fraction = self._target_fraction
            self.update_size()
            self.queue_draw()
            self._animation_timeout_id = None
            return False  # Stop the animation
        
        # Calculate progress (0 to 1)
        progress = elapsed / self._animation_duration
        
        # Apply easing function
        eased_progress = self._ease_out_cubic(progress)
        
        # Interpolate between start and target fractions
        self._fraction = self._animation_start_fraction + (
            self._target_fraction - self._animation_start_fraction
        ) * eased_progress
        
        self.update_size()
        self.queue_draw()
        return True  # Continue animation
    
    def _start_animation(self, target_fraction):
        """Start smooth animation to target fraction"""
        # Stop any existing animation
        if self._animation_timeout_id:
            GLib.source_remove(self._animation_timeout_id)
            self._animation_timeout_id = None
        
        # Set up animation parameters
        self._animation_start_fraction = self._fraction
        self._target_fraction = target_fraction
        self._animation_start_time = GLib.get_monotonic_time() / 1000
        
        # Start animation loop (60 FPS)
        self._animation_timeout_id = GLib.timeout_add(16, self._animate_step)
    
    def update_size(self):
        """Update the inner box width based on the current fraction."""
        allocation = self.get_allocation()
        total_width = allocation.width if allocation.width > 0 else self._width
        inner_width = int(self._fraction * total_width)
        self.inner_box.set_size_request(inner_width, self._height)  # Use custom height
    
    def set_fraction(self, fraction, animate=True):
        """Set the progress fraction with optional animation."""
        target_fraction = max(0, min(1, fraction))
        
        if animate and abs(target_fraction - self._fraction) > 0.001:
            self._start_animation(target_fraction)
        else:
            # Immediate update (no animation)
            self._fraction = target_fraction
            self._target_fraction = target_fraction
            self.update_size()
            self.queue_draw()
    
    def set_fraction_immediate(self, fraction):
        """Set fraction immediately without animation (for user interactions)"""
        self.set_fraction(fraction, animate=False)
    
    def get_fraction(self):
        """Get the current progress fraction."""
        return self._fraction
    
    def get_target_fraction(self):
        """Get the target fraction (useful during animations)"""
        return self._target_fraction
    
    def on_drag_begin(self, gesture, start_x, start_y):
        """Store the starting x position for drag."""
        self.start_x = start_x
        # Stop animation during user interaction
        if self._animation_timeout_id:
            GLib.source_remove(self._animation_timeout_id)
            self._animation_timeout_id = None
    
    def on_drag_update(self, gesture, x, y):
        """Update progress based on drag position."""
        allocation = self.get_allocation()
        width = allocation.width
        if width > 0:
            current_x = self.start_x + x
            fraction = current_x / width
            fraction = max(0, min(1, fraction))
            self.set_fraction_immediate(fraction)
            self.emit("value-changed", fraction)
    
    def on_click_pressed(self, gesture, n_press, x, y):
        """Set progress based on click position."""
        allocation = self.get_allocation()
        width = allocation.width
        if width > 0:
            fraction = x / width
            fraction = max(0, min(1, fraction))
            self.set_fraction_immediate(fraction)
            self.emit("value-changed", fraction)
    
    def on_scroll(self, controller, dx, dy):
        """Adjust progress based on scroll direction."""
        fraction_change = -dy * 0.05
        new_fraction = self._fraction + fraction_change
        new_fraction = max(0, min(1, new_fraction))
        self.set_fraction_immediate(new_fraction)
        self.emit("value-changed", new_fraction)
        return True