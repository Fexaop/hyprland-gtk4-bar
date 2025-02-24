#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

import dbus
import dbus.service
import dbus.mainloop.glib

# -------------------------------
# GTK Notification UI Components
# -------------------------------

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
            print("Adding notification:", title)
            notification = Notification(title, message, self.parent_box, self.remove_notification)
            self.notifications.append(notification)
            
            if len(self.notifications) > self.max_visible:
                old_notif = self.notifications.pop(0)
                old_notif.remove()
                print("Removed oldest notification due to max limit")
            
            self.resize_callback(len(self.notifications))
            GLib.timeout_add(timeout, self.remove_notification, notification)
            return False  # Run the idle callback only once
        GLib.idle_add(do_add)

    def remove_notification(self, notification):
        if notification in self.notifications:
            print("Removing notification:", notification)
            self.notifications.remove(notification)
            notification.remove()
            self.resize_callback(len(self.notifications))
        return False  # Ensure the timeout callback runs only once

    def clear_all(self):
        for notif in self.notifications[:]:
            self.remove_notification(notif)

# -----------------------------------------
# DBus Notification Daemon Implementation
# -----------------------------------------

class NotificationDaemon(dbus.service.Object):
    def __init__(self, bus, object_path, manager):
        super().__init__(bus, object_path)
        self.manager = manager

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="susssasa{sv}i", out_signature="u")
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        print("DBus Notification received!")
        print(f"Application: {app_name}")
        print(f"Summary: {summary}")
        print(f"Body: {body}\n")
        # Use expire_timeout if valid, else default to 2000ms.
        timeout = expire_timeout if expire_timeout > 0 else 2000
        # Use the summary as the title and body as the message for our UI notification.
        self.manager.add_notification(summary, body, timeout=timeout)
        return 0

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="as")
    def GetCapabilities(self):
        return ["body"]

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="ssss")
    def GetServerInformation(self):
        return ("PythonGTKNotificationDaemon", "YourVendor", "1.0", "1.2")

# -------------------------------
# Main Application Setup
# -------------------------------

if __name__ == '__main__':
    # Create GTK window and UI box.
    win = Gtk.Window()
    win.set_default_size(300, 200)
    parent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    win.set_child(parent_box)

    def resize_callback(count):
        print(f"Notifications count: {count}")

    manager = NotificationManager(parent_box, resize_callback)

    # Integrate DBus with the GLib main loop (which GTK uses)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()

    # Register our daemon under the standard notifications bus name.
    # If another notification daemon is running, you might need to disable it.
    bus_name = dbus.service.BusName("org.freedesktop.Notifications", session_bus)
    daemon = NotificationDaemon(session_bus, "/org/freedesktop/Notifications", manager)

    win.connect("destroy", Gtk.main_quit)
    win.show()

    Gtk.main()
