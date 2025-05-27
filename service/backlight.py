import os
import asyncio
from typing import List, Optional, Callable
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')

from gi.repository import GObject, Gio, GLib

# Constants
SYS_BACKLIGHT = "/sys/class/backlight"


class BacklightDevice(GObject.Object):
    """
    A backlight device using native GTK4/GObject.
    """
    
    # Define GObject properties
    __gproperties__ = {
        'device-name': (str, 'Device Name', 'The name of the backlight device', 
                       '', GObject.ParamFlags.READABLE),
        'brightness': (int, 'Brightness', 'Current brightness level', 
                      -1, GLib.MAXINT, -1, GObject.ParamFlags.READWRITE),
        'max-brightness': (int, 'Max Brightness', 'Maximum brightness level', 
                          -1, GLib.MAXINT, -1, GObject.ParamFlags.READABLE),
    }
    
    def __init__(self, device_name: str):
        super().__init__()
        self._device_name = device_name
        self._brightness = -1
        self._max_brightness = -1
        
        self._PATH_TO_BRIGHTNESS = os.path.join(SYS_BACKLIGHT, device_name, "brightness")
        self._PATH_TO_MAX_BRIGHTNESS = os.path.join(SYS_BACKLIGHT, device_name, "max_brightness")
        
        # Read max brightness
        try:
            with open(self._PATH_TO_MAX_BRIGHTNESS) as f:
                self._max_brightness = int(f.read().strip())
        except (IOError, ValueError) as e:
            print(f"Error reading max brightness for {device_name}: {e}")
            self._max_brightness = -1
        
        # Set up file monitoring
        self._setup_file_monitor()
        
        # Set up DBus proxy for systemd-logind
        self._setup_dbus_proxy()
        
        # Initial brightness sync
        self._sync_brightness()
    
    def _setup_file_monitor(self):
        """Set up file monitoring for brightness changes."""
        try:
            brightness_file = Gio.File.new_for_path(self._PATH_TO_BRIGHTNESS)
            self._file_monitor = brightness_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._file_monitor.connect('changed', self._on_brightness_file_changed)
        except Exception as e:
            print(f"Error setting up file monitor for {self._device_name}: {e}")
            self._file_monitor = None
    
    def _setup_dbus_proxy(self):
        """Set up DBus proxy for systemd-logind session."""
        try:
            # Get session path (simplified - you may need to implement get_session_path())
            session_path = self._get_session_path()
            
            self._session_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,  # interface info
                "org.freedesktop.login1",
                session_path,
                "org.freedesktop.login1.Session",
                None  # cancellable
            )
        except Exception as e:
            print(f"Error setting up DBus proxy: {e}")
            self._session_proxy = None
    
    def _get_session_path(self) -> str:
        """Get the session path for the current user session."""
        # This is a simplified implementation
        # You may need to implement the full get_session_path() logic
        try:
            manager_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.login1",
                "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager",
                None
            )
            
            # Get current session
            result = manager_proxy.call_sync(
                "GetSessionByPID",
                GLib.Variant("(u)", (os.getpid(),)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            
            if result:
                return result.get_child_value(0).get_string()
        except Exception as e:
            print(f"Error getting session path: {e}")
        
        # Fallback - this might not work for all systems
        return "/org/freedesktop/login1/session/auto"
    
    def _on_brightness_file_changed(self, monitor, file, other_file, event_type):
        """Handle brightness file changes."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            self._sync_brightness()
    
    def _sync_brightness(self):
        """Synchronize brightness value from file."""
        try:
            with open(self._PATH_TO_BRIGHTNESS) as f:
                new_brightness = int(f.read().strip())
                if new_brightness != self._brightness:
                    self._brightness = new_brightness
                    self.notify('brightness')
        except (IOError, ValueError) as e:
            print(f"Error reading brightness for {self._device_name}: {e}")
    
    def do_get_property(self, prop):
        """Handle property getting."""
        if prop.name == 'device-name':
            return self._device_name
        elif prop.name == 'brightness':
            return self._brightness
        elif prop.name == 'max-brightness':
            return self._max_brightness
        else:
            raise AttributeError(f'Unknown property {prop.name}')
    
    def do_set_property(self, prop, value):
        """Handle property setting."""
        if prop.name == 'brightness':
            self.set_brightness(value)
        else:
            raise AttributeError(f'Unknown property {prop.name}')
    
    @property
    def device_name(self) -> str:
        """The name of the directory in /sys/class/backlight."""
        return self._device_name
    
    @property
    def max_brightness(self) -> int:
        """The maximum brightness allowed by the device."""
        return self._max_brightness
    
    @property
    def brightness(self) -> int:
        """The current brightness of the device."""
        return self._brightness
    
    def set_brightness(self, value: int) -> None:
        """Set brightness using systemd-logind."""
        if self._session_proxy:
            try:
                self._session_proxy.call_sync(
                    "SetBrightness",
                    GLib.Variant("(ssu)", ("backlight", self._device_name, value)),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None
                )
            except Exception as e:
                print(f"Error setting brightness via DBus: {e}")
        else:
            print("No DBus proxy available for setting brightness")
    
    async def set_brightness_async(self, value: int) -> None:
        """Asynchronously set brightness."""
        if self._session_proxy:
            try:
                loop = asyncio.get_event_loop()
                
                def callback(proxy, result, user_data):
                    try:
                        proxy.call_finish(result)
                        future.set_result(None)
                    except Exception as e:
                        future.set_exception(e)
                
                future = loop.create_future()
                
                self._session_proxy.call(
                    "SetBrightness",
                    GLib.Variant("(ssu)", ("backlight", self._device_name, value)),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None,
                    callback,
                    None
                )
                
                await future
            except Exception as e:
                print(f"Error setting brightness async via DBus: {e}")
        else:
            print("No DBus proxy available for setting brightness")


class BacklightService(GObject.Object):
    """
    A backlight service using native GTK4/GObject.
    Allows controlling device screen brightness.
    """
    
    __gproperties__ = {
        'available': (bool, 'Available', 'Whether backlight devices are available', 
                     False, GObject.ParamFlags.READABLE),
        'brightness': (int, 'Brightness', 'Current brightness of first device', 
                      -1, GLib.MAXINT, -1, GObject.ParamFlags.READWRITE),
        'max-brightness': (int, 'Max Brightness', 'Max brightness of first device', 
                          -1, GLib.MAXINT, -1, GObject.ParamFlags.READABLE),
    }
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        super().__init__()
        self._initialized = True
        self._devices: List[BacklightDevice] = []
        
        # Set up directory monitoring
        self._setup_directory_monitor()
        
        # Initial device sync
        self._sync_devices()
    
    @classmethod
    def get_default(cls) -> 'BacklightService':
        """Get the default backlight service instance."""
        return cls()
    
    def _setup_directory_monitor(self):
        """Set up monitoring of the backlight directory."""
        try:
            backlight_dir = Gio.File.new_for_path(SYS_BACKLIGHT)
            self._dir_monitor = backlight_dir.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self._dir_monitor.connect('changed', self._on_directory_changed)
        except Exception as e:
            print(f"Error setting up directory monitor: {e}")
            self._dir_monitor = None
    
    def _on_directory_changed(self, monitor, file, other_file, event_type):
        """Handle changes in the backlight directory."""
        if event_type in (Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.DELETED):
            self._sync_devices()
    
    def _sync_devices(self):
        """Synchronize the list of backlight devices."""
        old_devices = self._devices
        self._devices = []
        
        try:
            if os.path.exists(SYS_BACKLIGHT):
                for device_name in os.listdir(SYS_BACKLIGHT):
                    device_path = os.path.join(SYS_BACKLIGHT, device_name)
                    if os.path.isdir(device_path):
                        device = BacklightDevice(device_name)
                        self._devices.append(device)
        except Exception as e:
            print(f"Error syncing devices: {e}")
        
        # Connect to brightness changes on the first device
        if len(self._devices) > 0:
            self._devices[0].connect('notify::brightness', self._on_first_device_brightness_changed)
        
        # Clean up old devices
        for device in old_devices:
            if hasattr(device, '_file_monitor') and device._file_monitor:
                device._file_monitor.cancel()
        
        # Notify all properties
        self.notify('available')
        self.notify('brightness')
        self.notify('max-brightness')
    
    def _on_first_device_brightness_changed(self, device, pspec):
        """Handle brightness changes on the first device."""
        self.notify('brightness')
    
    def do_get_property(self, prop):
        """Handle property getting."""
        if prop.name == 'available':
            return len(self._devices) > 0
        elif prop.name == 'brightness':
            return self._devices[0].brightness if len(self._devices) > 0 else -1
        elif prop.name == 'max-brightness':
            return self._devices[0].max_brightness if len(self._devices) > 0 else -1
        else:
            raise AttributeError(f'Unknown property {prop.name}')
    
    def do_set_property(self, prop, value):
        """Handle property setting."""
        if prop.name == 'brightness':
            self.set_brightness(value)
        else:
            raise AttributeError(f'Unknown property {prop.name}')
    
    @property
    def available(self) -> bool:
        """Whether there are controllable backlight devices."""
        return len(self._devices) > 0
    
    @property
    def devices(self) -> List[BacklightDevice]:
        """A list of all backlight devices."""
        return self._devices.copy()
    
    @property
    def brightness(self) -> int:
        """The current brightness of the first backlight device, -1 if none available."""
        return self._devices[0].brightness if len(self._devices) > 0 else -1
    
    def set_brightness(self, value: int) -> None:
        """Set brightness on all devices."""
        for device in self._devices:
            device.set_brightness(value)
    
    async def set_brightness_async(self, value: int) -> None:
        """Asynchronously set brightness for all devices."""
        tasks = []
        for device in self._devices:
            tasks.append(device.set_brightness_async(value))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    @property
    def max_brightness(self) -> int:
        """The maximum brightness of the first backlight device, -1 if none available."""
        return self._devices[0].max_brightness if len(self._devices) > 0 else -1


# Example usage
if __name__ == "__main__":
    import sys
    
    def main():
        # Create the backlight service
        backlight = BacklightService.get_default()
        
        print(f"Backlight available: {backlight.available}")
        print(f"Number of devices: {len(backlight.devices)}")
        
        if backlight.available:
            print(f"Current brightness: {backlight.brightness}")
            print(f"Max brightness: {backlight.max_brightness}")
            
            # Example: Set brightness to 50% of max
            if backlight.max_brightness > 0:
                new_brightness = backlight.max_brightness // 2
                print(f"Setting brightness to: {new_brightness}")
                backlight.set_brightness(new_brightness)
        
        # Keep the program running to monitor changes
        try:
            main_loop = GLib.MainLoop()
            main_loop.run()
        except KeyboardInterrupt:
            print("Exiting...")
            sys.exit(0)
    
    main()