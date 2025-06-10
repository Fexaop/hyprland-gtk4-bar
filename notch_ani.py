# GTK4 Layer Shell with Optimized Fixed Position Widgets
# Usage: GI_TYPELIB_PATH=build/src LD_LIBRARY_PATH=build/src python3 layer_shell_app.py

from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, GLib, Graphene, Gsk, Gdk
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
import math

class OptimizedViewportContainer(Gtk.Widget):
    """Optimized container with minimal redraws and calculations"""
    
    def __init__(self, width, height):
        super().__init__()
        self.viewport_width = width
        self.viewport_height = height
        
        # Animation properties
        self.target_width = width
        self.target_height = height
        self.is_animating = False
        self.animation_start_time = 0
        self.start_width = width
        self.start_height = height
        
        # Widget storage
        self.time_widget = None
        self.calendar_widget = None
        self.current_view = "time"
        
        # Fixed positions
        self.widget_x = 10
        self.widget_y = 10
        
        # Cache for performance
        self._last_rendered_view = None
        self._cached_clip_rect = Graphene.Rect()
    
    def add_time_widget(self, widget, natural_width, natural_height):
        """Add time widget with natural size"""
        if self.time_widget:
            self.time_widget.unparent()
        
        self.time_widget = widget
        widget.set_parent(self)
        widget.set_size_request(natural_width, natural_height)
    
    def add_calendar_widget(self, widget, natural_width, natural_height):
        """Add calendar widget with natural size"""
        if self.calendar_widget:
            self.calendar_widget.unparent()
        
        self.calendar_widget = widget
        widget.set_parent(self)
        widget.set_size_request(natural_width, natural_height)
    
    def set_current_view(self, view_name):
        """Set current view with minimal redraws"""
        if self.current_view != view_name:
            self.current_view = view_name
            self._last_rendered_view = None  # Force redraw only when view changes
            self.queue_draw()
    
    def start_size_animation(self, target_width, target_height, duration=0.3):
        """Start optimized size animation"""
        if self.is_animating:
            return
        
        self.start_width = self.viewport_width
        self.start_height = self.viewport_height
        self.target_width = target_width
        self.target_height = target_height
        self.is_animating = True
        self.animation_start_time = GLib.get_monotonic_time()
        self.animation_duration = duration * 1000000  # Convert to microseconds
        
        # Use frame clock for smooth animation
        self.add_tick_callback(self._animation_tick)
    
    def _animation_tick(self, widget, frame_clock):
        """Optimized animation tick using frame clock"""
        if not self.is_animating:
            return GLib.SOURCE_REMOVE
        
        current_time = frame_clock.get_frame_time()
        elapsed = current_time - self.animation_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        # Smoother easing with less CPU usage
        eased_progress = progress * progress * (3.0 - 2.0 * progress)  # smoothstep
        
        # Update viewport size
        self.viewport_width = int(self.start_width + (self.target_width - self.start_width) * eased_progress)
        self.viewport_height = int(self.start_height + (self.target_height - self.start_height) * eased_progress)
        
        # Only queue resize, not full redraw
        self.queue_resize()
        
        if progress >= 1.0:
            self.is_animating = False
            self.viewport_width = self.target_width
            self.viewport_height = self.target_height
            return GLib.SOURCE_REMOVE
        
        return GLib.SOURCE_CONTINUE
    
    def set_viewport_size(self, width, height):
        """Set viewport size instantly"""
        self.viewport_width = width
        self.viewport_height = height
        self.target_width = width
        self.target_height = height
        self.is_animating = False
        self.queue_resize()
    
    def do_measure(self, orientation, for_size):
        """Return viewport size"""
        if orientation == Gtk.Orientation.HORIZONTAL:
            return self.viewport_width, self.viewport_width, -1, -1
        else:
            return self.viewport_height, self.viewport_height, -1, -1
    
    def do_size_allocate(self, width, height, baseline):
        """Properly allocate all child widgets"""
        # Always allocate both widgets to ensure they have valid allocations
        if self.time_widget:
            # Create transform for time widget position
            time_transform = Gsk.Transform.new()
            time_transform = time_transform.translate(Graphene.Point().init(self.widget_x, self.widget_y))
            self.time_widget.allocate(300, 50, baseline, time_transform)
        
        if self.calendar_widget:
            # Create transform for calendar widget position  
            cal_transform = Gsk.Transform.new()
            cal_transform = cal_transform.translate(Graphene.Point().init(self.widget_x, self.widget_y))
            self.calendar_widget.allocate(500, 500, baseline, cal_transform)
    
    def do_snapshot(self, snapshot):
        """Simplified snapshot without custom positioning"""
        current_widget = None
        if self.current_view == "time":
            current_widget = self.time_widget
        elif self.current_view == "calendar":
            current_widget = self.calendar_widget
        
        if not current_widget:
            return
        
        # Create clipping rectangle for viewport
        clip_rect = Graphene.Rect()
        clip_rect.init(0, 0, self.viewport_width, self.viewport_height)
        
        # Push clip region to limit rendering to viewport
        snapshot.push_clip(clip_rect)
        
        # Snapshot the child widget (position already handled in allocation)
        Gtk.Widget.snapshot_child(self, current_widget, snapshot)
        
        # Pop the clip region
        snapshot.pop()

class LayerShellApp:
    """Optimized main application"""
    
    # Widget natural sizes
    TIME_WIDGET_SIZE = (300, 50)
    CALENDAR_WIDGET_SIZE = (500, 500)
    
    # Viewport sizes
    TIME_VIEWPORT_SIZE = (320, 70)
    CALENDAR_VIEWPORT_SIZE = (450, 450)
    
    # Reduced animation duration for smoother feel
    ANIMATION_DURATION = 0.3
    
    def __init__(self):
        self.current_view = "time"
        self.time_timeout_id = None
        self.is_animating = False
        
        self._setup_window()
        self._create_widgets()
        self._start_time_updates()
        
        self.window.present()
    
    def _setup_window(self):
        """Setup window and layer shell"""
        self.window = Gtk.Window()
        self.window.set_resizable(False)
        
        # Layer shell setup
        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.TOP)
        LayerShell.set_namespace(self.window, "notch")
        LayerShell.set_anchor(self.window, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self.window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_margin(self.window, LayerShell.Edge.TOP, 20)
        LayerShell.set_margin(self.window, LayerShell.Edge.RIGHT, 20)
        
        # Create optimized container
        initial_width, initial_height = self.TIME_VIEWPORT_SIZE
        self.container = OptimizedViewportContainer(initial_width, initial_height)
        
        LayerShell.set_exclusive_zone(self.window, max(initial_width, initial_height))
        
        # Click handler with debouncing
        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self._on_click)
        self.container.add_controller(click_gesture)
        
        self.window.set_child(self.container)
        self.window.connect("destroy", self._on_destroy)
    
    def _create_widgets(self):
        """Create optimized widgets"""
        # Time widget
        self.time_widget = self._create_time_widget()
        time_width, time_height = self.TIME_WIDGET_SIZE
        self.container.add_time_widget(self.time_widget, time_width, time_height)
        
        # Calendar widget
        self.calendar_widget = Gtk.Calendar()
        self.calendar_widget.set_show_heading(True)
        self.calendar_widget.set_show_day_names(True)
        self.calendar_widget.set_show_week_numbers(False)
        
        cal_width, cal_height = self.CALENDAR_WIDGET_SIZE
        self.container.add_calendar_widget(self.calendar_widget, cal_width, cal_height)
    
    def _create_time_widget(self):
        """Create time widget with minimal styling"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_halign(Gtk.Align.START)
        box.set_valign(Gtk.Align.START)
        box.set_spacing(2)
        
        self.time_label = Gtk.Label()
        self.time_label.set_halign(Gtk.Align.START)
        
        self.date_label = Gtk.Label()
        self.date_label.set_halign(Gtk.Align.START)
        
        box.append(self.time_label)
        box.append(self.date_label)
        
        return box
    
    def _start_time_updates(self):
        """Start time updates with reduced frequency"""
        self._update_time()
        # Update every 2 seconds instead of 1 to reduce CPU usage
        self.time_timeout_id = GLib.timeout_add_seconds(2, self._update_time)
    
    def _update_time(self):
        """Update time display efficiently"""
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%a, %b %d")
        
        # Only update if text changed
        current_time = f"<span font='20' weight='bold'>{time_str}</span>"
        current_date = f"<span font='12'>{date_str}</span>"
        
        if self.time_label.get_text() != time_str:
            self.time_label.set_markup(current_time)
        
        if self.date_label.get_text() != date_str:
            self.date_label.set_markup(current_date)
        
        return True
    
    def _animate_to_view(self, target_view):
        """Animate to target view with optimization"""
        if self.is_animating:
            return  # Prevent overlapping animations
        
        self.is_animating = True
        
        # Determine target size
        if target_view == "time":
            target_width, target_height = self.TIME_VIEWPORT_SIZE
        else:
            target_width, target_height = self.CALENDAR_VIEWPORT_SIZE
        
        # Switch view immediately
        self.container.set_current_view(target_view)
        self.current_view = target_view
        
        # Start size animation
        self.container.start_size_animation(target_width, target_height, self.ANIMATION_DURATION)
        
        # Update exclusive zone during animation
        def update_exclusive_zone():
            if self.container.is_animating:
                current_size = max(self.container.viewport_width, self.container.viewport_height)
                LayerShell.set_exclusive_zone(self.window, current_size)
                return GLib.SOURCE_CONTINUE
            else:
                # Final update
                final_size = max(self.container.viewport_width, self.container.viewport_height)
                LayerShell.set_exclusive_zone(self.window, final_size)
                self.is_animating = False
                return GLib.SOURCE_REMOVE
        
        # Use lower frequency for exclusive zone updates
        GLib.timeout_add(32, update_exclusive_zone)  # ~30fps for zone updates
    
    def _on_click(self, gesture, n_press, x, y):
        """Handle clicks with debouncing"""
        if self.is_animating:
            return
        
        target_view = "calendar" if self.current_view == "time" else "time"
        self._animate_to_view(target_view)
    
    def _on_destroy(self, widget):
        """Cleanup"""
        if self.time_timeout_id:
            GLib.source_remove(self.time_timeout_id)

def main():
    """Application entry point"""
    app = LayerShellApp()
    
    main_loop = GLib.MainLoop()
    app.window.connect("destroy", lambda w: main_loop.quit())
    
    try:
        main_loop.run()
    except KeyboardInterrupt:
        main_loop.quit()

if __name__ == "__main__":
    main()