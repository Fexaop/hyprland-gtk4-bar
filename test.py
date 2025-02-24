import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import socket
import json
import time

class NotificationDaemon(dbus.service.Object):
    def __init__(self, bus, object_path):
        super().__init__(bus, object_path)
        self.notification_count = 0
        # Setup UDP broadcast socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.port = 6942
        # Start broadcasting
        GLib.timeout_add_seconds(5, self.broadcast_notification)  # Broadcast every 5 seconds

    def broadcast_notification(self):
        self.notification_count += 1
        message = {
            "app_name": "PythonDaemon",
            "summary": f"Notification #{self.notification_count}",
            "body": f"Broadcast message at {time.ctime()}",
            "timestamp": time.time()
        }       
        return True  # Return True to keep the timer running

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="susssasa{sv}i", out_signature="u")
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        print("Notification received!")
        # print(f"Application: {app_name}")
        # print(f"Summary: {summary}")
        # print(f"Body: {body}\n")
        # Broadcast this notification too
        message = {
            "app_name": app_name,
            "summary": summary,
            "body": body,
            "timestamp": time.time()
        }
        try:
            broadcast_msg = json.dumps(message).encode('utf-8')
            self.sock.sendto(broadcast_msg, ('255.255.255.255', self.port))
        except Exception as e:
            print(f"Broadcast error: {e}")
        return 0

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="as")
    def GetCapabilities(self):
        return ["body"]

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="ssss")
    def GetServerInformation(self):
        return ("PythonNotificationDaemon", "YourVendor", "1.0", "1.2")

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    
    bus_name = dbus.service.BusName("org.freedesktop.Notifications", session_bus)
    daemon = NotificationDaemon(session_bus, "/org/freedesktop/Notifications")
    
    print(f"Python notification daemon is running and broadcasting on port {daemon.port}...")
    loop = GLib.MainLoop()
    loop.run()