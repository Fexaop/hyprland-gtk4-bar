import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, Pango

# Import notification service instead of using sockets
from service.notification import Notifications, Notification, NotificationCloseReason

import tempfile
import os

class NotificationStack(Gtk.Box):
    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8
        )
        self.set_name("notification-stack")
        self.notifications = {}

    def add_notification(self, notification: Notification, notification_center):
        view = NotificationView(notification_center)
        view.update_notification(notification)
        self.notifications[notification.id] = view
        self.prepend(view)  # Add new notifications at the top
        view.show()

    def remove_notification(self, notification_id: int):
        if notification_id in self.notifications:
            view = self.notifications.pop(notification_id)
            self.remove(view)

    def clear(self):
        for view in self.notifications.values():
            self.remove(view)
        self.notifications.clear()

class NotificationView(Gtk.Box):
    def __init__(self, notification_center):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-box"
        )
        self.notification_center = notification_center
        
        # Create stack instead of box for container
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=200,
            name="notification-stack"
        )
        self.stack.set_hexpand(True)
        
        # Keep track of notifications in stack
        self.notification_pages = {}
        
        # Add navigation button bar below stack
        self.nav_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            halign=Gtk.Align.CENTER
        )
        self.prev_button = Gtk.Button(label="◀")
        self.prev_button.get_style_context().add_class("flat")
        self.prev_button.get_style_context().add_class("white-text")
        self.prev_button.connect("clicked", self.on_prev_clicked)
        
        self.next_button = Gtk.Button(label="▶")
        self.next_button.get_style_context().add_class("flat")
        self.next_button.get_style_context().add_class("white-text")
        self.next_button.connect("clicked", self.on_next_clicked)
        
        self.nav_box.append(self.prev_button)
        self.nav_box.append(self.next_button)
        
        # Add stack and nav_box to main container
        self.append(self.stack)
        self.append(self.nav_box)
        
        # Add motion controller for hover detection
        self.motion_controller = Gtk.EventControllerMotion()
        self.motion_controller.connect("enter", self.on_hover_enter)
        self.motion_controller.connect("leave", self.on_hover_leave)
        self.add_controller(self.motion_controller)
        
        # Track hover state
        self.is_hovered = False
    
    def create_notification_page(self, notification):
        """Create a new page for the stack containing notification content"""
        page = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-container",
            spacing=8
        )
        
        # Create notification image
        image = Gtk.Picture(name="notification-image")
        image.set_size_request(48, 48)
        image.set_content_fit(Gtk.ContentFit.CONTAIN)
        image.set_can_shrink(True)
        
        # Text container
        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-text"
        )
        text_box.set_valign(Gtk.Align.CENTER)
        
        # Summary
        summary_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-summary-box"
        )
        summary_label = Gtk.Label(
            label=f"{notification.summary} | {notification.app_name}",
            name="notification-summary"
        )
        summary_label.set_halign(Gtk.Align.START)
        summary_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_label.set_max_width_chars(30)
        summary_box.append(summary_label)
        
        # Body
        body_label = Gtk.Label(label=notification.body)
        body_label.set_halign(Gtk.Align.START)
        body_label.set_ellipsize(Pango.EllipsizeMode.END)
        body_label.set_max_width_chars(30)
        
        text_box.append(summary_box)
        text_box.append(body_label)
        
        # Close button
        close_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-close-box"
        )
        close_box.set_valign(Gtk.Align.CENTER)
        close_box.set_halign(Gtk.Align.END)
        
        close_button = Gtk.Button(label="×", name="notification-close-button")
        close_button.set_halign(Gtk.Align.CENTER)
        close_button.connect("clicked", self.on_close_clicked)
        close_button.get_style_context().add_class("circular")
        
        close_box.append(close_button)
        
        # Add all elements to page
        page.append(image)
        page.append(text_box)
        text_box.set_hexpand(True)
        page.append(close_box)
        
        # Set image if available
        if notification.image_texture:
            image.set_paintable(notification.image_texture)
            image.set_visible(True)
        elif notification.app_icon and notification.app_icon.strip():
            if os.path.isfile(notification.app_icon):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        notification.app_icon, 48, 48, True)
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    image.set_paintable(texture)
                    image.set_visible(True)
                except Exception as e:
                    print(f"Error loading icon: {e}")
                    self._try_load_icon_name(image, notification.app_icon)
            else:
                self._try_load_icon_name(image, notification.app_icon)
        
        return page
    
    def update_notification(self, notification):
        """Add or update notification in stack"""
        # Create new page if needed
        if notification.id not in self.notification_pages:
            page = self.create_notification_page(notification)
            self.notification_pages[notification.id] = page
            self.stack.add_named(page, str(notification.id))
        
        # Show the page
        self.stack.set_visible_child_name(str(notification.id))
        self.notification = notification
    
    def _try_load_icon_name(self, image_widget, icon_name):
        """Try to load an icon by name from theme and set it as texture"""
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        try:
            pixbuf = icon_theme.load_icon(icon_name, 48, 0)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image_widget.set_paintable(texture)
            image_widget.set_visible(True)
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            try:
                pixbuf = icon_theme.load_icon("dialog-error", 48, 0)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                image_widget.set_paintable(texture)
                image_widget.set_visible(True)
            except:
                image_widget.set_visible(False)

    def on_notification_click(self, gesture, n_press, x, y):
        # Dismiss notification on click (unless an action should be invoked)
        self.notification_center.hide_notification()
        return True

    def on_close_clicked(self, button):
        print("Notification close button clicked")
        self.notification_center.hide_notification()
        return True

    def on_prev_clicked(self, button):
        if hasattr(self.notification_center, "navigate_previous"):
            self.notification_center.navigate_previous()
            
    def on_next_clicked(self, button):
        if hasattr(self.notification_center, "navigate_next"):
            self.notification_center.navigate_next()
    
    def on_hover_enter(self, controller, x, y):
        """Called when mouse enters the notification"""
        self.is_hovered = True
        self.notification_center.on_notification_hover()
        
    def on_hover_leave(self, controller):
        """Called when mouse leaves the notification"""
        self.is_hovered = False
        self.notification_center.on_notification_unhover()

class NotificationCenter:
    def __init__(self, notch):
        self.notch = notch
        self.history = []         # list of notifications (history)
        self.current_index = -1   # index in the history list
        self.current_notification = None
        self.notification_queue = []
        self.is_showing = False
        self.notification_view = NotificationView(self)
        self.notifications = Notifications()
        self.notifications.connect('notification-added', self.on_notification_added)
        self.hide_timeout_id = None
        self.unhover_timeout_id = None
        self.current_timeout = None
    
    def on_notification_added(self, _, notification_id):
        notification = self.notifications.get_notification_from_id(notification_id)
        if notification:
            print(f"Received notification: {notification.summary}")
            # Append to history and update current index
            self.history.append(notification)
            self.current_index = len(self.history) - 1
            # If currently showing, immediately update view to new notification.
            if self.is_showing:
                self.current_notification = notification
                self.prepare_notification(notification)
                self.update_nav_buttons()
            else:
                # Not showing? Start showing immediately.
                self.notification_queue.append(notification)
                self.show_next_notification()
    
    def navigate_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            notification = self.history[self.current_index]
            self.current_notification = notification
            self.prepare_notification(notification)
            self.update_nav_buttons()
    
    def navigate_next(self):
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            notification = self.history[self.current_index]
            self.current_notification = notification
            self.prepare_notification(notification)
            self.update_nav_buttons()
            
    def update_nav_buttons(self):
        # Dim prev button if at start, next button if at end.
        if self.current_index <= 0:
            self.notification_view.prev_button.set_sensitive(False)
        else:
            self.notification_view.prev_button.set_sensitive(True)
        if self.current_index >= len(self.history) - 1:
            self.notification_view.next_button.set_sensitive(False)
        else:
            self.notification_view.next_button.set_sensitive(True)
    
    def prepare_notification(self, notification):
        self.notification_view.update_notification(notification)
    
    def show_next_notification(self):
        if not self.notification_queue:
            self.is_showing = False
            return
            
        # Clear any existing timeouts
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
        if self.unhover_timeout_id:
            GLib.source_remove(self.unhover_timeout_id)
            
        self.is_showing = True
        notification = self.notification_queue.pop(0)
        self.current_notification = notification
        self.prepare_notification(notification)
        self.update_nav_buttons()
        self.notch.open_notch('notification')
        
        # Set new timeout
        self.hide_timeout_id = GLib.timeout_add(8000, self.check_and_hide)
    
    def check_and_hide(self):
        """Check if we can hide the notification"""
        if not self.notification_view.is_hovered:
            self.hide_notification()
        self.hide_timeout_id = None
        return False
    
    def hide_notification(self):
        if self.is_showing:
            if self.current_notification:
                self.notifications.close_notification(
                    self.current_notification.id,
                    NotificationCloseReason.EXPIRED
                )
            self.notch.collapse_notch()
            self.is_showing = False
            
            # Clear all timeouts
            if self.hide_timeout_id:
                GLib.source_remove(self.hide_timeout_id)
                self.hide_timeout_id = None
            if self.unhover_timeout_id:
                GLib.source_remove(self.unhover_timeout_id)
                self.unhover_timeout_id = None
                
            # Show next notification if any
            if self.notification_queue:
                GLib.timeout_add(500, self.show_next_notification)
                
        return False
    
    def on_notification_hover(self):
        """Handle mouse hover - cancel any pending hide"""
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
            self.hide_timeout_id = None
        if self.unhover_timeout_id:
            GLib.source_remove(self.unhover_timeout_id)
            self.unhover_timeout_id = None
    
    def on_notification_unhover(self):
        """Start countdown to hide after unhover"""
        if self.unhover_timeout_id:
            GLib.source_remove(self.unhover_timeout_id)
        self.unhover_timeout_id = GLib.timeout_add(1500, self.hide_notification)

