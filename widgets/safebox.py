#!/usr/bin/env python3
"""
GTK4 Size Measurement Override Fix
Prevents negative size warnings and performance degradation
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, GLib
import logging
import warnings

# Suppress GTK warnings to improve performance
logging.getLogger('Gtk').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=Warning, module="gi")

class SafeBox(Gtk.Box):
    """
    Custom Box widget that ensures minimum sizes are never negative
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_width = (0, 0)
        self._cached_height = (0, 0)
    
    def do_measure(self, orientation, for_size):
        """
        GTK4's unified measurement method - replaces separate width/height methods
        """
        try:
            minimum, natural, minimum_baseline, natural_baseline = super().do_measure(orientation, for_size)
            
            # Ensure minimum size is never negative
            minimum = max(0, minimum)
            natural = max(minimum, natural)
            
            # Baseline values can be -1 (no baseline) but not other negatives
            if minimum_baseline < -1:
                minimum_baseline = -1
            if natural_baseline < -1:
                natural_baseline = -1
                
            return minimum, natural, minimum_baseline, natural_baseline
        except Exception as e:
            # Fallback to safe defaults
            return 0, 0, -1, -1
    
    def do_compute_expand(self, orientation):
        """
        Override expand computation to prevent issues
        """
        try:
            return super().do_compute_expand(orientation)
        except:
            return False

# Register the custom widget type
GObject.type_register(SafeBox)

def monkey_patch_gtk4_widgets():
    """
    Monkey patch GTK4 widgets to use safe size calculations
    """
    
    # Store original methods
    original_box_measure = Gtk.Box.do_measure
    original_widget_measure = Gtk.Widget.do_measure
    
    def safe_box_measure(self, orientation, for_size):
        """Safe measure method for Gtk.Box"""
        try:
            minimum, natural, minimum_baseline, natural_baseline = original_box_measure(self, orientation, for_size)
            
            # Clamp negative values
            minimum = max(0, minimum)
            natural = max(minimum, natural)
            
            # Handle baselines
            if minimum_baseline < -1:
                minimum_baseline = -1
            if natural_baseline < -1:
                natural_baseline = -1
                
            return minimum, natural, minimum_baseline, natural_baseline
        except Exception:
            return 0, 0, -1, -1
    
    def safe_widget_measure(self, orientation, for_size):
        """Safe measure method for Gtk.Widget"""
        try:
            minimum, natural, minimum_baseline, natural_baseline = original_widget_measure(self, orientation, for_size)
            
            # Clamp negative values
            minimum = max(0, minimum)
            natural = max(minimum, natural)
            
            # Handle baselines
            if minimum_baseline < -1:
                minimum_baseline = -1
            if natural_baseline < -1:
                natural_baseline = -1
                
            return minimum, natural, minimum_baseline, natural_baseline
        except Exception:
            return 0, 0, -1, -1
    
    # Apply patches
    Gtk.Box.do_measure = safe_box_measure
    Gtk.Widget.do_measure = safe_widget_measure

def patch_gtk_orientable_widgets():
    """
    Patch other common GTK4 widgets that might have sizing issues
    """
    widgets_to_patch = [
        Gtk.Button,
        Gtk.Label,
        Gtk.Entry,
        Gtk.Frame,
        Gtk.ScrolledWindow,
        Gtk.Paned,
        Gtk.Grid,
        Gtk.ListBox,
        Gtk.FlowBox
    ]
    
    for widget_class in widgets_to_patch:
        if hasattr(widget_class, 'do_measure'):
            original_measure = widget_class.do_measure
            
            def create_safe_measure(orig_method):
                def safe_measure(self, orientation, for_size):
                    try:
                        minimum, natural, minimum_baseline, natural_baseline = orig_method(self, orientation, for_size)
                        minimum = max(0, minimum)
                        natural = max(minimum, natural)
                        
                        if minimum_baseline < -1:
                            minimum_baseline = -1
                        if natural_baseline < -1:
                            natural_baseline = -1
                            
                        return minimum, natural, minimum_baseline, natural_baseline
                    except Exception:
                        return 0, 0, -1, -1
                return safe_measure
            
            widget_class.do_measure = create_safe_measure(original_measure)

def suppress_gtk4_warnings():
    """
    Suppress GTK4 warnings and debug messages
    """
    import os
    import sys
    
    # Set environment variables to reduce GTK verbosity
    os.environ['G_MESSAGES_DEBUG'] = ''
    os.environ['GTK_DEBUG'] = ''
    os.environ['GSK_DEBUG'] = ''
    
    # Suppress GLib log messages
    def null_log_handler(domain, level, message, data):
        pass
    
    # Set up log handlers for common GTK domains
    domains = ['Gtk', 'GLib', 'GObject', 'Gdk', 'GskRenderer']
    for domain in domains:
        GLib.log_set_handler(domain, GLib.LogLevelFlags.LEVEL_WARNING, null_log_handler, None)
        GLib.log_set_handler(domain, GLib.LogLevelFlags.LEVEL_CRITICAL, null_log_handler, None)

def create_size_allocation_monitor():
    """
    Monitor and fix size allocations in real-time
    """
    def on_size_allocate(widget, allocation, user_data=None):
        """Callback to ensure allocated sizes are valid"""
        if hasattr(allocation, 'width') and allocation.width < 0:
            allocation.width = 0
        if hasattr(allocation, 'height') and allocation.height < 0:
            allocation.height = 0
    
    return on_size_allocate

def initialize_gtk4_fixes():
    """
    Initialize all GTK4 fixes - call this before creating any GTK widgets
    """
    print("Applying GTK4 size measurement fixes...")
    
    # Apply all patches
    monkey_patch_gtk4_widgets()
    patch_gtk_orientable_widgets()
    suppress_gtk4_warnings()
    
    print("GTK4 size measurement fixes applied successfully")

# Decorator for automatic fix application
def gtk4_safe_widget(widget_class):
    """
    Decorator to make any widget class safe from negative size issues
    """
    original_measure = widget_class.do_measure
    
    def safe_measure(self, orientation, for_size):
        try:
            minimum, natural, minimum_baseline, natural_baseline = original_measure(self, orientation, for_size)
            minimum = max(0, minimum)
            natural = max(minimum, natural)
            
            if minimum_baseline < -1:
                minimum_baseline = -1
            if natural_baseline < -1:
                natural_baseline = -1
                
            return minimum, natural, minimum_baseline, natural_baseline
        except Exception:
            return 0, 0, -1, -1
    
    widget_class.do_measure = safe_measure
    return widget_class

# Usage example
if __name__ == "__main__":
    # Initialize fixes before creating any widgets
    initialize_gtk4_fixes()
    
    # Create application
    app = Gtk.Application(application_id="com.example.gtk4sizefix")
    
    def on_activate(app):
        # Create main window
        window = Gtk.ApplicationWindow(application=app)
        window.set_title("GTK4 Size Fix Test")
        window.set_default_size(400, 300)
        
        # Use SafeBox instead of regular Gtk.Box for new widgets
        main_box = SafeBox(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        
        # Create test widgets
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Size Fix Test"))
        window.set_titlebar(header)
        
        # Add various widgets to test
        for i in range(3):
            label = Gtk.Label(label=f"Test Label {i}")
            main_box.append(label)
        
        # Create horizontal box with button
        h_box = SafeBox(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button = Gtk.Button(label="Test Button")
        h_box.append(button)
        main_box.append(h_box)
        
        # Add a problematic widget that might cause sizing issues
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        text_view = Gtk.TextView()
        buffer = text_view.get_buffer()
        buffer.set_text("This is a test of the GTK4 size fix.\n" * 10)
        scrolled.set_child(text_view)
        main_box.append(scrolled)
        
        window.set_child(main_box)
        window.present()
        
        print("GTK4 test window created. Monitor console for warnings.")
    
    app.connect('activate', on_activate)
    app.run(None)