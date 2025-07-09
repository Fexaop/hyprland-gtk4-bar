#!/usr/bin/env python3

import sys
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import IntEnum

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')
gi.require_version('NM', '1.0')

from gi.repository import Gtk, GLib, Gio, GObject, NM


class ConnectionState(IntEnum):
    """NetworkManager connection states"""
    UNKNOWN = 0
    ACTIVATING = 1
    ACTIVATED = 2
    DEACTIVATING = 3
    DEACTIVATED = 4


class DeviceState(IntEnum):
    """NetworkManager device states"""
    UNKNOWN = 0
    UNMANAGED = 10
    UNAVAILABLE = 20
    DISCONNECTED = 30
    PREPARE = 40
    CONFIG = 50
    NEED_AUTH = 60
    IP_CONFIG = 70
    IP_CHECK = 80
    SECONDARIES = 90
    ACTIVATED = 100
    DEACTIVATING = 110
    FAILED = 120


@dataclass
class AccessPoint:
    """Represents a WiFi access point"""
    bssid: str
    ssid: str
    strength: int
    frequency: int
    last_seen: int
    is_active: bool
    icon_name: str


class NetworkSignals(GObject.GObject):
    """Custom signals for network events"""

    __gsignals__ = {
        'wifi-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'wifi-enabled-changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        'ethernet-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)), # state
        'device-ready': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'connection-added': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'connection-removed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }


class WiFiManager(GObject.GObject):
    """Manages WiFi connections and access points"""

    def __init__(self, client: NM.Client, device: NM.DeviceWifi):
        super().__init__()
        self.client = client
        self.device = device
        self.active_ap: Optional[NM.AccessPoint] = None
        self.ap_signal_id: Optional[int] = None
        self.signals = NetworkSignals()

        # Connect to NetworkManager signals
        self.client.connect('notify::wireless-enabled', self._on_wireless_enabled_changed)
        self.client.connect('notify::primary-connection', self._on_primary_connection_changed)
        self.client.connect('notify::connectivity', self._on_connectivity_changed)

        if self.device:
            self.device.connect('notify::active-access-point', self._on_active_ap_changed)
            self.device.connect('access-point-added', self._on_access_point_added)
            self.device.connect('access-point-removed', self._on_access_point_removed)
            self.device.connect('state-changed', self._on_state_changed)
            self.device.connect('notify::active-connection', self._on_active_connection_changed)
            self._update_active_ap()

            # Monitor active connection changes
            active_conn = self.device.get_active_connection()
            if active_conn:
                active_conn.connect('notify::state', self._on_active_connection_state_changed)

    def _on_wireless_enabled_changed(self, client, pspec):
        """Handle wireless enabled/disabled events"""
        print(f"WiFi enabled changed: {self.enabled}")
        self.signals.emit('wifi-enabled-changed', self.enabled)
        self.signals.emit('wifi-changed')

    def _on_primary_connection_changed(self, client, pspec):
        """Handle primary connection changes"""
        print("Primary connection changed")
        self.signals.emit('wifi-changed')

    def _on_connectivity_changed(self, client, pspec):
        """Handle connectivity changes"""
        print(f"Connectivity changed: {client.get_connectivity()}")
        self.signals.emit('wifi-changed')

    def _on_active_ap_changed(self, device, pspec):
        """Handle active access point changes"""
        print("Active AP changed")
        self._update_active_ap()
        self.signals.emit('wifi-changed')

    def _on_active_connection_changed(self, device, pspec):
        """Handle active connection changes"""
        print("Active connection changed")
        # Monitor new active connection
        active_conn = device.get_active_connection()
        if active_conn:
            active_conn.connect('notify::state', self._on_active_connection_state_changed)
        self.signals.emit('wifi-changed')

    def _on_active_connection_state_changed(self, connection, pspec):
        """Handle active connection state changes"""
        state = connection.get_state()
        print(f"Active connection state changed: {state}")
        self.signals.emit('wifi-changed')

    def _on_access_point_added(self, device, ap):
        """Handle new access point detection"""
        ssid_bytes = ap.get_ssid()
        ssid = NM.utils_ssid_to_utf8(ssid_bytes.get_data()) if ssid_bytes else "Unknown"
        print(f"Access point added: {ssid}")
        self.signals.emit('wifi-changed')

    def _on_access_point_removed(self, device, ap):
        """Handle access point removal"""
        ssid_bytes = ap.get_ssid()
        ssid = NM.utils_ssid_to_utf8(ssid_bytes.get_data()) if ssid_bytes else "Unknown"
        print(f"Access point removed: {ssid}")
        self.signals.emit('wifi-changed')

    def _on_state_changed(self, device, new_state, old_state, reason):
        """Handle device state changes"""
        state_names = {
            NM.DeviceState.UNMANAGED: "unmanaged",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.IP_CHECK: "ip_check",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }
        old_name = state_names.get(old_state, f"unknown({old_state})")
        new_name = state_names.get(new_state, f"unknown({new_state})")
        print(f"Device state changed: {old_name} -> {new_name}")
        self.signals.emit('wifi-changed')

    def _update_active_ap(self):
        """Update the active access point and its signal monitoring"""
        if self.active_ap and self.ap_signal_id:
            try:
                self.active_ap.disconnect(self.ap_signal_id)
            except TypeError: # Can happen if the object is already gone
                pass
            self.ap_signal_id = None

        self.active_ap = self.device.get_active_access_point()

        if self.active_ap:
            self.ap_signal_id = self.active_ap.connect('notify::strength', self._on_strength_changed)

    def _on_strength_changed(self, ap, pspec):
        """Handle signal strength changes"""
        # print(f"Signal strength changed: {ap.get_strength()}%")
        self.signals.emit('wifi-changed')

    def _get_signal_icon(self, strength: int, is_connected: bool = False) -> str:
        """Get appropriate icon name for signal strength"""
        if strength >= 80:
            return "network-wireless-signal-excellent-symbolic"
        elif strength >= 60:
            return "network-wireless-signal-good-symbolic"
        elif strength >= 40:
            return "network-wireless-signal-ok-symbolic"
        elif strength >= 20:
            return "network-wireless-signal-weak-symbolic"
        else:
            return "network-wireless-signal-none-symbolic"

    @property
    def enabled(self) -> bool:
        """Check if WiFi is enabled"""
        return self.client.wireless_get_enabled()

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable WiFi using D-Bus"""
        self._set_wireless_enabled_async(value)

    def _set_wireless_enabled_async(self, enabled: bool, callback: Optional[Callable] = None):
        """Set wireless enabled state using proper D-Bus method"""
        def on_wireless_set_complete(source, result, user_data):
            try:
                source.call_finish(result)
                if callback:
                    callback(True, "Wireless state changed successfully")
            except Exception as e:
                if callback:
                    callback(False, str(e))

        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                'org.freedesktop.NetworkManager',
                '/org/freedesktop/NetworkManager',
                'org.freedesktop.NetworkManager',
                None
            )

            proxy.call(
                'org.freedesktop.DBus.Properties.Set',
                GLib.Variant('(ssv)', [
                    'org.freedesktop.NetworkManager',
                    'WirelessEnabled',
                    GLib.Variant('b', enabled)
                ]),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                on_wireless_set_complete,
                None
            )
        except Exception as e:
            if callback:
                callback(False, str(e))

    def set_enabled_async(self, enabled: bool, callback: Optional[Callable] = None):
        """Public method to set wireless enabled state asynchronously"""
        self._set_wireless_enabled_async(enabled, callback)

    @property
    def strength(self) -> int:
        """Get current connection signal strength"""
        return self.active_ap.get_strength() if self.active_ap else -1

    @property
    def frequency(self) -> int:
        """Get current connection frequency"""
        return self.active_ap.get_frequency() if self.active_ap else -1

    @property
    def ssid(self) -> str:
        """Get current connection SSID"""
        if not self.active_ap:
            return "Disconnected"

        ssid_bytes = self.active_ap.get_ssid()
        if ssid_bytes:
            return NM.utils_ssid_to_utf8(ssid_bytes.get_data())
        return "Unknown"

    @property
    def state(self) -> str:
        """Get device state as string"""
        state_map = {
            NM.DeviceState.UNMANAGED: "unmanaged",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.IP_CHECK: "ip_check",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }
        return state_map.get(self.device.get_state(), "unknown")

    @property
    def connection_state(self) -> str:
        """Get connection state as string"""
        active_conn = self.device.get_active_connection()
        if not active_conn:
            return "disconnected"

        state_map = {
            NM.ActiveConnectionState.UNKNOWN: "unknown",
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }
        return state_map.get(active_conn.get_state(), "unknown")

    @property
    def icon_name(self) -> str:
        """Get appropriate icon for current WiFi state"""
        if not self.enabled:
            return "network-wireless-disabled-symbolic"

        if not self.active_ap:
            return "network-wireless-offline-symbolic"

        if self.connection_state == "activated":
            return self._get_signal_icon(self.strength, True)
        elif self.connection_state == "activating":
            return "network-wireless-acquiring-symbolic"

        return "network-wireless-offline-symbolic"

    def get_access_points(self) -> List[AccessPoint]:
        """Get list of available access points"""
        aps = self.device.get_access_points() or []
        access_points = []

        active_ap_bssid = self.active_ap.get_bssid() if self.active_ap else None

        for ap in aps:
            ssid_bytes = ap.get_ssid()
            ssid = NM.utils_ssid_to_utf8(ssid_bytes.get_data()) if ssid_bytes else "Unknown"

            strength = ap.get_strength()

            access_point = AccessPoint(
                bssid=ap.get_bssid(),
                ssid=ssid,
                strength=strength,
                frequency=ap.get_frequency(),
                last_seen=ap.get_last_seen(),
                is_active=(ap.get_bssid() == active_ap_bssid),
                icon_name=self._get_signal_icon(strength)
            )
            access_points.append(access_point)

        return access_points

    def scan_async(self, callback: Optional[Callable] = None):
        """Request WiFi scan asynchronously"""
        def scan_finished(device, result):
            try:
                device.request_scan_finish(result)
                print("WiFi scan completed")
                self.signals.emit('wifi-changed')
                if callback:
                    callback(True, None)
            except Exception as e:
                print(f"WiFi scan failed: {e}")
                if callback:
                    callback(False, str(e))

        self.device.request_scan_async(None, scan_finished)
        
    # --- START OF CHANGE 1 ---
    # Added a dedicated helper method to find saved connections.
    # This makes the logic cleaner and reusable in the GUI.
    def find_connection_by_ssid(self, ssid: str) -> Optional[NM.Connection]:
        """Finds a saved connection profile for a given SSID."""
        for connection in self.client.get_connections():
            if connection.get_connection_type() == "802-11-wireless":
                s_wireless = connection.get_setting_wireless()
                if s_wireless:
                    conn_ssid_bytes = s_wireless.get_ssid()
                    if conn_ssid_bytes and NM.utils_ssid_to_utf8(conn_ssid_bytes.get_data()) == ssid:
                        return connection
        return None
    # --- END OF CHANGE 1 ---

    def connect_to_ap(self, ssid: str, password: str = "", callback: Optional[Callable] = None):
        """
        Connect to a WiFi access point.
        If a saved connection exists, it will be activated.
        Otherwise, a new connection will be created.
        """
        target_ap = None
        for ap in self.device.get_access_points() or []:
            ap_ssid_bytes = ap.get_ssid()
            if ap_ssid_bytes:
                ap_ssid = NM.utils_ssid_to_utf8(ap_ssid_bytes.get_data())
                if ap_ssid == ssid:
                    target_ap = ap
                    break

        if not target_ap:
            if callback:
                callback(False, f"Access point '{ssid}' not found in scan results.")
            return

        existing_connection = self.find_connection_by_ssid(ssid)

        def activation_callback(client, result):
            try:
                active_connection = client.activate_connection_finish(result)
                print(f"Successfully activated connection for {ssid}")
                if callback:
                    callback(True, "Connected successfully")
            except Exception as e:
                print(f"Failed to connect to {ssid}: {e}")
                if callback:
                    callback(False, str(e))

        if existing_connection:
            print(f"Found existing connection for {ssid}. Activating...")
            self.client.activate_connection_async(
                existing_connection,
                self.device,
                None, # Use None for AP path, NM will find the best one
                None,
                activation_callback
            )
        else:
            print(f"No existing connection for {ssid}. Creating a new one...")
            connection = NM.SimpleConnection.new()

            s_con = NM.SettingConnection.new()
            s_con.set_property("id", ssid)
            s_con.set_property("type", "802-11-wireless")
            s_con.set_property("autoconnect", True)
            connection.add_setting(s_con)

            s_wifi = NM.SettingWireless.new()
            s_wifi.set_property("ssid", GLib.Bytes.new(ssid.encode('utf-8')))
            s_wifi.set_property("mode", "infrastructure")
            connection.add_setting(s_wifi)

            if password:
                s_sec = NM.SettingWirelessSecurity.new()
                s_sec.set_property("key-mgmt", "wpa-psk")
                s_sec.set_property("psk", password)
                connection.add_setting(s_sec)

            s_ip4 = NM.SettingIP4Config.new()
            s_ip4.set_property("method", "auto")
            connection.add_setting(s_ip4)

            s_ip6 = NM.SettingIP6Config.new()
            s_ip6.set_property("method", "auto")
            connection.add_setting(s_ip6)

            self.client.add_and_activate_connection_async(
                connection,
                self.device,
                target_ap.get_path(),
                None,
                activation_callback
            )

    def disconnect(self, callback: Optional[Callable] = None):
        """Disconnect from current WiFi network"""
        active_connection = self.device.get_active_connection()
        if not active_connection:
            if callback:
                callback(True, "Already disconnected")
            return

        def deactivation_callback(client, result):
            try:
                client.deactivate_connection_finish(result)
                print("Successfully disconnected from WiFi")
                if callback:
                    callback(True, "Disconnected successfully")
            except Exception as e:
                print(f"Failed to disconnect: {e}")
                if callback:
                    callback(False, str(e))

        self.client.deactivate_connection_async(
            active_connection,
            None,
            deactivation_callback
        )


class EthernetManager(GObject.GObject):
    def __init__(self, client: NM.Client, device: NM.DeviceEthernet):
        super().__init__()
        self.client = client
        self.device = device
        self.signals = NetworkSignals()

    @property
    def speed(self) -> int:
        """Get ethernet connection speed"""
        return self.device.get_speed()

    @property
    def connection_state(self) -> str:
        """Get connection state as string"""
        # Simplified logic: if an active connection object exists, we're connected.
        if self.device.get_active_connection():
            return "connected"
        return "disconnected"

    @property
    def icon_name(self) -> str:
        """Get appropriate icon for ethernet state"""
        if self.connection_state == "activated":
            return "network-wired-symbolic"
        else:
            return "network-wired-disconnected-symbolic"

    @property
    def iface(self) -> str:
        """Get ethernet interface name"""
        return self.device.get_iface()

class NetworkManager(GObject.GObject):
    def __init__(self):
        super().__init__()
        self.client: Optional[NM.Client] = None
        self.wifi_manager: Optional[WiFiManager] = None
        self.ethernet_manager: Optional[EthernetManager] = None
        self.signals = NetworkSignals()
        
        # Initialize NetworkManager client asynchronously
        NM.Client.new_async(None, self._on_client_ready)
    
    def _on_client_ready(self, source, result):
        """Handle NetworkManager client initialization"""
        try:
            self.client = NM.Client.new_finish(result)
            self._setup_devices()
            
            # Connect to global NetworkManager signals
            self.client.connect('connection-added', self._on_connection_added)
            self.client.connect('connection-removed', self._on_connection_removed)
            self.client.connect('device-added', self._on_device_added)
            self.client.connect('device-removed', self._on_device_removed)
            
            print("NetworkManager client initialized successfully")
            self.signals.emit('device-ready')
        except Exception as e:
            print(f"Failed to initialize NetworkManager client: {e}")

    def _on_device_added(self, client, device):
        """Handle newly added network devices."""
        print(f"Device added: {device.get_iface()} ({device.get_device_type()})")
        # Check if a manager for this device type needs to be created.
        device_type = device.get_device_type()
        if device_type == NM.DeviceType.WIFI and not self.wifi_manager:
            self.wifi_manager = WiFiManager(self.client, device)
            print(f"WiFi device initialized: {device.get_iface()}")
            self.signals.emit('device-ready')
        elif device_type == NM.DeviceType.ETHERNET and not self.ethernet_manager:
            self.ethernet_manager = EthernetManager(self.client, device)
            print(f"Ethernet device initialized: {device.get_iface()}")
            self.signals.emit('device-ready')

    def _on_device_removed(self, client, device):
        """Handle removed network devices."""
        print(f"Device removed: {device.get_iface()}")
        iface = device.get_iface()
        
        if self.wifi_manager and self.wifi_manager.device.get_iface() == iface:
            self.wifi_manager = None
            print("WiFi manager removed.")
            self.signals.emit('device-ready')

        if self.ethernet_manager and self.ethernet_manager.device.get_iface() == iface:
            self.ethernet_manager = None
            print("Ethernet manager removed.")
            self.signals.emit('device-ready')

    def _on_connection_added(self, client, connection):
        """Handle new connection added"""
        conn_id = connection.get_id()
        print(f"Connection added: {conn_id}")
        self.signals.emit('connection-added', conn_id)

        # Emit specific signal based on connection type
        connection_type = connection.get_connection_type()
        if "wireless" in connection_type:
            if self.wifi_manager:
                self.wifi_manager.signals.emit('wifi-changed')
        elif "ethernet" in connection_type:
            if self.ethernet_manager:
                self.ethernet_manager.signals.emit('ethernet-changed', 'connected')

    def _on_connection_removed(self, client, connection):
        """Handle connection removed"""
        conn_id = connection.get_id()
        print(f"Connection removed: {conn_id}")
        self.signals.emit('connection-removed', conn_id)

        # Emit specific signal based on connection type
        connection_type = connection.get_connection_type()
        if "wireless" in connection_type:
            if self.wifi_manager:
                self.wifi_manager.signals.emit('wifi-changed')
        elif "ethernet" in connection_type:
            if self.ethernet_manager:
                self.ethernet_manager.signals.emit('ethernet-changed', 'disconnected')
    
    def _setup_devices(self):
        """Setup WiFi and Ethernet device managers"""
        if not self.client:
            return
        
        devices = self.client.get_devices()
        
        for device in devices:
            device_type = device.get_device_type()
            
            if device_type == NM.DeviceType.WIFI and not self.wifi_manager:
                self.wifi_manager = WiFiManager(self.client, device)
                print(f"WiFi device initialized: {device.get_iface()}")
            
            elif device_type == NM.DeviceType.ETHERNET and not self.ethernet_manager:
                self.ethernet_manager = EthernetManager(self.client, device)
                print(f"Ethernet device initialized: {device.get_iface()}")
    
    @property
    def primary_connection_type(self) -> Optional[str]:
        """Get the type of primary connection"""
        if not self.client:
            return None
        
        primary_connection = self.client.get_primary_connection()
        if not primary_connection:
            return None
        
        connection_type = primary_connection.get_connection_type()
        
        if "wireless" in connection_type:
            return "wifi"
        elif "ethernet" in connection_type:
            return "ethernet"
        
        return None
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get comprehensive connection information"""
        info = {
            "primary_type": self.primary_connection_type,
            "wifi": None,
            "ethernet": None,
        }
        
        if self.wifi_manager:
            info["wifi"] = {
                "enabled": self.wifi_manager.enabled,
                "ssid": self.wifi_manager.ssid,
                "strength": self.wifi_manager.strength,
                "frequency": self.wifi_manager.frequency,
                "state": self.wifi_manager.state,
                "connection_state": self.wifi_manager.connection_state,
                "icon_name": self.wifi_manager.icon_name,
            }
        
        if self.ethernet_manager:
            info["ethernet"] = {
                "iface": self.ethernet_manager.iface,
                "speed": self.ethernet_manager.speed,
                "connection_state": self.ethernet_manager.connection_state,
                "icon_name": self.ethernet_manager.icon_name,
            }
        
        return info


# Example usage and testing
if __name__ == "__main__":
    class NetworkTestApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="com.example.NetworkTest")
            self.network_manager = None

        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self)
            window.set_title("Network Manager Test")
            window.set_default_size(400, 300)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_margin_top(10)
            box.set_margin_bottom(10)
            box.set_margin_start(10)
            box.set_margin_end(10)

            self.status_label = Gtk.Label(label="Initializing NetworkManager...")
            box.append(self.status_label)

            wifi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            self.wifi_toggle = Gtk.Switch()
            self.wifi_toggle.connect('notify::active', self._on_wifi_toggle)
            wifi_box.append(Gtk.Label(label="WiFi:"))
            wifi_box.append(self.wifi_toggle)
            self.scan_button = Gtk.Button(label="Scan")
            self.scan_button.connect('clicked', self._on_scan_clicked)
            wifi_box.append(self.scan_button)
            box.append(wifi_box)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(200)
            self.ap_list = Gtk.ListBox()
            self.ap_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.ap_list.connect('row-activated', self._on_ap_selected)
            scrolled.set_child(self.ap_list)
            box.append(scrolled)

            self.connection_status = Gtk.Label(label="")
            self.connection_status.set_wrap(True)
            box.append(self.connection_status)

            window.set_child(box)
            window.present()

            self.network_manager = NetworkManager()
            self.network_manager.signals.connect('device-ready', self._on_device_ready)

        def _on_device_ready(self, signals):
            print("Device ready - setting up signal connections")
            if self.network_manager.wifi_manager:
                self.network_manager.wifi_manager.signals.connect('wifi-changed', self._update_wifi_info)
                self.network_manager.wifi_manager.signals.connect('wifi-enabled-changed', self._update_wifi_info)
            if self.network_manager.ethernet_manager:
                self.network_manager.ethernet_manager.signals.connect('ethernet-changed', self._update_wifi_info)
            self._update_wifi_info()

        def _update_wifi_info(self, *args):
            if not self.network_manager or not self.network_manager.wifi_manager:
                return

            wifi = self.network_manager.wifi_manager
            info = self.network_manager.get_connection_info()['wifi']

            if not info['enabled']:
                status_text = "WiFi: Disabled"
            elif info['connection_state'] == "activated":
                status_text = f"WiFi: {info['ssid']} ({info['strength']}% signal)"
            elif info['connection_state'] == "activating":
                status_text = "WiFi: Connecting..."
            else:
                status_text = f"WiFi: {info['state'].title()}"

            self.status_label.set_text(status_text)
            self.wifi_toggle.set_active(info['enabled'])

            self._clear_ap_list()
            access_points = wifi.get_access_points()
            access_points.sort(key=lambda ap: ap.strength, reverse=True)

            unique_ssids = {}
            for ap in access_points:
                if ap.ssid and ap.ssid not in unique_ssids:
                    unique_ssids[ap.ssid] = ap

            for ap in unique_ssids.values():
                row = Gtk.ListBoxRow()
                row.ap_data = ap
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row_box.set_margin_start(10); row_box.set_margin_end(10); row_box.set_margin_top(5); row_box.set_margin_bottom(5)

                icon_name = wifi._get_signal_icon(ap.strength)
                icon = Gtk.Image.new_from_icon_name(icon_name)
                row_box.append(icon)

                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                ssid_label = Gtk.Label()
                ssid_label.set_halign(Gtk.Align.START)
                if ap.is_active:
                    ssid_label.set_markup(f"<b>{GLib.markup_escape_text(ap.ssid)}</b>")
                else:
                    ssid_label.set_text(ap.ssid)
                info_box.append(ssid_label)

                row_box.append(info_box)
                row.set_child(row_box)
                self.ap_list.append(row)

        def _clear_ap_list(self):
            child = self.ap_list.get_first_child()
            while child:
                self.ap_list.remove(child)
                child = self.ap_list.get_first_child()
        
        def _on_wifi_toggle(self, switch, pspec):
            if self.network_manager and self.network_manager.wifi_manager:
                def toggle_callback(success, message):
                    if not success:
                        print(f"Failed to toggle WiFi: {message}")
                        GLib.idle_add(switch.set_active, not switch.get_active())
                
                self.network_manager.wifi_manager.set_enabled_async(
                    switch.get_active(), toggle_callback
                )
        
        def _on_scan_clicked(self, button):
            if self.network_manager and self.network_manager.wifi_manager:
                button.set_sensitive(False)
                button.set_label("Scanning...")
                def scan_callback(success, error):
                    button.set_sensitive(True)
                    button.set_label("Scan")
                    if not success:
                        self.connection_status.set_text(f"Scan failed: {error}")
                self.network_manager.wifi_manager.scan_async(scan_callback)

        def _on_ap_selected(self, listbox, row):
            if row and hasattr(row, 'ap_data'):
                ap_data = row.ap_data
                if ap_data.is_active:
                    self._disconnect_from_wifi()
                else:
                    # This is the same logic as the connect button
                    self._on_connect_clicked(None, ap_data)

        # --- START OF CHANGE 2 ---
        # This is the core of the fix. The logic now checks for a saved
        # connection first before deciding to show the password dialog.
        def _on_connect_clicked(self, button, ap_data):
            """Handle connect button click from anywhere."""
            wifi = self.network_manager.wifi_manager
            if not wifi:
                return

            # Check if a connection profile for this SSID already exists
            saved_connection = wifi.find_connection_by_ssid(ap_data.ssid)

            if saved_connection:
                # If it exists, connect directly without asking for a password.
                print(f"Connecting to saved network: {ap_data.ssid}")
                self._connect_to_wifi(ap_data, "") # Password can be empty, it won't be used
            else:
                # If it's a new network, show the password dialog.
                print(f"New network detected: {ap_data.ssid}. Showing password dialog.")
                self._show_connect_dialog(ap_data)
        # --- END OF CHANGE 2 ---

        def _disconnect_from_wifi(self):
            """Handle disconnect request."""
            if self.network_manager and self.network_manager.wifi_manager:
                self.connection_status.set_text("Disconnecting...")
                def disconnect_callback(success, message):
                    self.connection_status.set_text(message if success else f"Disconnect failed: {message}")
                self.network_manager.wifi_manager.disconnect(disconnect_callback)

        def _show_connect_dialog(self, ap_data):
            # Dialog creation is fine, just added a check for security
            dialog = Gtk.Window(title=f"Connect to {ap_data.ssid}", transient_for=self.get_active_window(), modal=True, resizable=False)
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=20, margin_bottom=20, margin_start=20, margin_end=20)
            
            # ... dialog UI is largely the same ...
            password_entry = Gtk.Entry(visibility=False, placeholder_text="Enter WiFi password")
            main_box.append(password_entry)

            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.END)
            cancel_btn = Gtk.Button(label="Cancel")
            cancel_btn.connect('clicked', lambda btn: dialog.close())
            button_box.append(cancel_btn)
            connect_btn = Gtk.Button(label="Connect", css_classes=["suggested-action"])
            button_box.append(connect_btn)
            main_box.append(button_box)

            def do_connect_action(widget):
                password = password_entry.get_text()
                dialog.close()
                self._connect_to_wifi(ap_data, password)

            password_entry.connect('activate', do_connect_action)
            connect_btn.connect('clicked', do_connect_action)
            
            dialog.set_child(main_box)
            dialog.present()

        def _connect_to_wifi(self, ap_data, password):
            """Connect to WiFi network with or without a password."""
            if not self.network_manager or not self.network_manager.wifi_manager:
                return

            self.connection_status.set_text(f"Connecting to {ap_data.ssid}...")
            def connect_callback(success, message):
                if success:
                    self.connection_status.set_text(f"Connection to {ap_data.ssid} initiated.")
                else:
                    self.connection_status.set_text(f"Connection failed: {message}")

            self.network_manager.wifi_manager.connect_to_ap(
                ap_data.ssid, password, connect_callback
            )
            
    app = NetworkTestApp()
    app.run(sys.argv)