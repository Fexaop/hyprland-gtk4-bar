# noti.py
from gi.repository import Gtk, GLib

class Notification:
    def __init__(self, title, message, parent_box, remove_callback):
        self.widget = self._create_widget(title, message, remove_callback)
        self.parent_box = parent_box
        self.parent_box.append(self.widget)

    def _create_widget(self, title, message, remove_callback):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.add_css_class("notification")

        title_label = Gtk.Label(label=title)
        title_label.add_css_class("notification-title")
        box.append(title_label)

        message_label = Gtk.Label(label=message)
        message_label.add_css_class("notification-message")
        box.append(message_label)

        close_button = Gtk.Button(label="×")
        close_button.add_css_class("notification-close")
        close_button.connect("clicked", lambda btn: remove_callback(self))
        box.append(close_button)

        box.set_visible(True)
        return box

    def remove(self):
        self.parent_box.remove(self.widget)

class NotificationManager:
    def __init__(self, parent_box, resize_callback):
        self.notifications = []
        self.parent_box = parent_box
        self.resize_callback = resize_callback
        self.max_visible = 3

    def add_notification(self, title, message, timeout=2000):
        def do_add():
            notification = Notification(title, message, self.parent_box, self.remove_notification)
            self.notifications.append(notification)
            
            if len(self.notifications) > self.max_visible:
                old_notif = self.notifications.pop(0)
                old_notif.remove()
            
            self.resize_callback(len(self.notifications))
            GLib.timeout_add(timeout, self.remove_notification, notification)
        
        GLib.idle_add(do_add)

    def remove_notification(self, notification):
        if notification in self.notifications:
            self.notifications.remove(notification)
            notification.remove()
            self.resize_callback(len(self.notifications))
        return False

    def clear_all(self):
        for notif in self.notifications[:]:
            self.remove_notification(notif)