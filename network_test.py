#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GObject', '2.0')
from gi.repository import Gtk, GObject, Gio, GLib, Pango
import sys
import os

# Import the network service
try:
    from test import NetworkClient
except ImportError:
    print("Error: Could not import network service from services.network")
    print("Make sure the services/network.py file exists and is accessible")
    sys.exit(1)


class WiFiAccessPointRow(Gtk.ListBoxRow):
    """Custom row widget for WiFi access points"""
    
    def __init__(self, ap_data, network_client):
        super().__init__()
        self.ap_data = ap_data
        self.network_client = network_client
        
        # Create main container
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name(ap_data['icon_name'])
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        box.append(icon)
        
        # SSID and info container
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        # SSID label
        ssid_label = Gtk.Label(label=ap_data['ssid'])
        ssid_label.set_halign(Gtk.Align.START)
        ssid_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        if ap_data['active_ap']:
            ssid_label.add_css_class('accent')
            ssid_label.set_markup(f"<b>{ap_data['ssid']}</b>")
        
        info_box.append(ssid_label)
        
        # Signal strength and frequency
        details = f"{ap_data['strength']}% • {ap_data['frequency']} MHz"
        if ap_data['active_ap']:
            details += " • Connected"
        
        details_label = Gtk.Label(label=details)
        details_label.set_halign(Gtk.Align.START)
        details_label.add_css_class('dim-label')
        details_label.add_css_class('caption')
        info_box.append(details_label)
        
        box.append(info_box)
        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        box.append(spacer)
        
        # Connect button (only for non-active APs)
        if not ap_data['active_ap']:
            connect_btn = Gtk.Button(label="Connect")
            connect_btn.add_css_class('suggested-action')
            connect_btn.connect('clicked', self._on_connect_clicked)
            box.append(connect_btn)
        
        self.set_child(box)
    
    def _on_connect_clicked(self, button):
        """Handle connect button click"""
        button.set_sensitive(False)
        button.set_label("Connecting...")
        
        # Connect using BSSID
        self.network_client.connect_wifi_bssid(self.ap_data['bssid'])
        
        # The button will be re-enabled when the connection state changes
    
    def update_button_state(self):
        """Update button state based on connection status"""
        # Find the button in our widget tree
        box = self.get_child()
        if box:
            # Get the last child (should be the button if it exists)
            button = None
            child = box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                if isinstance(child, Gtk.Button):
                    button = child
                child = next_child
            
            if button:
                if self.ap_data['active_ap']:
                    # This AP is now active, remove the button
                    box.remove(button)
                else:
                    # Reset button to normal state
                    button.set_sensitive(True)
                    button.set_label("Connect")


class NetworkManagerWindow(Gtk.ApplicationWindow):
    """Main network manager window"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.network_client = None
        self.wifi_list_box = None
        self.ethernet_status_box = None
        self.wifi_status_box = None
        
        self.set_title("Network Manager")
        self.set_default_size(600, 500)
        
        # Create UI
        self._setup_ui()
        
        # Initialize network client
        self._init_network_client()
    
    def _setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)
        
        # Header bar
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Network Manager"))
        
        # Refresh button in header
        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh networks")
        refresh_btn.connect('clicked', self._on_refresh_clicked)
        header.pack_end(refresh_btn)
        
        self.set_titlebar(header)
        
        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)
        
        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.set_margin_top(18)
        content_box.set_margin_bottom(18)
        content_box.set_margin_start(18)
        content_box.set_margin_end(18)
        scrolled.set_child(content_box)
        
        # WiFi Section
        self._create_wifi_section(content_box)
        
        # Ethernet Section
        self._create_ethernet_section(content_box)
        
        # Status bar
        self.status_label = Gtk.Label(label="Initializing network client...")
        self.status_label.add_css_class('dim-label')
        self.status_label.set_margin_top(12)
        main_box.append(self.status_label)
    
    def _create_wifi_section(self, parent):
        """Create WiFi section"""
        # WiFi header
        wifi_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        wifi_title = Gtk.Label(label="WiFi")
        wifi_title.add_css_class('title-2')
        wifi_title.set_halign(Gtk.Align.START)
        wifi_header_box.append(wifi_title)
        
        # WiFi toggle switch
        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.set_halign(Gtk.Align.END)
        self.wifi_switch.set_hexpand(True)
        self.wifi_switch.connect('notify::active', self._on_wifi_toggle)
        wifi_header_box.append(self.wifi_switch)
        
        parent.append(wifi_header_box)
        
        # WiFi status
        self.wifi_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wifi_status_icon = Gtk.Image()
        self.wifi_status_label = Gtk.Label()
        self.wifi_status_label.set_halign(Gtk.Align.START)
        
        self.wifi_status_box.append(self.wifi_status_icon)
        self.wifi_status_box.append(self.wifi_status_label)
        parent.append(self.wifi_status_box)
        
        # WiFi access points list
        frame = Gtk.Frame()
        frame.set_margin_top(12)
        
        self.wifi_list_box = Gtk.ListBox()
        self.wifi_list_box.add_css_class('boxed-list')
        self.wifi_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        
        frame.set_child(self.wifi_list_box)
        parent.append(frame)
        
        # Initially show loading message
        self._show_wifi_loading()
    
    def _create_ethernet_section(self, parent):
        """Create Ethernet section"""
        # Ethernet header
        eth_title = Gtk.Label(label="Ethernet")
        eth_title.add_css_class('title-2')
        eth_title.set_halign(Gtk.Align.START)
        eth_title.set_margin_top(6)
        parent.append(eth_title)
        
        # Ethernet status
        frame = Gtk.Frame()
        frame.set_margin_top(12)
        
        self.ethernet_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.ethernet_status_box.set_margin_top(12)
        self.ethernet_status_box.set_margin_bottom(12)
        self.ethernet_status_box.set_margin_start(12)
        self.ethernet_status_box.set_margin_end(12)
        
        self.ethernet_icon = Gtk.Image()
        self.ethernet_icon.set_icon_size(Gtk.IconSize.NORMAL)
        
        self.ethernet_label = Gtk.Label()
        self.ethernet_label.set_halign(Gtk.Align.START)
        
        self.ethernet_status_box.append(self.ethernet_icon)
        self.ethernet_status_box.append(self.ethernet_label)
        
        frame.set_child(self.ethernet_status_box)
        parent.append(frame)
        
        # Initially show disconnected
        self._update_ethernet_status()
    
    def _show_wifi_loading(self):
        """Show loading state for WiFi"""
        # Clear existing items
        while True:
            child = self.wifi_list_box.get_first_child()
            if child is None:
                break
            self.wifi_list_box.remove(child)
        
        # Add loading row
        loading_row = Gtk.ListBoxRow()
        loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        loading_box.set_margin_top(12)
        loading_box.set_margin_bottom(12)
        loading_box.set_margin_start(12)
        loading_box.set_margin_end(12)
        
        spinner = Gtk.Spinner()
        spinner.start()
        loading_box.append(spinner)
        
        loading_label = Gtk.Label(label="Scanning for networks...")
        loading_box.append(loading_label)
        
        loading_row.set_child(loading_box)
        self.wifi_list_box.append(loading_row)
    
    def _init_network_client(self):
        """Initialize the network client"""
        self.network_client = NetworkClient()
        self.network_client.connect("device-ready", self._on_device_ready)
    
    def _on_device_ready(self, network_client):
        """Handle network device ready signal"""
        print("Network devices ready!")
        
        # Setup WiFi if available
        if network_client.wifi_device:
            wifi_device = network_client.wifi_device
            
            # Debug: Print WiFi state info
            nm_wifi_enabled = network_client._client.wireless_get_enabled()
            device_state = wifi_device._device.get_state()
            wifi_enabled = wifi_device.get_property('enabled')
            
            print(f"NetworkManager WiFi enabled: {nm_wifi_enabled}")
            print(f"WiFi device state: {device_state}")
            print(f"WiFi service enabled property: {wifi_enabled}")
            
            # Connect to WiFi signals
            wifi_device.connect("changed", self._on_wifi_changed)
            wifi_device.connect("enabled", self._on_wifi_enabled_changed)
            
            # Also connect directly to NetworkManager client signals
            network_client._client.connect("notify::wireless-enabled", self._on_nm_wifi_changed)
            
            # Update WiFi UI
            self._update_wifi_status()
            self._update_wifi_list()
            
            # Set initial switch state based on NetworkManager state
            self.wifi_switch.set_active(nm_wifi_enabled)
        else:
            self._show_no_wifi_device()
        
        # Setup Ethernet if available
        if network_client.ethernet_device:
            ethernet_device = network_client.ethernet_device
            ethernet_device.connect("changed", self._on_ethernet_changed)
            self._update_ethernet_status()
        
        self.status_label.set_text("Ready")
    
    def _on_nm_wifi_changed(self, client, pspec):
        """Handle NetworkManager WiFi enabled state change"""
        print(f"NetworkManager WiFi state changed: {client.wireless_get_enabled()}")
        self.wifi_switch.set_active(client.wireless_get_enabled())
        self._update_wifi_status()
        self._update_wifi_list()
    
    def _on_wifi_changed(self, wifi_device):
        """Handle WiFi device changes"""
        print("WiFi device changed")
        self._update_wifi_status()
        self._update_wifi_list()
    
    def _on_wifi_enabled_changed(self, wifi_device, enabled):
        """Handle WiFi enabled state change"""
        print(f"WiFi enabled changed: {enabled}")
        # Don't set switch state here to avoid loops
        self._update_wifi_status()
        if enabled:
            self._update_wifi_list()
    
    def _on_ethernet_changed(self, ethernet_device):
        """Handle Ethernet device changes"""
        self._update_ethernet_status()
    
    def _on_wifi_toggle(self, switch, gparam):
        """Handle WiFi toggle switch"""
        is_active = switch.get_active()
        print(f"WiFi switch toggled to: {is_active}")
        
        if self.network_client and self.network_client._client:
            current_state = self.network_client._client.wireless_get_enabled()
            print(f"Current NetworkManager WiFi state: {current_state}")
            
            if is_active != current_state:
                print(f"Setting NetworkManager WiFi to: {is_active}")
                self.network_client._client.wireless_set_enabled(is_active)
                
                # Update status immediately
                self.status_label.set_text("Updating WiFi state..." if is_active else "Disabling WiFi...")
                
                # Schedule a delayed update
                self._schedule_wifi_update()
    
    def _delayed_wifi_update(self):
        """Delayed WiFi update after state change"""
        self._update_wifi_status()
        self._update_wifi_list()
        self.status_label.set_text("Ready")
        return False  # Don't repeat
    
    def _on_refresh_clicked(self, button):
        """Handle refresh button click"""
        if self.network_client and self.network_client.wifi_device:
            self.network_client.wifi_device.scan()
            self._show_wifi_loading()
            self.status_label.set_text("Scanning for networks...")
    
    def _update_wifi_status(self):
        """Update WiFi status display"""
        if not self.network_client or not self.network_client._client:
            return
        
        # Use NetworkManager client directly for enabled state
        nm_wifi_enabled = self.network_client._client.wireless_get_enabled()
        print(f"Updating WiFi status - NM enabled: {nm_wifi_enabled}")
        
        if not self.network_client.wifi_device:
            self.wifi_status_icon.set_from_icon_name("network-wireless-disabled-symbolic")
            self.wifi_status_label.set_text("No WiFi device available")
            return
        
        wifi_device = self.network_client.wifi_device
        
        # Update icon
        if not nm_wifi_enabled:
            icon_name = "network-wireless-disabled-symbolic"
        else:
            icon_name = wifi_device.get_property('icon-name')
        
        self.wifi_status_icon.set_from_icon_name(icon_name)
        
        # Update status text
        if not nm_wifi_enabled:
            status_text = "WiFi is disabled"
        else:
            ssid = wifi_device.get_property('ssid')
            state = wifi_device.get_property('state')
            internet = wifi_device.get_property('internet')
            
            print(f"WiFi state: {state}, internet: {internet}, ssid: {ssid}")
            
            if state == "activated" and internet == "activated":
                strength = wifi_device.get_property('strength')
                status_text = f"Connected to {ssid} ({strength}%)"
            elif state == "activating":
                status_text = f"Connecting to {ssid}..."
            else:
                status_text = "Not connected"
        
        self.wifi_status_label.set_text(status_text)
    
    def _update_wifi_list(self):
        """Update WiFi access points list"""
        if not self.network_client or not self.network_client._client:
            return
        
        # Use NetworkManager client directly for enabled state
        nm_wifi_enabled = self.network_client._client.wireless_get_enabled()
        
        if not nm_wifi_enabled or not self.network_client.wifi_device:
            self._show_wifi_disabled()
            return
        
        # Clear existing items
        while True:
            child = self.wifi_list_box.get_first_child()
            if child is None:
                break
            self.wifi_list_box.remove(child)
        
        # Get access points
        try:
            access_points = self.network_client.wifi_device.get_access_points()
            print(f"Found {len(access_points)} access points")
        except Exception as e:
            print(f"Error getting access points: {e}")
            self._show_no_networks()
            return
        
        if not access_points:
            self._show_no_networks()
            return
        
        # Sort by signal strength (strongest first)
        access_points.sort(key=lambda x: x['strength'], reverse=True)
        
        # Add access point rows
        for ap in access_points:
            if ap['ssid'] and ap['ssid'] != "Unknown":  # Skip hidden/unknown networks
                row = WiFiAccessPointRow(ap, self.network_client)
                self.wifi_list_box.append(row)
    
    def _show_wifi_disabled(self):
        """Show WiFi disabled message"""
        # Clear existing items
        while True:
            child = self.wifi_list_box.get_first_child()
            if child is None:
                break
            self.wifi_list_box.remove(child)
        
        # Add disabled message
        disabled_row = Gtk.ListBoxRow()
        disabled_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        disabled_box.set_margin_top(12)
        disabled_box.set_margin_bottom(12)
        disabled_box.set_margin_start(12)
        disabled_box.set_margin_end(12)
        
        disabled_icon = Gtk.Image.new_from_icon_name("network-wireless-disabled-symbolic")
        disabled_box.append(disabled_icon)
        
        disabled_label = Gtk.Label(label="WiFi is disabled")
        disabled_label.add_css_class('dim-label')
        disabled_box.append(disabled_label)
        
        disabled_row.set_child(disabled_box)
        self.wifi_list_box.append(disabled_row)
    
    def _show_no_networks(self):
        """Show no networks found message"""
        no_networks_row = Gtk.ListBoxRow()
        no_networks_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        no_networks_box.set_margin_top(12)
        no_networks_box.set_margin_bottom(12)
        no_networks_box.set_margin_start(12)
        no_networks_box.set_margin_end(12)
        
        no_networks_icon = Gtk.Image.new_from_icon_name("network-wireless-no-route-symbolic")
        no_networks_box.append(no_networks_icon)
        
        no_networks_label = Gtk.Label(label="No networks found")
        no_networks_label.add_css_class('dim-label')
        no_networks_box.append(no_networks_label)
        
        no_networks_row.set_child(no_networks_box)
        self.wifi_list_box.append(no_networks_row)
    
    def _show_no_wifi_device(self):
        """Show no WiFi device message"""
        self.wifi_switch.set_sensitive(False)
        
        # Clear existing items
        while True:
            child = self.wifi_list_box.get_first_child()
            if child is None:
                break
            self.wifi_list_box.remove(child)
        
        no_device_row = Gtk.ListBoxRow()
        no_device_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        no_device_box.set_margin_top(12)
        no_device_box.set_margin_bottom(12)
        no_device_box.set_margin_start(12)
        no_device_box.set_margin_end(12)
        
        no_device_icon = Gtk.Image.new_from_icon_name("network-wireless-disabled-symbolic")
        no_device_box.append(no_device_icon)
        
        no_device_label = Gtk.Label(label="No WiFi device found")
        no_device_label.add_css_class('dim-label')
        no_device_box.append(no_device_label)
        
        no_device_row.set_child(no_device_box)
        self.wifi_list_box.append(no_device_row)
        
        self.wifi_status_label.set_text("No WiFi device available")
    
    def _update_ethernet_status(self):
        """Update Ethernet status display"""
        if not self.network_client or not self.network_client.ethernet_device:
            self.ethernet_icon.set_from_icon_name("network-wired-disconnected-symbolic")
            self.ethernet_label.set_text("No Ethernet device found")
            return
        
        ethernet_device = self.network_client.ethernet_device
        
        # Update icon
        icon_name = ethernet_device.get_property('icon-name')
        self.ethernet_icon.set_from_icon_name(icon_name)
        
        # Update status text
        state = ethernet_device.get_property('state')
        internet = ethernet_device.get_property('internet')
        speed = ethernet_device.get_property('speed')
        
        if state == "activated" and internet == "activated":
            if speed > 0:
                status_text = f"Connected ({speed} Mbps)"
            else:
                status_text = "Connected"
        elif state == "activating":
            status_text = "Connecting..."
        elif state == "unavailable":
            status_text = "Cable unplugged"
        else:
            status_text = "Disconnected"
        
        self.ethernet_label.set_text(status_text)


class NetworkManagerApp(Gtk.Application):
    """Network Manager application"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.example.networkmanager",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            **kwargs
        )
        self.window = None
    
    def do_activate(self):
        if not self.window:
            self.window = NetworkManagerWindow(application=self)
        self.window.present()


def main():
    """Main entry point"""
    app = NetworkManagerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()