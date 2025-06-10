#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import math

class CalendarRevealWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Calendar Reveal Animation")
        self.set_default_size(800, 600)
        
        # Animation parameters
        self.start_width = 300
        self.start_height = 50
        self.end_width = 500
        self.end_height = 500
        self.animation_duration = 1000  # milliseconds
        self.animation_start_time = None
        self.tick_callback_id = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(50)
        main_box.set_margin_bottom(50)
        main_box.set_margin_start(50)
        main_box.set_margin_end(50)
        self.set_child(main_box)
        
        # Title
        title = Gtk.Label(label="Calendar Reveal Animation")
        title.add_css_class("title-1")
        main_box.append(title)
        
        # Center container for the animated widget
        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        main_box.append(center_box)
        
        # Container with fixed size for the animation
        self.container = Gtk.Box()
        self.container.set_size_request(self.end_width, self.end_height)
        self.container.set_halign(Gtk.Align.CENTER)
        self.container.set_valign(Gtk.Align.CENTER)
        center_box.append(self.container)
        
        # Use ScrolledWindow for clipping - this is the GTK4 way
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)  # No scrollbars
        self.scrolled.set_size_request(self.start_width, self.start_height)
        self.scrolled.set_halign(Gtk.Align.CENTER)
        self.scrolled.set_valign(Gtk.Align.CENTER)
        self.scrolled.add_css_class("clip-container")
        
        # Create the calendar widget
        self.calendar = Gtk.Calendar()
        self.calendar.set_size_request(self.end_width, self.end_height)
        self.calendar.add_css_class("calendar-widget")
        
        # Put calendar in scrolled window
        self.scrolled.set_child(self.calendar)
        self.container.append(self.scrolled)
        
        # Control buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        main_box.append(button_box)
        
        start_button = Gtk.Button(label="Start Animation")
        start_button.connect("clicked", self.start_animation)
        start_button.add_css_class("suggested-action")
        button_box.append(start_button)
        
        reset_button = Gtk.Button(label="Reset")
        reset_button.connect("clicked", self.reset_animation)
        button_box.append(reset_button)
    
    def easing_function(self, t):
        """Ease-out cubic easing function for smooth animation"""
        return 1 - pow(1 - t, 3)
    
    def start_animation(self, button):
        """Start the reveal animation"""
        if self.tick_callback_id is not None:
            # Animation already running
            return
        
        # Reset to start state
        self.reset_to_start()
        
        # Start the animation
        self.animation_start_time = None
        self.tick_callback_id = self.add_tick_callback(self.animate_tick)
    
    def reset_animation(self, button):
        """Reset animation to start state"""
        self.stop_animation()
        self.reset_to_start()
    
    def reset_to_start(self):
        """Reset calendar to initial clipped state"""
        self.scrolled.set_size_request(self.start_width, self.start_height)
    
    def stop_animation(self):
        """Stop the current animation"""
        if self.tick_callback_id is not None:
            self.remove_tick_callback(self.tick_callback_id)
            self.tick_callback_id = None
    
    def animate_tick(self, widget, frame_clock):
        """Animation tick callback"""
        current_time = frame_clock.get_frame_time()
        
        # Initialize start time on first frame
        if self.animation_start_time is None:
            self.animation_start_time = current_time
            return GLib.SOURCE_CONTINUE
        
        # Calculate progress (0.0 to 1.0)
        elapsed = (current_time - self.animation_start_time) / 1000  # Convert to milliseconds
        progress = min(elapsed / self.animation_duration, 1.0)
        
        # Apply easing
        eased_progress = self.easing_function(progress)
        
        # Calculate current dimensions
        current_width = self.start_width + (self.end_width - self.start_width) * eased_progress
        current_height = self.start_height + (self.end_height - self.start_height) * eased_progress
        
        # Update the scrolled window size (this clips the calendar)
        self.scrolled.set_size_request(int(current_width), int(current_height))
        
        # Check if animation is complete
        if progress >= 1.0:
            self.stop_animation()
            return GLib.SOURCE_REMOVE
        
        return GLib.SOURCE_CONTINUE

class CalendarRevealApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.calendarreveal")
    
    def do_activate(self):
        window = CalendarRevealWindow(self)
        window.present()

def main():
    # Add some custom CSS for better styling
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        .clip-container {
            border-radius: 12px;
            border: 2px solid #d4d4d8;
            background: white;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .calendar-widget {
            background: white;
            border-radius: 10px;
        }
        
        window {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .title-1 {
            color: white;
            font-weight: bold;
            font-size: 24px;
            margin-bottom: 20px;
        }
        
        button {
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 500;
            min-height: 40px;
        }
        
        .suggested-action {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            border: none;
        }
        
        .suggested-action:hover {
            background: linear-gradient(135deg, #047857 0%, #065f46 100%);
        }
    """)
    
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    
    app = CalendarRevealApp()
    app.run()

if __name__ == "__main__":
    main()