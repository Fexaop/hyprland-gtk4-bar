from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

import gi
import signal
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('GLib', '2.0')

from gi.repository import Gtk, GLib, Gdk, Gio
from gi.repository import Gtk4LayerShell as LayerShell
import datetime
from widgets.corner import Corner
from modules.dashboard import Dashboard
from modules.music import MusicPlayer
from modules.notifications import NotificationCenter
from modules.osd import Osd
from modules.applauncher import ApplicationLauncherBox
class Notch(Gtk.Overlay):
    def __init__(self,  notch_window=None, **kwargs):
        super().__init__(name="notch-overlay")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.notch_window = notch_window
        self.set_can_target(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        
        self.normal_height = 30
        self.previous_widget = 'active-event-box'
        
        # Widget configurations for easier management
        self.widget_configs = {
            'dashboard': {'css_class': 'dashboard', 'widget': None},
            'music': {'css_class': 'music', 'widget': None},
            'notification': {'css_class': 'notification', 'widget': None},
            'osd': {'css_class': 'osd', 'widget': None},
            'applauncher': {'css_class': 'applauncher', 'widget': None}
        }
        
        self._init_widgets()
        self._init_stack()
        self._init_controllers()
        self._init_corners()
        self._start_timers()

    def _init_widgets(self):
        """Initialize all widgets"""
        self.dashboard = Dashboard(notch=self)
        self.osd = Osd(notch=self)
        self.music_player = MusicPlayer()
        self.applauncher = ApplicationLauncherBox(notch=self)
        self.notification_center = NotificationCenter(self)
        
        # Update widget configs
        self.widget_configs['dashboard']['widget'] = self.dashboard
        self.widget_configs['music']['widget'] = self.music_player
        self.widget_configs['osd']['widget'] = self.osd
        self.widget_configs['applauncher']['widget'] = self.applauncher
        self.widget_configs['notification']['widget'] = self.notification_center.notification_view
        
    def _init_stack(self):
        """Initialize the main stack and active event box"""
        # Active event box setup
        self.active_event_box = Gtk.Stack(
            name="active-event-box",
            transition_type="crossfade",
            transition_duration=100,
        )
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        self.active_event_box.set_vexpand(True)
        self.active_event_box.set_hexpand(True)
        
        # Time label
        self.time_label = Gtk.Label()
        self._update_time()
        self.active_event_box.add_named(self.time_label, 'time-date')
        
        # Main stack setup
        self.stack = Gtk.Stack(
            name="notch-content",
            transition_type="crossfade",
            transition_duration=250,
        )
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        
        # Add all widgets to stack
        self.stack.add_named(self.dashboard, 'dashboard')
        self.stack.add_named(self.osd, 'osd')
        self.stack.add_named(self.active_event_box, 'active-event-box')
        self.stack.add_named(self.music_player, 'music')
        self.stack.add_named(self.applauncher, 'applauncher')
        
        # Notification page
        self.notification_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-page")
        self.notification_page.append(self.notification_center.notification_view)
        self.stack.add_named(self.notification_page, 'notification')
        
        self.stack.set_visible_child_name('active-event-box')
        self.active_event_box.set_visible_child_name('time-date')
        self.set_child(self.stack)

    def _init_controllers(self):
        """Initialize event controllers"""
        # Scroll controllers
        scroll_controller_active_box = Gtk.EventControllerScroll()
        scroll_controller_active_box.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller_active_box.connect("scroll", self.on_active_event_box_scroll)
        self.active_event_box.add_controller(scroll_controller_active_box)
        
        notch_content_scroll_controller = Gtk.EventControllerScroll()
        notch_content_scroll_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        notch_content_scroll_controller.connect("scroll", self.on_notch_content_scroll)
        self.stack.add_controller(notch_content_scroll_controller)
        
        # Click gesture
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_active_event_box_click)
        self.time_label.add_controller(gesture)
        
        # Key controllers
        widgets_for_key_control = [
            self, self.dashboard, self.notification_page, 
            self.active_event_box, self.stack, self.music_player, self.osd, self.applauncher
        ]
        
        for widget in widgets_for_key_control:
            key_controller = Gtk.EventControllerKey.new()
            key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            key_controller.connect("key-pressed", self.on_key_pressed)
            widget.add_controller(key_controller)

    def _init_corners(self):
        """Initialize corner widgets"""
        self.left_corner = Corner("top-right")
        self.left_corner.set_size_request(20, 30)
        self.left_corner.set_halign(Gtk.Align.START)
        self.left_corner.set_valign(Gtk.Align.START)
        self.add_overlay(self.left_corner)

        self.right_corner = Corner("top-left")
        self.right_corner.set_size_request(20, 30)
        self.right_corner.set_halign(Gtk.Align.END)
        self.right_corner.set_valign(Gtk.Align.START)
        self.add_overlay(self.right_corner)

    def _start_timers(self):
        """Start periodic timers"""
        GLib.timeout_add_seconds(1, self._update_time)
        GLib.timeout_add(100, self.ensure_keyboard_focus)

    def ensure_keyboard_focus(self):
        """Ensure keyboard focus is maintained"""
        self.grab_focus()
        return False

    def _update_time(self):
        """Update time display"""
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime(" · %A %d/%m")
        self.time_label.set_markup(f'<span size="11000" foreground="white"><b>{time_str}</b>{date_str}</span>')
        return True

    def _apply_widget_styling(self, widget_name, is_opening=True):
        """Apply or remove CSS styling for widgets with GLib.idle_add for smooth transitions"""
        if widget_name not in self.widget_configs:
            return
            
        config = self.widget_configs[widget_name]
        css_class = config['css_class']
        widget = config['widget']
        
        def apply_stack_class():
            if is_opening:
                self.stack.add_css_class(css_class)
            else:
                self.stack.remove_css_class(css_class)
            return False
            
        def apply_widget_class():
            if widget and hasattr(widget, 'add_css_class'):
                if is_opening:
                    widget.add_css_class("open")
                else:
                    widget.remove_css_class("open")
            return False
        
        # Use GLib.idle_add for smooth CSS transitions
        GLib.idle_add(apply_stack_class)
        GLib.idle_add(apply_widget_class)

    def open_notch(self, widget_name):
        """Open a specific notch widget"""
        current = self.stack.get_visible_child_name()
        if current == widget_name:
            return
            
        # Handle keyboard mode for applauncher
        if widget_name == 'applauncher' and self.notch_window:
            LayerShell.set_keyboard_mode(self.notch_window, LayerShell.KeyboardMode.EXCLUSIVE)
        elif current == 'applauncher' and self.notch_window:
            # Restore to ON_DEMAND when leaving applauncher
            LayerShell.set_keyboard_mode(self.notch_window, LayerShell.KeyboardMode.ON_DEMAND)
            
        # Handle previous widget tracking for notifications/osd
        if widget_name in ['notification', 'osd']:
            if self.previous_widget not in ["osd", "notification"]:
                self.previous_widget = current
        
        # Close current widget styling
        if current in self.widget_configs:
            self._apply_widget_styling(current, is_opening=False)
        
        # Open new widget styling
        if widget_name in self.widget_configs:
            self._apply_widget_styling(widget_name, is_opening=True)

        self.stack.set_visible_child_name(widget_name)
        self._focus_widget(widget_name)

    def _focus_widget(self, widget_name):
        """Handle focus for opened widgets"""
        def do_focus():
            if widget_name == 'notification':
                self.notification_center.notification_view.grab_focus()
            elif widget_name == 'dashboard':
                # Focus dashboard children if needed
                for child in self.dashboard:
                    if hasattr(child, 'grab_focus'):
                        child.grab_focus()
                        break
            elif widget_name == 'applauncher':
                # Special handling for applauncher search input
                if hasattr(self.applauncher, 'search_entry'):
                    # Ensure the search entry is focusable
                    self.applauncher.search_entry.set_can_focus(True)
                    self.applauncher.search_entry.set_receives_default(True)
                    
                    # Clear any existing text and focus
                    self.applauncher.search_entry.set_text("")
                    self.applauncher.search_entry.grab_focus()
                    
                    # Additional method to ensure cursor is in the entry
                    if hasattr(self.applauncher.search_entry, 'set_position'):
                        self.applauncher.search_entry.set_position(-1)
                    
                    print(f"Search entry focused: {self.applauncher.search_entry.has_focus()}")
                else:
                    self.applauncher.grab_focus()
            else:
                newly_opened_widget = self.stack.get_visible_child()
                if newly_opened_widget and hasattr(newly_opened_widget, 'grab_focus'):
                    newly_opened_widget.grab_focus()
            
            # Don't grab focus back to notch when focusing applauncher
            if widget_name != 'applauncher':
                self.grab_focus()
            return False
        
        # For applauncher, use multiple attempts with longer delays to work with EXCLUSIVE mode
        if widget_name == 'applauncher':
            GLib.timeout_add(100, do_focus)
            GLib.timeout_add(200, do_focus)
            GLib.timeout_add(300, do_focus)
        else:
            GLib.timeout_add(50, do_focus)

    def collapse_notch(self):
        """Collapse notch to previous state"""
        current = self.stack.get_visible_child_name()
        
        # Restore keyboard mode when collapsing from applauncher
        if current == 'applauncher' and self.notch_window:
            LayerShell.set_keyboard_mode(self.notch_window, LayerShell.KeyboardMode.ON_DEMAND)
        
        if current in ['notification', 'osd']:
            # Close current widget
            self._apply_widget_styling(current, is_opening=False)
            
            if current == 'notification':
                self.notification_center.is_showing = False
            
            # Restore previous widget
            if self.previous_widget in self.widget_configs:
                self._apply_widget_styling(self.previous_widget, is_opening=True)
            
            self.stack.set_visible_child_name(self.previous_widget)
            
            # Focus restored widget
            restored_widget = self.stack.get_child_by_name(self.previous_widget)
            if restored_widget and hasattr(restored_widget, 'grab_focus'):
                restored_widget.grab_focus()
        else:
            # Fallback collapse to active-event-box
            if current in self.widget_configs:
                self._apply_widget_styling(current, is_opening=False)
            
            self.stack.set_visible_child_name('active-event-box')
            self.active_event_box.grab_focus()
        
        return False

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events"""
        if keyval in [Gdk.KEY_Escape, 65307]:
            current = self.stack.get_visible_child_name()
            
            # Restore keyboard mode when escaping from applauncher
            if current == 'applauncher' and self.notch_window:
                LayerShell.set_keyboard_mode(self.notch_window, LayerShell.KeyboardMode.ON_DEMAND)
            
            if current in ['notification', 'osd']:
                self.collapse_notch()
            elif current in self.widget_configs:
                self._apply_widget_styling(current, is_opening=False)
                self.stack.set_visible_child_name('active-event-box')
                
                # Focus active event box child
                active_child = self.active_event_box.get_visible_child()
                if active_child and hasattr(active_child, 'grab_focus'):
                    active_child.grab_focus()
                elif hasattr(self.active_event_box, 'grab_focus'):
                    self.active_event_box.grab_focus()
            
            return True
                
        return False

    def on_notch_content_scroll(self, controller, delta_x, delta_y):
        """Handle scroll events on notch content"""
        current_child_name = self.stack.get_visible_child_name()
        
        if current_child_name == 'active-event-box':
            self.open_notch('music')
            return True
        elif current_child_name == 'music':
            self.open_notch('active-event-box')
            return True
        
        return False

    def on_active_event_box_scroll(self, controller, delta_x, delta_y):
        """Handle scroll events to cycle through active_event_box children"""
        direction = 1 if delta_y > 0 else -1 if delta_y < 0 else 0
        if direction != 0:
            return self.open_active_event_box_child(direction)
        return False

    def open_active_event_box_child(self, direction):
        """Cycle through active event box children"""
        pages = self.active_event_box.get_pages()
        num_pages = pages.get_n_items()
        
        if num_pages <= 1:
            return False

        current_name = self.active_event_box.get_visible_child_name()
        names = [pages.get_item(i).get_name() for i in range(num_pages)]
        
        if current_name not in names:
            current_name = names[0] if names else None
            if not current_name:
                return False

        current_index = names.index(current_name)
        new_index = (current_index + direction) % num_pages
        new_name = names[new_index]
        
        if current_name == new_name:
            return False

        # Handle styling transitions
        def update_styling():
            # Remove old styling
            if current_name == 'time-date':
                self.time_label.remove_css_class("open")
            
            # Add new styling
            if new_name == 'time-date':
                self.time_label.add_css_class("open")
            
            return False
        
        GLib.idle_add(update_styling)
        
        self.active_event_box.set_visible_child_name(new_name)
        
        # Focus new child
        def focus_new_child():
            new_child_widget = self.active_event_box.get_child_by_name(new_name)
            if new_child_widget and hasattr(new_child_widget, 'grab_focus'):
                new_child_widget.grab_focus()
            else:
                self.active_event_box.grab_focus()
            return False
        
        GLib.timeout_add(50, focus_new_child)
        return True

    def on_active_event_box_click(self, gesture, n_press, x, y):
        """Handle click on active event box"""
        self.open_notch('dashboard')
        return True

    def show_notification(self):
        """Show notification center"""
        current = self.stack.get_visible_child_name()
        if current != 'notification':
            self.previous_widget = current
        self.open_notch('notification')

    def print_box_size(self):
        """Debug method to print box size"""
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        print(f"Width: {width}, Height: {height}")
        return False