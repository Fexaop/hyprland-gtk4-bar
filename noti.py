import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import socket
import json
import time
import base64
import os
from PIL import Image
import io

class NotificationDaemon(dbus.service.Object):
    def __init__(self, bus, object_path):
        super().__init__(bus, object_path)
        # Setup UDP broadcast socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.port = 6942
        self.notifications = []  # Store recent notifications
        self.next_id = 1  # Start with ID 1
        self.temp_dir = "/tmp/notch-notifications"
        
        # Create temp directory for images if it doesn't exist
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="susssasa{sv}i", out_signature="u")
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        # Use either the replaces_id or generate a new ID within UInt32 bounds
        if replaces_id > 0:
            notification_id = replaces_id
        else:
            notification_id = self.next_id
            self.next_id = (self.next_id + 1) % 4294967295  # Stay within UInt32 bounds
        
        # Process image data
        image_path = None
        
        # Check for image-data, image_data or icon_data
        if 'image-data' in hints or 'image_data' in hints or 'icon_data' in hints:
            image_data = None
            if 'image-data' in hints:
                image_data = hints['image-data']
            elif 'image_data' in hints:
                image_data = hints['image_data']
            elif 'icon_data' in hints:
                image_data = hints['icon_data']
            
            if image_data:
                try:
                    # Extract image data (width, height, rowstride, has_alpha, bits_per_sample, channels, data)
                    width, height, rowstride, has_alpha, bits_per_sample, channels, raw_data = image_data
                    
                    # Convert to PIL image and save as temp file
                    image_path = f"{self.temp_dir}/notification_{notification_id}.png"
                    
                    # Create PIL image from raw data
                    if has_alpha:
                        mode = 'RGBA'
                    else:
                        mode = 'RGB'
                    
                    # Convert dbus.Array to bytes
                    byte_data = bytes(raw_data)
                    
                    # Create the image
                    img = Image.frombytes(mode, (width, height), byte_data)
                    img.save(image_path)
                    
                    print(f"Saved notification image to {image_path}")
                    
                except Exception as e:
                    print(f"Error processing image data: {e}")
                    image_path = None
        
        # Check for image-path
        elif 'image-path' in hints:
            image_path = hints['image-path']
            if not os.path.exists(image_path):
                image_path = None
        
        # Create notification object
        message = {
            "id": notification_id,
            "app_name": app_name,
            "app_icon": app_icon,
            "summary": summary,
            "body": body,
            "timestamp": time.time(),
            "replaces_id": replaces_id,
            "image_path": image_path
        }
        
        # Store notification
        if replaces_id > 0:
            # Replace existing notification if it exists
            for i, notif in enumerate(self.notifications):
                if notif.get("id") == replaces_id:
                    self.notifications[i] = message
                    break
            else:
                self.notifications.append(message)
        else:
            self.notifications.append(message)
        
        # Keep only the 10 most recent notifications
        self.notifications = sorted(self.notifications, key=lambda x: x["timestamp"], reverse=True)[:10]
        
        try:
            # Convert image_path to base64 if it exists for easier transmission
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as img_file:
                    img_data = img_file.read()
                    message["image_data"] = base64.b64encode(img_data).decode('utf-8')
            
            # Broadcast the notification
            broadcast_msg = json.dumps(message).encode('utf-8')
            self.sock.sendto(broadcast_msg, ('255.255.255.255', self.port))
            print(f"Notification sent via UDP: {app_name} - {summary}")
        except Exception as e:
            print(f"Broadcast error: {e}")
            
        return notification_id

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="as")
    def GetCapabilities(self):
        return ["body", "icon-static", "actions", "image"]

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="ssss")
    def GetServerInformation(self):
        return ("PythonNotificationDaemon", "YourVendor", "1.0", "1.2")
        
    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="u", out_signature="")
    def CloseNotification(self, id):
        for i, notif in enumerate(self.notifications):
            if notif.get("id") == id:
                # Remove any associated image file
                image_path = notif.get("image_path")
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except:
                        pass
                del self.notifications[i]
                break

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    
    bus_name = dbus.service.BusName("org.freedesktop.Notifications", session_bus)
    daemon = NotificationDaemon(session_bus, "/org/freedesktop/Notifications")
    
    print(f"Python notification daemon is running and broadcasting on port {daemon.port}...")
    loop = GLib.MainLoop()
    loop.run()