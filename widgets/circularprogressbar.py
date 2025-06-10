import gi
import math
from typing import Literal, Optional, List

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GObject, Graphene, Gsk, GdkPixbuf


class CircularProgressBar(Gtk.Widget):
    """A circular progress bar widget for GTK4 that works with angles directly"""
    
    # GObject properties
    __gtype_name__ = 'CircularProgressBar'
    
    # Custom signals - Fixed deprecation warnings
    __gsignals__ = {
        'value-changed': (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        'angle-changed': (GObject.SignalFlags.RUN_FIRST, None, (float,)),  # new angle signal
        'clicked': (GObject.SignalFlags.RUN_FIRST, None, (float,)),  # angle at click
        'dragged': (GObject.SignalFlags.RUN_FIRST, None, (float,)),  # new angle
    }
    
    def __init__(
        self,
        angle: float = 0.0,  # Current angle in degrees
        min_angle: float = -180.0,  # Minimum angle (supports negative)
        max_angle: float = 180.0,   # Maximum angle (supports negative)
        start_angle: float = -90.0,
        end_angle: float = 270.0,
        line_width: int = 4,
        line_style: Literal["butt", "round", "square"] = "round",
        pie: bool = False,
        invert: bool = False,
        child_spacing: int = 10,
        snap_to_angles: Optional[List[float]] = None,  # Optional angle snapping
        snap_threshold: float = 5.0,  # Degrees within which to snap
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Internal properties
        self._angle = angle
        self._min_angle = min_angle
        self._max_angle = max_angle
        self._start_angle = start_angle
        self._end_angle = end_angle
        self._line_width = line_width
        self._line_style = line_style
        self._pie = pie
        self._invert = invert
        self._child_spacing = child_spacing
        self._snap_to_angles = snap_to_angles or []
        self._snap_threshold = snap_threshold
        
        # Child widget
        self._child: Optional[Gtk.Widget] = None
        
        # Interaction state
        self._is_dragging = False
        self._drag_start_angle = 0.0
        self._last_mouse_angle = 0.0
        
        # Store widget dimensions
        self._width = 0
        self._height = 0
        
        # Set default size request
        self.set_size_request(100, 100)
        
        # Set up interaction controllers
        self._setup_interaction()
    
    # Property getters and setters
    @GObject.Property(type=float, default=-180.0)
    def min_angle(self) -> float:
        return self._min_angle
    
    @min_angle.setter
    def min_angle(self, value: float):
        if value != self._min_angle:
            self._min_angle = self._normalize_angle(value)
            self._angle = self._clamp_angle(self._angle)
            self.queue_draw()
    
    @GObject.Property(type=float, default=180.0)
    def max_angle(self) -> float:
        return self._max_angle
    
    @max_angle.setter
    def max_angle(self, value: float):
        if value != self._max_angle:
            self._max_angle = self._normalize_angle(value)
            self._angle = self._clamp_angle(self._angle)
            self.queue_draw()
    
    @GObject.Property(type=float, default=0.0)
    def angle(self) -> float:
        return self._angle
    
    @angle.setter
    def angle(self, value: float):
        new_angle = self._clamp_angle(self._normalize_angle(value))
        if abs(new_angle - self._angle) > 0.001:
            self._angle = new_angle
            self.queue_draw()
            self.emit("angle-changed", self._angle)
    
    @GObject.Property(type=bool, default=False)
    def pie(self) -> bool:
        return self._pie
    
    @pie.setter
    def pie(self, value: bool):
        if value != self._pie:
            self._pie = value
            self.queue_draw()
    
    @GObject.Property(type=int, default=4)
    def line_width(self) -> int:
        return self._line_width
    
    @line_width.setter
    def line_width(self, value: int):
        if value != self._line_width:
            self._line_width = max(1, value)
            self.queue_draw()
    
    @GObject.Property(type=float, default=-90.0)
    def start_angle(self) -> float:
        return self._start_angle
    
    @start_angle.setter
    def start_angle(self, value: float):
        if value != self._start_angle:
            self._start_angle = self._normalize_angle(value)
            self.queue_draw()
    
    @GObject.Property(type=float, default=270.0)
    def end_angle(self) -> float:
        return self._end_angle
    
    @end_angle.setter
    def end_angle(self, value: float):
        if value != self._end_angle:
            self._end_angle = self._normalize_angle(value)
            self.queue_draw()
    
    @GObject.Property(type=bool, default=False)
    def invert(self) -> bool:
        return self._invert
    
    @invert.setter
    def invert(self, value: bool):
        if value != self._invert:
            self._invert = value
            self.queue_draw()
    
    @GObject.Property(type=int, default=10)
    def child_spacing(self) -> int:
        return self._child_spacing
    
    @child_spacing.setter
    def child_spacing(self, value: int):
        if value != self._child_spacing:
            self._child_spacing = max(0, value)
            self.queue_resize()
    
    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to -180 to 180 range"""
        while angle > 180:
            angle -= 360
        while angle <= -180:
            angle += 360
        return angle
    
    def _clamp_angle(self, angle: float) -> float:
        """Clamp angle between min_angle and max_angle, handling negative values properly"""
        # Normalize the angle first
        angle = self._normalize_angle(angle)
        min_norm = self._normalize_angle(self._min_angle)
        max_norm = self._normalize_angle(self._max_angle)
        
        # Handle case where range crosses -180/180 boundary
        if min_norm > max_norm:
            # Range crosses the boundary (e.g., min=170, max=-170)
            if angle >= min_norm or angle <= max_norm:
                return angle
            else:
                # Find which boundary is closer
                dist_to_min = min(abs(angle - min_norm), abs(angle - min_norm + 360), abs(angle - min_norm - 360))
                dist_to_max = min(abs(angle - max_norm), abs(angle - max_norm + 360), abs(angle - max_norm - 360))
                return min_norm if dist_to_min < dist_to_max else max_norm
        else:
            # Normal range
            return max(min_norm, min(max_norm, angle))
    
    def _apply_angle_snapping(self, angle: float) -> float:
        """Apply snapping to predefined angles if enabled"""
        if not self._snap_to_angles:
            return angle
        
        # Find the closest snap angle
        closest_snap = None
        min_distance = float('inf')
        
        for snap_angle in self._snap_to_angles:
            snap_norm = self._normalize_angle(snap_angle)
            distance = min(
                abs(angle - snap_norm),
                abs(angle - snap_norm + 360),
                abs(angle - snap_norm - 360)
            )
            
            if distance < min_distance and distance <= self._snap_threshold:
                min_distance = distance
                closest_snap = snap_norm
        
        return closest_snap if closest_snap is not None else angle
    
    def get_line_cap_style(self) -> str:
        """Convert line style string to Cairo equivalent"""
        style_map = {
            "butt": "butt",
            "round": "round", 
            "square": "square"
        }
        return style_map.get(self._line_style, "round")
    
    def _setup_interaction(self):
        """Set up mouse and touch interaction controllers"""
        # Drag controller
        self.drag_controller = Gtk.GestureDrag()
        self.drag_controller.connect("drag-begin", self._on_drag_begin)
        self.drag_controller.connect("drag-update", self._on_drag_update)
        self.drag_controller.connect("drag-end", self._on_drag_end)
        self.add_controller(self.drag_controller)
        
        # Click controller
        self.click_controller = Gtk.GestureClick()
        self.click_controller.connect("pressed", self._on_click_pressed)
        self.add_controller(self.click_controller)
        
        # Scroll controller for fine adjustments
        self.scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        self.scroll_controller.connect("scroll", self._on_scroll)
        self.add_controller(self.scroll_controller)
    
    def _calculate_angle_from_point(self, x: float, y: float) -> float:
        """Calculate angle in degrees (0°=top, 90°=right, 180°=bottom, -90°=left)
           from the widget's center to the given coordinates.
        """
        center_x = self._width / 2
        center_y = self._height / 2

        dx = x - center_x
        dy = y - center_y

        # math.atan2(dy, dx) returns angle in radians:
        #   0 rad for positive X-axis (to the right)
        #   PI/2 rad for positive Y-axis (downwards, as dy = y - center_y)
        #   -PI/2 rad for negative Y-axis (upwards)
        #   Result is in range [-PI, PI]
        math_angle_rad = math.atan2(dy, dx)
        math_angle_deg = math.degrees(math_angle_rad)
        # math_angle_deg is now in range [-180, 180]:
        #   0° means to the right.
        #   90° means downwards.
        #   -90° means upwards.
        #   180° or -180° means to the left.

        # Convert to the widget's angle system where 0° is at the top,
        # 90° is to the right, 180° is at the bottom, and -90° (or 270°) is to the left.
        # This requires shifting the math_angle_deg.
        # If math_angle_deg = -90° (up), we want widget_angle = 0° (top).
        # If math_angle_deg = 0° (right), we want widget_angle = 90° (right).
        # If math_angle_deg = 90° (down), we want widget_angle = 180° (bottom).
        # If math_angle_deg = 180° (left), we want widget_angle = 270°, which normalizes to -90° (left).
        # So, widget_angle = math_angle_deg + 90°.
        widget_angle_deg = math_angle_deg + 90

        return self._normalize_angle(widget_angle_deg)
    
    def _is_point_on_progress_bar(self, x: float, y: float) -> bool:
        """Check if a point is roughly on the progress bar circle"""
        center_x = self._width / 2
        center_y = self._height / 2
        radius = min(self._width, self._height) / 2 - self._line_width / 2
        
        # Calculate distance from center
        dx = x - center_x
        dy = y - center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Allow some tolerance around the circle (±line_width)
        tolerance = self._line_width * 1.5
        return abs(distance - radius) <= tolerance
    
    def _on_drag_begin(self, gesture, start_x, start_y):
        """Handle start of drag interaction"""
        if self._is_point_on_progress_bar(start_x, start_y):
            self._is_dragging = True
            self._drag_start_angle = self._calculate_angle_from_point(start_x, start_y)
            self._last_mouse_angle = self._drag_start_angle
            
            print(f"[CircularProgressBar] Drag started at angle: {self._drag_start_angle:.1f}°, "
                  f"current angle: {self._angle:.1f}°")
        else:
            # If not on the progress bar, treat as a click to set angle
            mouse_angle = self._calculate_angle_from_point(start_x, start_y)
            self._set_angle_from_mouse(mouse_angle)
    
    def _on_drag_update(self, gesture, offset_x, offset_y):
        """Handle drag movement - follow the circular path"""
        if not self._is_dragging:
            return
            
        # Get current position
        success, start_x, start_y = gesture.get_start_point()
        if not success:
            return
        
        current_x = start_x + offset_x
        current_y = start_y + offset_y
        
        # Calculate current mouse angle
        current_mouse_angle = self._calculate_angle_from_point(current_x, current_y)
        
        # Calculate the angular difference since last update
        angle_diff = self._calculate_angle_difference(self._last_mouse_angle, current_mouse_angle)
        
        # Apply the angular difference to our current angle
        new_angle = self._angle + angle_diff
        new_angle = self._apply_angle_snapping(new_angle)
        new_angle = self._clamp_angle(new_angle)
        
        # Only update if the angle changed meaningfully
        if abs(new_angle - self._angle) > 0.1:
            old_angle = self._angle
            self._angle = new_angle
            self.queue_draw()
            
            print(f"[CircularProgressBar] Dragging: mouse {current_mouse_angle:.1f}°, "
                  f"diff: {angle_diff:.1f}°, angle: {old_angle:.1f}° → {self._angle:.1f}°")
            
            # Emit signals
            self.emit("angle-changed", self._angle)
            self.emit("dragged", self._angle)
        
        # Update last mouse angle for next iteration
        self._last_mouse_angle = current_mouse_angle
    
    def _calculate_angle_difference(self, from_angle: float, to_angle: float) -> float:
        """Calculate the shortest angular difference between two angles"""
        diff = to_angle - from_angle
        
        # Normalize to -180 to 180 range
        while diff > 180:
            diff -= 360
        while diff <= -180:
            diff += 360
            
        return diff
    
    def _set_angle_from_mouse(self, mouse_angle: float):
        """Set the angle directly based on mouse position"""
        # Map mouse angle to our angle range
        new_angle = self._apply_angle_snapping(mouse_angle)
        new_angle = self._clamp_angle(new_angle)
        
        old_angle = self._angle
        self._angle = new_angle
        self.queue_draw()
        
        print(f"[CircularProgressBar] Set angle from mouse: {mouse_angle:.1f}° → {new_angle:.1f}°")
        
        # Emit signals
        self.emit("angle-changed", self._angle)
    
    def _on_drag_end(self, gesture, offset_x, offset_y):
        """Handle end of drag interaction"""
        if self._is_dragging:
            print(f"[CircularProgressBar] Drag ended, final angle: {self._angle:.1f}°")
            self._is_dragging = False
    
    def _on_click_pressed(self, gesture, n_press, x, y):
        """Handle click interaction - set angle based on click position"""
        if self._is_dragging:
            return  # Don't process clicks during drag
            
        mouse_angle = self._calculate_angle_from_point(x, y)
        self._set_angle_from_mouse(mouse_angle)
        
        # Emit click signal with the angle
        self.emit("clicked", mouse_angle)
    
    def _on_scroll(self, controller, dx, dy):
        """Handle scroll wheel interaction"""
        # Calculate scroll increment (5° per scroll step)
        increment = -dy * 5.0  # degrees
        
        old_angle = self._angle
        new_angle = self._apply_angle_snapping(self._angle + increment)
        new_angle = self._clamp_angle(new_angle)
        
        if abs(new_angle - old_angle) > 0.1:
            self._angle = new_angle
            self.queue_draw()
            
            print(f"[CircularProgressBar] Scrolled dy={dy:.2f}, "
                  f"angle: {old_angle:.1f}° → {new_angle:.1f}°")
            
            self.emit("angle-changed", new_angle)
        
        return True  # Event handled
    
    def set_angle(self, angle: float):
        """Programmatically set the angle"""
        self.angle = angle
    
    def get_angle(self) -> float:
        """Get the current angle"""
        return self._angle
    
    def set_angle_range(self, min_angle: float, max_angle: float):
        """Set the allowed angle range"""
        self._min_angle = self._normalize_angle(min_angle)
        self._max_angle = self._normalize_angle(max_angle)
        self._angle = self._clamp_angle(self._angle)
        self.queue_draw()
    
    def get_angle_range(self) -> tuple[float, float]:
        """Get the current angle range"""
        return (self._min_angle, self._max_angle)
    
    def set_snap_angles(self, angles: List[float], threshold: float = 5.0):
        """Set angles to snap to during interaction"""
        self._snap_to_angles = [self._normalize_angle(a) for a in angles]
        self._snap_threshold = threshold
    
    def clear_snap_angles(self):
        """Clear angle snapping"""
        self._snap_to_angles = []
    
    # Legacy compatibility methods (convert angle to normalized value)
    @property
    def value(self) -> float:
        """Get angle as normalized value (0.0 to 1.0)"""
        if self._max_angle == self._min_angle:
            return 0.0
        
        angle_range = self._max_angle - self._min_angle
        if angle_range < 0:
            angle_range += 360
        
        current_offset = self._angle - self._min_angle
        if current_offset < 0:
            current_offset += 360
            
        return current_offset / angle_range
    
    @value.setter 
    def value(self, value: float):
        """Set angle from normalized value (0.0 to 1.0)"""
        value = max(0.0, min(1.0, value))
        
        angle_range = self._max_angle - self._min_angle
        if angle_range < 0:
            angle_range += 360
            
        new_angle = self._min_angle + (value * angle_range)
        self.angle = new_angle
    
    def set_child(self, child: Optional[Gtk.Widget]):
        """Set a child widget"""
        if self._child:
            self._child.unparent()
        
        self._child = child
        if child:
            child.set_parent(self)
    
    def get_child(self) -> Optional[Gtk.Widget]:
        """Get the child widget"""
        return self._child
    
    def do_measure(self, orientation: Gtk.Orientation, for_size: int) -> tuple:
        """Measure the widget size"""
        # Request a square size
        min_size = max(self._line_width * 2 + self._child_spacing * 2 + 20, 50)
        nat_size = 100  # Natural size
        
        if self._child:
            child_min, child_nat, _, _ = self._child.measure(orientation, for_size)
            child_with_spacing = child_min + self._line_width + self._child_spacing * 2
            min_size = max(min_size, child_with_spacing)
            
            child_nat_with_spacing = child_nat + self._line_width + self._child_spacing * 2
            nat_size = max(nat_size, child_nat_with_spacing)
        
        return (min_size, nat_size, -1, -1)
    
    def do_size_allocate(self, width: int, height: int, baseline: int):
        """Allocate size to the widget"""
        self._width = width
        self._height = height
        
        size = min(width, height)
        
        if self._child:
            total_margin = self._line_width + self._child_spacing
            child_size = max(0, size - 2 * total_margin)
            child_x = (width - child_size) // 2
            child_y = (height - child_size) // 2
            
            child_allocation = Gdk.Rectangle()
            child_allocation.x = child_x
            child_allocation.y = child_y
            child_allocation.width = child_size
            child_allocation.height = child_size
            
            self._child.size_allocate(child_allocation, baseline)
    
    def do_snapshot(self, snapshot: Gtk.Snapshot):
        """Draw the circular progress bar"""
        width = self._width
        height = self._height
        
        if width <= 0 or height <= 0:
            return
        
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - self._line_width / 2
        
        if radius <= 0:
            return
        
        # Create a Cairo context for drawing
        cairo_context = snapshot.append_cairo(
            Graphene.Rect().init(0, 0, width, height)
        )
        
        # Set line properties
        cairo_context.set_line_width(self._line_width)
        
        cap_styles = {
            "butt": 0, "round": 1, "square": 2
        }
        cairo_context.set_line_cap(cap_styles.get(self._line_style, 1))
        
        # Draw background circle/arc
        cairo_context.set_source_rgba(0.3, 0.3, 0.3, 0.5)
        
        if self._pie:
            cairo_context.move_to(center_x, center_y)
            cairo_context.arc(
                center_x, center_y, radius,
                math.radians(self._start_angle - 90),
                math.radians(self._end_angle - 90)
            )
            cairo_context.fill()
        else:
            cairo_context.arc(
                center_x, center_y, radius,
                math.radians(self._start_angle - 90),
                math.radians(self._end_angle - 90)
            )
            cairo_context.stroke()
        
        # Calculate progress based on current angle
        angle_range = self._end_angle - self._start_angle
        if angle_range < 0:
            angle_range += 360
            
        if angle_range != 0:
            current_progress = (self._angle - self._start_angle) / angle_range
            if current_progress < 0:
                current_progress += 1
            current_progress = max(0.0, min(1.0, current_progress))
        else:
            current_progress = 0.0
        
        if self._invert:
            current_progress = 1.0 - current_progress
        
        # Draw progress
        if current_progress > 0:
            cairo_context.set_source_rgba(1.0, 1.0, 1.0, 1.0)  # White progress
            
            progress_angle = self._start_angle + current_progress * angle_range
            
            if self._pie:
                cairo_context.move_to(center_x, center_y)
                cairo_context.arc(
                    center_x, center_y, radius,
                    math.radians(self._start_angle - 90),
                    math.radians(progress_angle - 90)
                )
                cairo_context.fill()
            else:
                cairo_context.arc(
                    center_x, center_y, radius,
                    math.radians(self._start_angle - 90),
                    math.radians(progress_angle - 90)
                )
                cairo_context.stroke()
        
        # Draw child widget if present
        if self._child:
            self.snapshot_child(self._child, snapshot)
    
    def do_dispose(self):
        """Clean up when widget is destroyed"""
        if self._child:
            self._child.unparent()
            self._child = None
        super().do_dispose()
# Custom rounded image widget
class RoundedImage(Gtk.Widget):
    """A widget that displays a rounded image"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pixbuf = None
        self.set_size_request(80, 80)
        self._create_placeholder_image()
    
    def _create_placeholder_image(self):
        """Create a placeholder image using Cairo and modern pixbuf creation"""
        import cairo
        
        size = 80
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)
        
        # Clear background
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()
        
        # Draw gradient circle
        gradient = cairo.RadialGradient(size/2, size/2, 0, size/2, size/2, size/2)
        gradient.add_color_stop_rgba(0, 0.4, 0.7, 1.0, 1.0)  # Light blue center
        gradient.add_color_stop_rgba(1, 0.2, 0.4, 0.8, 1.0)  # Darker blue edge
        
        ctx.set_source(gradient)
        ctx.arc(size/2, size/2, size/2 - 2, 0, 2 * math.pi)
        ctx.fill()
        
        # Add a person icon (simple representation)
        ctx.set_source_rgba(1, 1, 1, 0.8)
        ctx.set_line_width(2)
        
        # Head
        ctx.arc(size/2, size/2 - 8, 8, 0, 2 * math.pi)
        ctx.stroke()
        
        # Body
        ctx.arc(size/2, size/2 + 12, 16, math.pi, 0)
        ctx.stroke()
        
        # Create pixbuf from surface data using modern approach
        surface_data = surface.get_data()
        self._pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            surface_data,
            GdkPixbuf.Colorspace.RGB,
            True,  # has_alpha
            8,     # bits_per_sample
            size, size,
            surface.get_stride()
        )
    
    def set_image_from_file(self, filename):
        """Load image from file"""
        try:
            self._pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, 80, 80, True)
            self.queue_draw()
        except Exception as e:
            print(f"Could not load image: {e}")
    
    def do_snapshot(self, snapshot):
        """Draw the rounded image"""
        if not self._pixbuf:
            return
            
        # Use GTK4's get_width() and get_height() methods
        width = self.get_width()
        height = self.get_height()
        size = min(width, height)
        
        # Create Cairo context
        cairo_context = snapshot.append_cairo(
            Graphene.Rect().init(0, 0, width, height)
        )
        
        # Create circular clipping path
        center_x = width / 2
        center_y = height / 2
        radius = size / 2 - 2
        
        cairo_context.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cairo_context.clip()
        
        # Scale and draw the image
        scale_x = size / self._pixbuf.get_width()
        scale_y = size / self._pixbuf.get_height()
        scale = min(scale_x, scale_y)
        
        scaled_width = self._pixbuf.get_width() * scale
        scaled_height = self._pixbuf.get_height() * scale
        
        x = (width - scaled_width) / 2
        y = (height - scaled_height) / 2
        
        cairo_context.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cairo_context, self._pixbuf, x/scale, y/scale)
        cairo_context.paint()
    def set_from_pixbuf(self, pixbuf):
        """Set image from a GdkPixbuf.Pixbuf object with high-quality scaling"""
        if pixbuf:
            # The target_size here should be the internal rendering size of RoundedImage.
            # If RoundedImage is always, say, 100x100 for its drawing logic, use that.
            # Or, if it adapts, it needs to determine its target render size.
            # For this example, let's assume it has an internal target (e.g., from set_size_request).
            
            # Get the size RoundedImage aims for (e.g., from its own size request or a fixed value)
            # Let's use 100 as a placeholder for its internal desired rendering dimension.
            # This should ideally match the size used in _create_placeholder_image.
            internal_target_dim = 100 # Example: internal rendering dimension

            orig_width = pixbuf.get_width()
            orig_height = pixbuf.get_height()

            if orig_width == internal_target_dim and orig_height == internal_target_dim:
                self._pixbuf = pixbuf # Use as is if already target size
            else:
                # Scale to the internal target dimension if different
                # This ensures the pixbuf stored is what do_snapshot expects for rounding.
                scale = min(internal_target_dim / orig_width, internal_target_dim / orig_height)
                new_width = int(orig_width * scale)
                new_height = int(orig_height * scale)

                if new_width > 0 and new_height > 0:
                    self._pixbuf = pixbuf.scale_simple(
                        new_width, new_height,
                        GdkPixbuf.InterpType.BILINEAR # Faster for frequent updates
                    )
                else: # Invalid dimensions after scaling
                    self.clear() # Fallback to placeholder
                    return
            self.queue_draw()
        else:
            self.clear()

    def clear(self):
        """Clear the current image and show placeholder"""
        self._create_placeholder_image()
        self.queue_draw()

    def set_from_data(self, data):
        """Set image from raw data (bytes)"""
        try:
            # Create a GdkPixbuf.PixbufLoader to handle the data
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            self.set_from_pixbuf(pixbuf)
        except Exception as e:
            print(f"Could not load image from data: {e}")
            self.clear()

    def set_from_stream(self, stream):
        """Set image from a GInputStream"""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
            self.set_from_pixbuf(pixbuf)
        except Exception as e:
            print(f"Could not load image from stream: {e}")
            self.clear()
    def clear_image(self):
        """Clear current image and show default placeholder"""
        self._create_placeholder_image()
        self.queue_draw()
    
# Example usage and test application
class CircularProgressBarDemo(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Circular Progress Bar with Spacing Control Demo")
        self.set_default_size(500, 500)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        
        # Create a large progress bar with image in center
        self.main_progress = CircularProgressBar(
                angle=0.0,
    min_angle=-90.0,
    max_angle=90.0,
    start_angle=-90.0,
    end_angle=90.0,
                line_width=12,
                child_spacing=100,)
        self.main_progress.set_size_request(200, 200)
        
        # Create rounded image for the center
        self.profile_image = RoundedImage()
        self.main_progress.set_child(self.profile_image)
        
        # Connect to the progress bar signals for logging
        self.main_progress.connect("value-changed", self._on_progress_value_changed)
        self.main_progress.connect("clicked", self._on_progress_clicked)
        self.main_progress.connect("dragged", self._on_progress_dragged)
        
        # Center the main progress bar
        main_progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_progress_box.set_halign(Gtk.Align.CENTER)
        main_progress_box.append(self.main_progress)
        
        # Create smaller progress bars for comparison
        self.progress1 = CircularProgressBar(    angle=0.0,
    min_angle=-90.0,
    max_angle=90.0,
    start_angle=-90.0,
    end_angle=90.0)
        self.progress2 = CircularProgressBar(    angle=0.0,
    min_angle=-90.0,
    max_angle=90.0,
    start_angle=-90.0,
    end_angle=90.0)
        self.progress3 = CircularProgressBar(
                angle=0.0,
    min_angle=-90.0,
    max_angle=90.0,
    start_angle=-90.0,
    end_angle=90.0
        )
        
        # Add labels to smaller progress bars
        label1 = Gtk.Label(label="60%")
        label1.add_css_class("caption")
        self.progress1.set_child(label1)
        
        label2 = Gtk.Label(label="40%")
        label2.add_css_class("caption")
        self.progress2.set_child(label2)
        
        label3 = Gtk.Label(label="80%")
        label3.add_css_class("caption")
        self.progress3.set_child(label3)
        
        # Layout smaller progress bars horizontally
        small_progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        small_progress_box.set_halign(Gtk.Align.CENTER)
        small_progress_box.append(self.progress1)
        small_progress_box.append(self.progress2)
        small_progress_box.append(self.progress3)
        
        # Create controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Value adjustment
        value_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.value_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 1, 0.01
        )
        self.value_scale.set_value(0.75)
        self.value_scale.set_hexpand(True)
        self.value_scale.connect("value-changed", self.on_value_changed)
        
        value_box.append(Gtk.Label(label="Progress Value:"))
        value_box.append(self.value_scale)
        
        # Line width adjustment
        width_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.width_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 2, 20, 1
        )
        self.width_scale.set_value(12)
        self.width_scale.set_hexpand(True)
        self.width_scale.connect("value-changed", self.on_width_changed)
        
        width_box.append(Gtk.Label(label="Line Width:"))
        width_box.append(self.width_scale)
        
        # Child spacing adjustment - NEW CONTROL
        spacing_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.spacing_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 50, 1
        )
        self.spacing_scale.set_value(15)
        self.spacing_scale.set_hexpand(True)
        self.spacing_scale.connect("value-changed", self.on_spacing_changed)
        
        spacing_box.append(Gtk.Label(label="Child Spacing:"))
        spacing_box.append(self.spacing_scale)
        
        # Mode toggles
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.pie_button = Gtk.ToggleButton(label="Pie Mode")
        self.pie_button.connect("toggled", self.on_pie_toggled)
        
        self.invert_button = Gtk.ToggleButton(label="Invert Progress")
        self.invert_button.connect("toggled", self.on_invert_toggled)
        
        toggle_box.append(self.pie_button)
        toggle_box.append(self.invert_button)
        
        controls_box.append(value_box)
        controls_box.append(width_box)
        controls_box.append(spacing_box)  # Add the new spacing control
        controls_box.append(toggle_box)
        
        # Add everything to main box
        main_box.append(main_progress_box)
        main_box.append(Gtk.Label(label="Profile Progress: 75%"))
        main_box.append(Gtk.Separator())
        main_box.append(small_progress_box)
        main_box.append(controls_box)
        
        self.set_child(main_box)
    
    def _on_progress_value_changed(self, progress_bar, value):
        """Handle progress bar value changes"""
        percentage = int(value * 100)
        print(f"[Demo] Main progress value changed to {value:.3f} ({percentage}%)")
        
    def _on_progress_clicked(self, progress_bar, angle):
            print(f"Progress bar clicked at angle: {angle}")
    
    def _on_progress_dragged(self, progress_bar, value):
        """Handle progress bar drag events"""
        percentage = int(value * 100)
        print(f"[Demo] Main progress dragged to {value:.3f} ({percentage}%)")
    
    def on_value_changed(self, scale):
        value = scale.get_value()
        self.main_progress.set_property("value", value)
        self.progress1.set_property("value", value)
        self.progress2.set_property("value", value)
        self.progress3.set_property("value", value)
        
        # Update labels
        percentage = int(value * 100)
        if self.progress1.get_child():
            self.progress1.get_child().set_text(f"{percentage}%")
        if self.progress2.get_child():
            self.progress2.get_child().set_text(f"{percentage}%")
        if self.progress3.get_child():
            self.progress3.get_child().set_text(f"{percentage}%")
    
    def on_width_changed(self, scale):
        width = int(scale.get_value())
        self.main_progress.set_property("line_width", width)
    
    def on_spacing_changed(self, scale):
        """Handle child spacing changes"""
        spacing = int(scale.get_value())
        self.main_progress.set_property("child_spacing", spacing)
        self.progress1.set_property("child_spacing", spacing)
        self.progress2.set_property("child_spacing", spacing)
        self.progress3.set_property("child_spacing", spacing)
    
    def on_pie_toggled(self, button):
        pie_mode = button.get_active()
        self.main_progress.set_property("pie", pie_mode)
        self.progress1.set_property("pie", pie_mode)
        self.progress2.set_property("pie", pie_mode)
        self.progress3.set_property("pie", pie_mode)
    
    def on_invert_toggled(self, button):
        invert_mode = button.get_active()
        self.main_progress.set_property("invert", invert_mode)


class CircularProgressBarApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.circularprogressbar")
    
    def do_activate(self):
        window = CircularProgressBarDemo(self)
        window.present()


if __name__ == "__main__":
    app = CircularProgressBarApp()
    app.run()