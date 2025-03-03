import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, Pango

# Import notification service instead of using sockets
from service.notification import Notifications, Notification, NotificationCloseReason

import tempfile
import os

class NotificationView(Gtk.Box):
    def __init__(self, notification_center):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-box"
        )
        self.notification_center = notification_center
        self.container_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-container",
            spacing=8
        )
        self.notification_image = Gtk.Image(
            name="notification-image",
        )

        self.container_box.set_hexpand(True)
        self.notification_text = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-text"
        )
        self.notification_text.set_valign(Gtk.Align.CENTER)
        # Summary box with app name
        self.summary_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-summary-box"
        )
        
        self.sender_label = Gtk.Label(name="notification-summary")
        self.sender_label.set_halign(Gtk.Align.START)
        self.sender_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        self.app_name_label = Gtk.Label(name="notification-app-name")
        self.app_name_label.set_halign(Gtk.Align.START)
        self.app_name_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        self.summary_box.append(self.sender_label)
        self.summary_box.append(self.app_name_label)
        
        # Body label
        self.body_label = Gtk.Label()
        self.body_label.set_halign(Gtk.Align.START)
        
        # Add boxes to notification text
        self.notification_text.append(self.summary_box)
        self.notification_text.append(self.body_label)
        
        # Add everything to container
        self.container_box.append(self.notification_image)
        self.container_box.append(self.notification_text)
        # Third box: Close button
        self.close_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="notification-close-box")
        self.close_box.set_valign(Gtk.Align.CENTER)
        
        self.close_button = Gtk.Button(label="×", name="notification-close-button")
        self.close_button.set_halign(Gtk.Align.CENTER)
        self.close_button.connect("clicked", self.on_close_clicked)
        self.close_button.get_style_context().add_class("circular")
        
        self.close_box.append(self.close_button)
        self.container_box.append(self.close_box)
        # Then put the container box in the notification box
        self.append(self.container_box)
        
        # Add click gesture for the notification box
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self.on_notification_click)
        self.container_box.add_controller(gesture)
        
    def update_notification(self, notification):
        """Update the notification view with new data"""
        self.notification_id = notification.id
        
        # Set the text labels
        self.sender_label.set_text(notification.summary)
        self.app_name_label.set_text(notification.app_name)
        print(notification.app_name)
        self.body_label.set_text(notification.body)
        
        # Handle notification image or app icon if present
        if notification.image_texture:
            # Use the image data from notification
            self.notification_image.set_from_paintable(notification.image_texture)
            self.notification_image.set_visible(True)
        elif notification.app_icon and notification.app_icon.strip():
            # Try to use app_icon as fallback
            if os.path.isfile(notification.app_icon):
                # If app_icon is a file path
                try:
                    self.notification_image.set_from_file(notification.app_icon)
                    self.notification_image.set_visible(True)
                except Exception as e:
                    print(f"Error loading icon from file {notification.app_icon}: {e}")
                    self._try_load_icon_name(notification.app_icon)
            else:
                # If app_icon is an icon name
                self._try_load_icon_name(notification.app_icon)
        else:
            # No image or icon available
            self.notification_image.set_visible(False)
            
    def _try_load_icon_name(self, icon_name):
        """Try to load an icon by name from theme"""
        try:
            # Try standard sizes in descending order
            for size in [64, 48, 32, 24, 16]:
                self.notification_image.set_from_icon_name(icon_name)
                self.notification_image.set_pixel_size(size)
                self.notification_image.set_visible(True)
                return
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            self.notification_image.set_visible(False)
            
    def on_notification_click(self, gesture, n_press, x, y):
        """Handle click on notification body"""
        # Only dismiss when clicking on the notification body, not buttons
        widget = gesture.get_widget()
        if widget != self.close_button:
            self.notification_center.hide_notification()
        return True
        
    def on_close_clicked(self, button):
        """Handle close button click"""
        print("Notification close button clicked")  # Debug print
        self.notification_center.hide_notification()
        return True

class NotificationCenter:
    def __init__(self, notch):
        self.notch = notch
        self.current_notification = None
        self.notification_queue = []
        self.is_showing = False
        self.notification_view = NotificationView(self)
        
        # Use the DBus notification service instead of sockets
        self.notifications = Notifications()
        self.notifications.connect('notification-added', self.on_notification_added)
        
    def on_notification_added(self, _, notification_id):
        """Handle new notification from service"""
        notification = self.notifications.get_notification_from_id(notification_id)
        if notification:
            print(f"Received notification: {notification.summary}")
            
            # Add to queue and show if not already showing
            self.notification_queue.append(notification)
            if not self.is_showing:
                self.show_next_notification()
    
    def prepare_notification(self, notification):
        """Process and add notification to the view before showing it"""
        self.notification_view.update_notification(notification)
    
    def show_next_notification(self):
        """Display the next notification in the queue"""
        if not self.notification_queue:
            self.is_showing = False
            return
        
        self.is_showing = True
        notification = self.notification_queue.pop(0)
        self.current_notification = notification
        
        # Process notification and update the view before showing
        self.prepare_notification(notification)
        
        # Show the notification in the notch
        self.notch.open_notch('notification')
        
        # Auto-hide after a delay
        GLib.timeout_add(8000, self.hide_notification)
    
    def hide_notification(self):
        """Hide the current notification"""
        if self.is_showing:
            # Print the previous widget for debugging
            print(f"Previous widget before closing notification: {self.notch.previous_widget}")
            
            # Close the notification with proper reason if it exists
            if self.current_notification:
                self.notifications.close_notification(
                    self.current_notification.id, 
                    NotificationCloseReason.EXPIRED
                )
            
            # Use collapse_notch directly
            self.notch.collapse_notch()
            
            self.is_showing = False
            
            # Show the next notification if there are any
            if self.notification_queue:
                GLib.timeout_add(500, self.show_next_notification)
                
        return False  # for GLib.timeout_add