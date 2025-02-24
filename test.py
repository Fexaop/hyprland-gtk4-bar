import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

class NotificationDaemon(dbus.service.Object):
    def __init__(self, bus, object_path):
        super().__init__(bus, object_path)

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="susssasa{sv}i", out_signature="u")
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        print("Notification received!")
        print(f"Application: {app_name}")
        print(f"Summary: {summary}")
        print(f"Body: {body}\n")
        # Return 0 as a dummy notification ID
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
    # Initialize the main loop for DBus
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()

    # Register the daemon under the standard Notifications interface name.
    # Note: If your system already has a notification daemon running,
    # you might need to disable it to test this code.
    bus_name = dbus.service.BusName("org.freedesktop.Notifications", session_bus)
    daemon = NotificationDaemon(session_bus, "/org/freedesktop/Notifications")
    
    print("Python notification daemon is running...")
    loop = GLib.MainLoop()
    loop.run()
