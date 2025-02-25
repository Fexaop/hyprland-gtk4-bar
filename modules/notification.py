import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, Pango
import socket
import json
import threading
import time
import base64
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
        self.notification_id = notification.get("id")
        
        # Set the text labels
        self.sender_label.set_text(notification.get("summary", ""))
        self.app_name_label.set_text(notification.get("app_name", ""))
        print(notification.get("app_name", ""))
        self.body_label.set_text(notification.get("body", ""))
        
        # Handle notification image if present
        if "image_data" in notification and notification["image_data"]:
            try:
                # Create a temporary file to store the image
                fd, temp_path = tempfile.mkstemp(suffix=".png")
                os.write(fd, base64.b64decode(notification["image_data"]))
                os.close(fd)
                
                # Load the image from file and display it
                self.notification_image.set_from_file(temp_path)
                self.notification_image.set_visible(True)
                
                # Clean up the temp file when done
                GLib.timeout_add_seconds(10, lambda: os.unlink(temp_path) if os.path.exists(temp_path) else None)
            except Exception as e:
                print(f"Error displaying notification image: {e}")
                self.notification_image.set_visible(False)
        else:
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
        self.notification_center.hide_notification()
        return True

class NotificationCenter:
    # Rest of the NotificationCenter class remains the same
    def __init__(self, notch):
        self.notch = notch
        self.port = 6942
        self.current_notification = None
        self.notification_queue = []
        self.is_showing = False
        self.notification_view = NotificationView(self)
        
        # Setup UDP listener socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Start the listener thread
        self.running = True
        self.thread = threading.Thread(target=self.listen_for_notifications)
        self.thread.daemon = True
        self.thread.start()
        
    def listen_for_notifications(self):
        """Listen for UDP broadcasts from the notification daemon"""
        try:
            self.sock.bind(('', self.port))
            print(f"Listening for notifications on port {self.port}")
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(65535)  # Increased buffer size for images
                    notification = json.loads(data.decode('utf-8'))
                    # Process notification on the main thread
                    GLib.idle_add(self.process_notification, notification)
                except Exception as e:
                    print(f"Error receiving notification: {e}")
                    time.sleep(1)  # Prevent busy loop on error
        except Exception as e:
            print(f"Socket error: {e}")
        finally:
            self.sock.close()
    
    def process_notification(self, notification):
        """Process a received notification"""
        print(f"Received notification: {notification['summary']}")
        
        # Add to queue and show if not already showing
        self.notification_queue.append(notification)
        if not self.is_showing:
            self.show_next_notification()
        
        return False  # for GLib.idle_add
    
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
        self.notch.show_notification()
        
        # Auto-hide after a delay
        GLib.timeout_add(8000, self.hide_notification)
    
    def hide_notification(self):
        """Hide the current notification"""
        if self.is_showing:
            self.notch.hide_notification()
            self.is_showing = False
            
            # Show the next notification if there are any
            if self.notification_queue:
                GLib.timeout_add(500, self.show_next_notification)
                
        return False  # for GLib.timeout_add