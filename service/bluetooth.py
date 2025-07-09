#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GObject", "2.0")
gi.require_version("GnomeBluetooth", "3.0")

from gi.repository import Gtk, Adw, GObject, GLib, GnomeBluetooth, Gio
from typing import List, Dict, Optional
import logging
import threading

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
ADAPTER_STATE = {
    GnomeBluetooth.AdapterState.ABSENT: "absent",
    GnomeBluetooth.AdapterState.ON: "on",
    GnomeBluetooth.AdapterState.TURNING_ON: "turning-on",
    GnomeBluetooth.AdapterState.TURNING_OFF: "turning-off",
    GnomeBluetooth.AdapterState.OFF: "off",
}

class BluetoothDevice(GObject.Object):
    """A Bluetooth device wrapper."""
    
    __gtype_name__ = 'CustomBluetoothDevice'
    
    # Define signals
    __gsignals__ = {
        'removed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'property-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self, client: GnomeBluetooth.Client, gdevice: GnomeBluetooth.Device):
        super().__init__()
        self._client = client
        self._gdevice = gdevice
        
        # Connect to property change notifications
        for prop_name in [
            "address", "alias", "battery-level", "battery-percentage",
            "connected", "name", "paired", "trusted"
        ]:
            gdevice.connect(
                f"notify::{prop_name}",
                lambda x, y, prop_name=prop_name: self.emit('property-changed', prop_name)
            )
        
        gdevice.connect("notify::icon", lambda x, y: self.emit('property-changed', 'icon-name'))
    
    @property
    def gdevice(self) -> GnomeBluetooth.Device:
        return self._gdevice
    
    @property
    def address(self) -> str:
        return self._gdevice.props.address or ""
    
    @property
    def alias(self) -> str:
        return self._gdevice.props.alias or ""
    
    @property
    def battery_level(self) -> int:
        return self._gdevice.props.battery_level
    
    @property
    def battery_percentage(self) -> float:
        return self._gdevice.props.battery_percentage
    
    @property
    def connectable(self) -> bool:
        return self._gdevice.props.connectable
    
    @property
    def connected(self) -> bool:
        return self._gdevice.props.connected
    
    @property
    def icon_name(self) -> str:
        return self._gdevice.props.icon or "bluetooth"
    
    @property
    def name(self) -> str:
        return self._gdevice.props.name or ""
    
    @property
    def paired(self) -> bool:
        return self._gdevice.props.paired
    
    @property
    def trusted(self) -> bool:
        return self._gdevice.props.trusted
    
    @property
    def device_type(self) -> str:
        return GnomeBluetooth.type_to_string(self._gdevice.props.type)
    
    def _connect_service(self, connect: bool) -> bool:
        """Connect or disconnect from the device service."""
        try:
            success = self._client.connect_service(self._gdevice.get_object_path(), connect, None)
            logger.info(f"connect_service returned {success} for {'connect' if connect else 'disconnect'}")
            return success
        except Exception as e:
            logger.warning(f"Bluetooth connection error: {e}")
            return False
    
    def connect_to(self) -> bool:
        """Connect to this device."""
        return self._connect_service(True)
    
    def disconnect_from(self) -> bool:
        """Disconnect from this device."""
        return self._connect_service(False)
    
    def pair_device(self) -> bool:
        """Pair with this device using D-Bus."""
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        try:
            bus.call_sync(
                "org.bluez",
                self._gdevice.get_object_path(),
                "org.bluez.Device1",
                "Pair",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            logger.info(f"Paired device {self.address}")
            return True
        except Exception as e:
            logger.warning(f"Bluetooth pairing error: {e}")
            return False

class BluetoothService(GObject.Object):
    """A Bluetooth service using native GTK 4 and GObject."""
    
    __gtype_name__ = 'CustomBluetoothService'
    
    # Define signals
    __gsignals__ = {
        'device-added': (GObject.SignalFlags.RUN_FIRST, None, (GObject.Object,)),
        'device-removed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'property-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self):
        super().__init__()
        self._client = GnomeBluetooth.Client.new()
        self._devices: Dict[str, BluetoothDevice] = {}
        
        # Connect to client signals
        self._client.connect("device-added", self._on_device_added)
        self._client.connect("device-removed", self._on_device_removed)
        
        # Connect to property change notifications
        for key, prop_name in {
            "default-adapter-powered": "powered",
            "default-adapter-setup-mode": "setup-mode",
            "default-adapter-state": "state",
        }.items():
            self._client.connect(
                f"notify::{key}",
                lambda x, y, prop_name=prop_name: self.emit('property-changed', prop_name)
            )
        
        # Add existing devices
        for gdevice in self._client.get_devices():
            self._on_device_added(None, gdevice)
    
    @property
    def client(self) -> GnomeBluetooth.Client:
        return self._client
    
    @property
    def devices(self) -> List[BluetoothDevice]:
        return list(self._devices.values())
    
    @property
    def connected_devices(self) -> List[BluetoothDevice]:
        return [device for device in self._devices.values() if device.connected]
    
    @property
    def powered(self) -> bool:
        return self._client.props.default_adapter_powered
    
    @powered.setter
    def powered(self, value: bool) -> None:
        self._client.props.default_adapter_powered = value
    
    @property
    def state(self) -> str:
        return ADAPTER_STATE.get(self._client.props.default_adapter_state, "absent")
    
    @property
    def setup_mode(self) -> bool:
        return self._client.props.default_adapter_setup_mode
    
    @setup_mode.setter
    def setup_mode(self, value: bool) -> None:
        self._client.props.default_adapter_setup_mode = value
    
    def remove_device(self, device: BluetoothDevice) -> None:
        """Remove (unpair) the specified device using D-Bus."""
        adapter_path = self._client.props.default_adapter
        if not adapter_path:
            logger.warning("No default adapter found")
            return
        
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        try:
            bus.call_sync(
                "org.bluez",
                adapter_path,
                "org.bluez.Adapter1",
                "RemoveDevice",
                GLib.Variant("(o)", (device.gdevice.get_object_path(),)),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            logger.info(f"Removed device {device.address}")
        except Exception as e:
            logger.warning(f"Failed to remove device: {e}")
    
    def _on_device_added(self, client, gdevice: GnomeBluetooth.Device) -> None:
        device = BluetoothDevice(self._client, gdevice)
        if device.device_type.lower() == "unknown":
            logger.info(f"Skipping device {device.address} with unknown type")
            return
        
        object_path = gdevice.get_object_path()
        self._devices[object_path] = device
        
        device.connect(
            'property-changed',
            lambda dev, prop_name: self._on_device_property_changed(dev, prop_name)
        )
        
        self.emit('device-added', device)
        self.emit('property-changed', 'devices')
    
    def _on_device_removed(self, client, object_path: str) -> None:
        if object_path not in self._devices:
            return
        
        device = self._devices.pop(object_path)
        device.emit('removed')
        
        self.emit('device-removed', object_path)
        self.emit('property-changed', 'devices')
        self.emit('property-changed', 'connected-devices')
    
    def _on_device_property_changed(self, device: BluetoothDevice, prop_name: str) -> None:
        if prop_name == 'connected':
            self.emit('property-changed', 'connected-devices')

class DeviceRow(Adw.ActionRow):
    """A row widget for displaying a Bluetooth device."""
    
    def __init__(self, device: BluetoothDevice, service: BluetoothService):
        super().__init__()
        self.device = device
        self.service = service
        
        # Set up the row
        self.set_title(device.alias or device.name or "Unknown Device")
        self.set_subtitle(f"{device.address} • {device.device_type}")
        
        # Add icon
        icon = Gtk.Image.new_from_icon_name(device.icon_name)
        icon.set_icon_size(Gtk.IconSize.LARGE)
        self.add_prefix(icon)
        
        # Add status labels
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        # Connection status
        self.connection_label = Gtk.Label()
        self.connection_label.set_css_classes(["caption"])
        self.status_box.append(self.connection_label)
        
        # Battery level if available
        self.battery_label = Gtk.Label()
        self.battery_label.set_css_classes(["caption"])
        if device.battery_percentage > 0:
            self.battery_label.set_text(f"Battery: {device.battery_percentage:.0f}%")
            self.status_box.append(self.battery_label)
        
        self.add_suffix(self.status_box)
        
        # Initialize forget button reference
        self.forget_button = None
        self.action_button = Gtk.Button()
        self.action_button.set_valign(Gtk.Align.CENTER)
        self.action_button.connect("clicked", self._on_action_clicked)
        self.add_suffix(self.action_button)
        
        # Add forget button for paired devices
        if self.device.paired:
            self.forget_button = Gtk.Button()
            self.forget_button.set_label("Forget")
            self.forget_button.set_css_classes(["destructive-action"])
            self.forget_button.set_valign(Gtk.Align.CENTER)
            self.forget_button.connect("clicked", self._on_forget_clicked)
            self.add_suffix(self.forget_button)
        
        # Update button state
        self._update_status()
        
        # Connect to device property changes
        device.connect('property-changed', self._on_device_property_changed)
    
    def _update_status(self):
        """Update the status display and button."""
        if self.device.connected:
            self.connection_label.set_text("Connected")
            self.connection_label.set_css_classes(["caption", "success"])
            self.action_button.set_label("Disconnect")
            self.action_button.set_css_classes(["destructive-action"])
        elif self.device.paired:
            self.connection_label.set_text("Paired")
            self.connection_label.set_css_classes(["caption"])
            self.action_button.set_label("Connect")
            self.action_button.set_css_classes(["suggested-action"])
        else:
            self.connection_label.set_text("Not paired")
            self.connection_label.set_css_classes(["caption", "dim-label"])
            self.action_button.set_label("Connect")
            self.action_button.set_css_classes(["suggested-action"])
        
        self.action_button.set_sensitive(True)
    
    def _on_forget_clicked(self, button):
        """Handle forget device button click."""
        button.set_sensitive(False)
        button.set_label("Removing...")
        
        def on_complete(success, error=None):
            def update_ui():
                button.set_sensitive(True)
                button.set_label("Forget")
                
                if not success and error:
                    toast = Adw.Toast.new(f"Error: {error}")
                    toast.set_timeout(3)
                    parent = self.get_root()
                    if hasattr(parent, 'add_toast'):
                        parent.add_toast(toast)
            
            GLib.idle_add(update_ui)
        
        def remove_device():
            try:
                self.service.remove_device(self.device)
                on_complete(True)
            except Exception as e:
                logger.warning(f"Failed to remove device: {e}")
                on_complete(False, str(e))
        
        threading.Thread(target=remove_device, daemon=True).start()
    
    def _on_device_property_changed(self, device, prop_name):
        """Handle device property changes."""
        def update_ui():
            self._update_status()
            
            if prop_name == 'connected':
                if device.connected:
                    message = f"Connected to {device.alias}"
                else:
                    message = f"Disconnected from {device.alias}"
                toast = Adw.Toast.new(message)
                toast.set_timeout(2)
                parent = self.get_root()
                if hasattr(parent, 'add_toast'):
                    parent.add_toast(toast)
            
            if prop_name == 'paired' and device.paired:
                toast = Adw.Toast.new(f"Paired with {device.alias}")
                toast.set_timeout(2)
                parent = self.get_root()
                if hasattr(parent, 'add_toast'):
                    parent.add_toast(toast)
            
            if prop_name == 'paired':
                if device.paired and not self.forget_button:
                    self.forget_button = Gtk.Button()
                    self.forget_button.set_label("Forget")
                    self.forget_button.set_css_classes(["destructive-action"])
                    self.forget_button.set_valign(Gtk.Align.CENTER)
                    self.forget_button.connect("clicked", self._on_forget_clicked)
                    self.add_suffix(self.forget_button)
                elif not device.paired and self.forget_button:
                    self.remove(self.forget_button)
                    self.forget_button = None
            
            if prop_name == 'battery-percentage' and device.battery_percentage > 0:
                if not self.battery_label.get_parent():
                    self.status_box.append(self.battery_label)
                self.battery_label.set_text(f"Battery: {device.battery_percentage:.0f}%")
            elif prop_name == 'battery-percentage' and device.battery_percentage <= 0:
                if self.battery_label.get_parent():
                    self.status_box.remove(self.battery_label)
        
        GLib.idle_add(update_ui)
    
    def _on_action_clicked(self, button):
        """Handle connect/disconnect/pair button clicks."""
        button.set_sensitive(False)
        button.set_label("Working...")
        
        def on_complete():
            def update_ui():
                button.set_sensitive(True)
                self._update_status()
            GLib.idle_add(update_ui)
        
        def run_operation():
            try:
                if self.device.connected:
                    self.device.disconnect_from()
                else:
                    if not self.device.paired:
                        self.device.pair_device()
                    self.device.connect_to()
                on_complete()
            except Exception as e:
                logger.warning(f"Operation failed: {e}")
                on_complete()
        
        threading.Thread(target=run_operation, daemon=True).start()

class BluetoothWindow(Adw.ApplicationWindow):
    """Main Bluetooth management window."""
    
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Bluetooth Manager")
        self.set_default_size(600, 700)
        
        self.bt_service = BluetoothService()
        
        self._create_ui()
        
        self.bt_service.connect('device-added', self._on_device_added)
        self.bt_service.connect('device-removed', self._on_device_removed)
        self.bt_service.connect('property-changed', self._on_service_property_changed)
        
        self._populate_devices()
        self._update_adapter_status()
    
    def _create_ui(self):
        """Create the user interface."""
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)
        
        header_bar = Adw.HeaderBar()
        main_box.append(header_bar)
        
        refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh devices")
        refresh_button.connect("clicked", self._on_refresh_clicked)
        header_bar.pack_start(refresh_button)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        scrolled.set_child(content_box)
        
        self.adapter_group = Adw.PreferencesGroup()
        self.adapter_group.set_title("Bluetooth Adapter")
        content_box.append(self.adapter_group)
        
        self.power_row = Adw.SwitchRow()
        self.power_row.set_title("Bluetooth")
        self.power_row.set_subtitle("Enable Bluetooth adapter")
        self.power_row.connect("notify::active", self._on_power_toggled)
        self.adapter_group.add(self.power_row)
        
        self.scan_row = Adw.SwitchRow()
        self.scan_row.set_title("Discoverable")
        self.scan_row.set_subtitle("Make this device discoverable and scan for devices")
        self.scan_row.connect("notify::active", self._on_scan_toggled)
        self.adapter_group.add(self.scan_row)
        
        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Status")
        self.adapter_group.add(self.status_row)
        
        self.devices_group = Adw.PreferencesGroup()
        self.devices_group.set_title("Devices")
        content_box.append(self.devices_group)
        
        self.no_devices_row = Adw.ActionRow()
        self.no_devices_row.set_title("No devices found")
        self.no_devices_row.set_subtitle("Turn on discoverable mode to scan for devices")
        self.devices_group.add(self.no_devices_row)
        
        self.device_rows = {}
    
    def _update_adapter_status(self):
        """Update adapter status display."""
        self.power_row.set_active(self.bt_service.powered)
        self.scan_row.set_active(self.bt_service.setup_mode)
        self.scan_row.set_sensitive(self.bt_service.powered)
        
        state = self.bt_service.state
        connected_count = len(self.bt_service.connected_devices)
        
        if state == "on":
            status_text = f"Active • {connected_count} connected"
        elif state == "turning-on":
            status_text = "Turning on..."
        elif state == "turning-off":
            status_text = "Turning off..."
        elif state == "off":
            status_text = "Off"
        else:
            status_text = "No adapter"
        
        self.status_row.set_subtitle(status_text)
    
    def _populate_devices(self):
        """Populate the devices list, excluding unknown types."""
        for row in self.device_rows.values():
            self.devices_group.remove(row)
        self.device_rows.clear()
        
        devices = [device for device in self.bt_service.devices if device.device_type.lower() != "unknown"]
        if devices:
            self.devices_group.remove(self.no_devices_row)
            for device in devices:
                self._add_device_row(device)
        else:
            if self.no_devices_row.get_parent() is None:
                self.devices_group.add(self.no_devices_row)
    
    def _add_device_row(self, device: BluetoothDevice):
        """Add a device row to the UI."""
        if self.no_devices_row.get_parent():
            self.devices_group.remove(self.no_devices_row)
        
        row = DeviceRow(device, self.bt_service)
        self.devices_group.add(row)
        self.device_rows[device.address] = row
    
    def _remove_device_row(self, device_address: str):
        """Remove a device row from the UI."""
        if device_address in self.device_rows:
            row = self.device_rows.pop(device_address)
            self.devices_group.remove(row)
            
            if not self.device_rows and self.no_devices_row.get_parent() is None:
                self.devices_group.add(self.no_devices_row)
    
    def _on_device_added(self, service, device):
        """Handle device addition."""
        GLib.idle_add(lambda: self._add_device_row(device))
    
    def _on_device_removed(self, service, object_path):
        """Handle device removal."""
        for address, row in list(self.device_rows.items()):
            if row.device.gdevice.get_object_path() == object_path:
                GLib.idle_add(lambda: self._remove_device_row(address))
                break
    
    def _on_service_property_changed(self, service, prop_name):
        """Handle service property changes."""
        GLib.idle_add(self._update_adapter_status)
    
    def _on_power_toggled(self, switch, param):
        """Handle power switch toggle."""
        if switch.get_active() != self.bt_service.powered:
            self.bt_service.powered = switch.get_active()
    
    def _on_scan_toggled(self, switch, param):
        """Handle scan switch toggle."""
        if switch.get_active() != self.bt_service.setup_mode:
            self.bt_service.setup_mode = switch.get_active()
    
    def _on_refresh_clicked(self, button):
        """Handle refresh button click."""
        self._populate_devices()
        self._update_adapter_status()
        
        toast = Adw.Toast.new("Refreshed")
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)
    
    def add_toast(self, toast):
        """Add a toast notification."""
        self.toast_overlay.add_toast(toast)

class BluetoothApp(Adw.Application):
    """Main application class."""
    
    def __init__(self):
        super().__init__(application_id="com.example.bluetooth-manager")
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        """Called when the application is activated."""
        self.window = BluetoothWindow(self)
        self.window.present()

if __name__ == "__main__":
    app = BluetoothApp()
    app.run()