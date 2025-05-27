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
from modules.music import MusicPlayer # Assuming this is correctly importable
from modules.notifications import NotificationCenter
from modules.osd import Osd
class Notch(Gtk.Overlay):
    def __init__(self, **kwargs):
        super().__init__(name="notch-overlay")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        
        self.set_can_target(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        
        self.normal_height = 30
        self.dashboard = Dashboard(notch=self)
        self.osd = Osd(notch=self)
        self.music_player = MusicPlayer() # MusicPlayer instantiated here

        self.active_event_box = Gtk.Stack(
            name="active-event-box",
            transition_type="crossfade",
            transition_duration=100,
        )
        self.active_event_box.set_halign(Gtk.Align.CENTER)
        self.active_event_box.set_valign(Gtk.Align.CENTER)
        self.active_event_box.set_vexpand(True)
        self.active_event_box.set_hexpand(True)
        
        scroll_controller_active_box = Gtk.EventControllerScroll()
        scroll_controller_active_box.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller_active_box.connect("scroll", self.on_active_event_box_scroll)
        self.active_event_box.add_controller(scroll_controller_active_box)
        
        self.time_label = Gtk.Label()
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime(" · %A %d/%m")
        self.time_label.set_markup(f'<span size="11000" foreground="white"><b>{time_str}</b>{date_str}</span>')
        self.active_event_box.add_named(self.time_label, 'time-date')
        # self.active_event_box.add_named(self.music_player, 'music') # REMOVED from here
        
        self.stack = Gtk.Stack(
            name="notch-content",
            transition_type="crossfade",
            transition_duration=250,
        )
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        
        self.stack.add_named(self.dashboard, 'dashboard')
        self.stack.add_named(self.osd, 'osd')
        self.stack.add_named(self.active_event_box, 'active-event-box')
        self.stack.add_named(self.music_player, 'music') # ADDED music_player to notch-content stack

        self.notification_center = NotificationCenter(self)
        self.notification_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-page")
        self.notification_page.append(self.notification_center.notification_view)
        self.stack.add_named(self.notification_page, 'notification')
        
        self.stack.set_visible_child_name('active-event-box')
        self.active_event_box.set_visible_child_name('time-date') # Ensure time-date is default for active_event_box

        self.set_child(self.stack)

        # Add scroll controller for notch-content (self.stack)
        notch_content_scroll_controller = Gtk.EventControllerScroll()
        notch_content_scroll_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        notch_content_scroll_controller.connect("scroll", self.on_notch_content_scroll)
        self.stack.add_controller(notch_content_scroll_controller)

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
        
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_active_event_box_click)
        self.time_label.add_controller(gesture) # Assuming click on time_label opens dashboard
        
        # Key controllers
        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(self.key_controller)
        
        for widget in [self.dashboard, self.notification_page, self.active_event_box, self.stack, self.music_player, self.osd]:
            key_controller = Gtk.EventControllerKey.new()
            key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            key_controller.connect("key-pressed", self.on_key_pressed)
            widget.add_controller(key_controller)
        
        GLib.timeout_add_seconds(1, self.update_time)
        GLib.timeout_add(100, self.ensure_keyboard_focus)
        self.previous_widget = 'active-event-box'

    def ensure_keyboard_focus(self):
        self.grab_focus()
        return False

    def update_time(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime(" · %A %d/%m")
        self.time_label.set_markup(f'<span size="11000" foreground="white"><b>{time_str}</b>{date_str}</span>')
        return True

    def open_notch(self, widget_name):
        current = self.stack.get_visible_child_name()
        if current == widget_name:
            return
            
        if widget_name == 'notification' or widget_name == 'osd':
            if self.previous_widget == "osd" or self.previous_widget == "notification":
                self.previous_widget = self.previous_widget
            else:
                self.previous_widget = current
        
        # Close any currently active widget styling
        if current == 'dashboard':
            self.stack.remove_css_class("dashboard")
            self.dashboard.remove_css_class("open")
        elif current == 'notification':
            self.stack.remove_css_class("notification")
            self.notification_center.notification_view.remove_css_class("open")
        elif current == 'music': # ADDED
            self.stack.remove_css_class("music")
            self.music_player.remove_css_class("open")
        elif current == 'osd':
            self.stack.remove_css_class("osd")
            self.osd.remove_css_class("open")
        # Open the requested widget styling
        if widget_name == 'dashboard':
            self.stack.add_css_class("dashboard")
            self.dashboard.add_css_class("open")
        elif widget_name == 'notification':
            self.stack.add_css_class("notification")
            self.notification_center.notification_view.add_css_class("open")
        elif widget_name == 'music': # ADDED
            self.stack.add_css_class("music")
            self.music_player.add_css_class("open")
        elif widget_name == 'osd':
            self.stack.add_css_class("osd")
            self.osd.add_css_class("open")

        self.stack.set_visible_child_name(widget_name)
        
        # Focus handling
        newly_opened_widget = self.stack.get_visible_child()
        if newly_opened_widget and hasattr(newly_opened_widget, 'grab_focus'):
            newly_opened_widget.grab_focus()
            # Special handling for composite widgets like notification_page
            if widget_name == 'notification':
                 self.notification_center.notification_view.grab_focus()
            elif widget_name == 'dashboard': # Force focus on dashboard children if needed
                for child in self.dashboard:
                    if hasattr(child, 'grab_focus'): child.grab_focus()

        self.grab_focus() # Focus the overlay itself
        GLib.timeout_add(50, lambda: self.grab_focus() and False) # Ensure focus

    def on_active_event_box_click(self, gesture, n_press, x, y):
        self.open_notch('dashboard')
        return True

    def show_notification(self):
        current = self.stack.get_visible_child_name()
        if current != 'notification':
            self.previous_widget = current
        self.open_notch('notification')

    def collapse_notch(self):
        current = self.stack.get_visible_child_name()
        
        # This method is primarily for notifications returning to a previous state.
        # Other collapses (dashboard, music via ESC) are handled directly in on_key_pressed.
        if current == 'notification' or current == 'osd':
            if current == 'notification':
                self.stack.remove_css_class("notification")
                self.notification_center.notification_view.remove_css_class("open")
            elif current == 'osd':
                self.stack.remove_css_class("osd")
                self.osd.remove_css_class("open")
            # Restore previous widget's styling
            if self.previous_widget == 'dashboard':
                self.stack.add_css_class("dashboard")
                self.dashboard.add_css_class("open")
            elif self.previous_widget == 'music': # ADDED
                self.stack.add_css_class("music")
                self.music_player.add_css_class("open")
            elif self.previous_widget == 'osd':
                self.stack.add_css_class("osd")
                self.osd.add_css_class("open")
            # If previous_widget was 'active-event-box', no specific class needed on stack for it.
            
            self.stack.set_visible_child_name(self.previous_widget)
            # Focus the restored widget
            restored_widget = self.stack.get_child_by_name(self.previous_widget)
            if restored_widget and hasattr(restored_widget, 'grab_focus'):
                restored_widget.grab_focus()
        else:
            # Fallback for other cases if this method is called unexpectedly
            if current == 'dashboard':
                self.stack.remove_css_class("dashboard")
                self.dashboard.remove_css_class("open")
            elif current == 'music':
                self.stack.remove_css_class("music")
                self.music_player.remove_css_class("open")
            self.stack.set_visible_child_name('active-event-box')
            self.active_event_box.grab_focus() # Focus active event box
        
        return False

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape or keyval == 65307:
            current = self.stack.get_visible_child_name()
            
            target_widget_for_focus = None

            if current == 'dashboard':
                self.stack.remove_css_class("dashboard")
                self.dashboard.remove_css_class("open")
                self.stack.set_visible_child_name('active-event-box')
                target_widget_for_focus = self.active_event_box
            elif current == 'notification':
                self.collapse_notch() # Handles returning to previous_widget and its focus
                return True # collapse_notch handles focus
            elif current == 'music': # ADDED
                self.stack.remove_css_class("music")
                self.music_player.remove_css_class("open")
                self.stack.set_visible_child_name('active-event-box')
                target_widget_for_focus = self.active_event_box
            elif current == 'osd':
                self.collapse_notch() # Handles returning to previous_widget and its focus
                return True # collapse_notch handles focus

            if target_widget_for_focus:
                # Try to focus the actual visible child within active_event_box (e.g., time_label)
                active_child_of_target = target_widget_for_focus.get_visible_child() if hasattr(target_widget_for_focus, 'get_visible_child') else None
                if active_child_of_target and hasattr(active_child_of_target, 'grab_focus'):
                    active_child_of_target.grab_focus()
                elif hasattr(target_widget_for_focus, 'grab_focus'):
                    target_widget_for_focus.grab_focus()
                return True # Key handled
                
        return False

    # NEW METHOD for scrolling on notch-content (self.stack)
    def on_notch_content_scroll(self, controller, delta_x, delta_y):
        current_child_name = self.stack.get_visible_child_name()
        handled = False
        if current_child_name == 'active-event-box':
            self.open_notch('music')
            handled = True
        elif current_child_name == 'music':
            self.open_notch('active-event-box')
            handled = True
        return handled # True if event was handled, False otherwise to allow propagation

    def on_active_event_box_scroll(self, controller, delta_x, delta_y):
        """Handle scroll events to cycle through active_event_box children."""
        # This method is effective only if active_event_box has more than one child.
        changed = False
        if delta_y > 0:
            changed = self.open_active_event_box_child(1)
        elif delta_y < 0:
            changed = self.open_active_event_box_child(-1)
        return changed # True if handled, False otherwise

    def open_active_event_box_child(self, direction):
        pages = self.active_event_box.get_pages()
        num_pages = pages.get_n_items()
        if num_pages <= 1: # No change if 0 or 1 page
            return False

        current_name = self.active_event_box.get_visible_child_name()
        names = [pages.get_item(i).get_name() for i in range(num_pages)]
        
        if current_name not in names: # Should not happen if initialized correctly
             # Default to first child if current is somehow invalid and pages exist
            current_name = names[0] if names else None
            if not current_name: return False


        current_index = names.index(current_name)
        new_index = (current_index + direction) % num_pages
        new_name = names[new_index]
        
        if current_name == new_name: # Already visible or only one item
            return False

        # Close current child styling (if any specific styling was applied)
        if current_name == 'time-date':
            self.time_label.remove_css_class("open") # Assuming "open" class for active item
        # Add other cases if more children are added to active_event_box
            
        # Open new child styling
        if new_name == 'time-date':
            self.time_label.add_css_class("open")
        # Add other cases for new children
        
        self.active_event_box.set_visible_child_name(new_name)
        
        new_child_widget = self.active_event_box.get_child_by_name(new_name)
        if new_child_widget and hasattr(new_child_widget, 'grab_focus'):
            new_child_widget.grab_focus()
        else:
            self.active_event_box.grab_focus() # Fallback to stack focus
        
        GLib.timeout_add(50, lambda: (new_child_widget.grab_focus() if new_child_widget and hasattr(new_child_widget, 'grab_focus') else self.active_event_box.grab_focus()) and False)
        return True
    def print_box_size(self):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        print(f"Width: {width}, Height: {height}")
        return False