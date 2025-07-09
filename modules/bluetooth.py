import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio
from service.bluetooth import BluetoothService, BluetoothDevice

class BluetoothStack(Gtk.Box):
    """Main Bluetooth management window."""
    
    def __init__(self, notch, **kwargs):
        super().__init__(
            name="bluetooth",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL
        )
        
        self.bt_service = BluetoothService()
        
        self._create_ui()
        
        self.bt_service.connect('device-added', self._on_device_added)
        self.bt_service.connect('device-removed', self._on_device_removed)
        self.bt_service.connect('property-changed', self._on_service_property_changed)
        
        self._populate_devices()
        self._update_adapter_status()
    
    def _create_ui(self):
        """Create the user interface."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.append(main_box)
        
        
        
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
        
        adapter_box, self.adapter_list_box = self._create_titled_list("Adapter")
        content_box.append(adapter_box)
        
        self.power_row = self._create_switch_row("Bluetooth", "Enable Bluetooth adapter")
        self.power_row.switch.connect("notify::active", self._on_power_toggled)
        power_list_row = Gtk.ListBoxRow()
        power_list_row.set_child(self.power_row.box)
        self.adapter_list_box.append(power_list_row)
        
        self.scan_row = self._create_switch_row("Discoverable", "Make this device discoverable and scan for devices")
        self.scan_row.switch.connect("notify::active", self._on_scan_toggled)
        scan_list_row = Gtk.ListBoxRow()
        scan_list_row.set_child(self.scan_row.box)
        self.adapter_list_box.append(scan_list_row)
        
        
        
        devices_box, self.devices_list_box = self._create_titled_list("Devices")
        content_box.append(devices_box)
        
        self.no_devices_row = self._create_info_row("No devices found", "Turn on discoverable mode to scan for devices")
        self.no_devices_list_row = Gtk.ListBoxRow()
        self.no_devices_list_row.set_child(self.no_devices_row.box)
        
        self.device_rows = {}
        
        self.toast_label = Gtk.Label()
        self.toast_label.set_visible(False)
        self.toast_label.add_css_class("toast")
        main_box.append(self.toast_label)

    def _list_box_separator_header_func(self, row, before):
        if before:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def _create_titled_list(self, title):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{title}</b>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_bottom(6)
        box.append(title_label)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        list_box.set_header_func(self._list_box_separator_header_func)
        
        box.append(list_box)
        return box, list_box
    
    def _create_switch_row(self, title, subtitle=""):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_start(12)
        row_box.set_margin_end(12)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)
        
        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        text_box.append(title_label)
        
        if subtitle:
            subtitle_label = Gtk.Label(label=subtitle)
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.add_css_class("dim-label")
            text_box.append(subtitle_label)
        
        row_box.append(text_box)
        
        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        row_box.append(switch)
        
        class SwitchRow:
            def __init__(self, box, switch):
                self.box = box
                self.switch = switch
            def set_active(self, active):
                self.switch.set_active(active)
            def set_sensitive(self, sensitive):
                self.switch.set_sensitive(sensitive)
        
        return SwitchRow(row_box, switch)
    
    def _create_info_row(self, title, subtitle=""):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_start(12)
        row_box.set_margin_end(12)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)
        
        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        text_box.append(title_label)
        
        subtitle_label = None
        if subtitle:
            subtitle_label = Gtk.Label(label=subtitle)
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.add_css_class("dim-label")
            text_box.append(subtitle_label)
        
        row_box.append(text_box)
        
        class InfoRow:
            def __init__(self, box, title_label, subtitle_label):
                self.box = box
                self.title_label = title_label
                self.subtitle_label = subtitle_label
            def set_title(self, title):
                self.title_label.set_text(title)
            def set_subtitle(self, subtitle):
                if self.subtitle_label:
                    self.subtitle_label.set_text(subtitle)
        
        return InfoRow(row_box, title_label, subtitle_label)
    
    def _update_adapter_status(self):
        self.power_row.set_active(self.bt_service.powered)
        self.scan_row.set_active(self.bt_service.setup_mode)
        self.scan_row.set_sensitive(self.bt_service.powered)
        
        
    
    def _populate_devices(self):
        for row in self.device_rows.values():
            self.devices_list_box.remove(row)
        self.device_rows.clear()
        
        devices = [device for device in self.bt_service.devices if device.device_type.lower() != "unknown"]
        if devices:
            if self.no_devices_list_row.get_parent():
                self.devices_list_box.remove(self.no_devices_list_row)
            for device in devices:
                self._add_device_row(device)
        else:
            if self.no_devices_list_row.get_parent() is None:
                self.devices_list_box.append(self.no_devices_list_row)
    
    def _add_device_row(self, device: BluetoothDevice):
        if self.no_devices_list_row.get_parent():
            self.devices_list_box.remove(self.no_devices_list_row)
        
        row = DeviceRow(device, self.bt_service)
        self.devices_list_box.append(row)
        self.device_rows[device.address] = row
    
    def _remove_device_row(self, device_address: str):
        if device_address in self.device_rows:
            row = self.device_rows.pop(device_address)
            self.devices_list_box.remove(row)
            
            if not self.device_rows and self.no_devices_list_row.get_parent() is None:
                self.devices_list_box.append(self.no_devices_list_row)
    
    def _on_device_added(self, service, device):
        GLib.idle_add(self._add_device_row, device)
    
    def _on_device_removed(self, service, object_path):
        for address, row in list(self.device_rows.items()):
            if row.device.gdevice.get_object_path() == object_path:
                GLib.idle_add(self._remove_device_row, address)
                break
    
    def _on_service_property_changed(self, service, prop_name):
        GLib.idle_add(self._update_adapter_status)
    
    def _on_power_toggled(self, switch, param):
        if switch.get_active() != self.bt_service.powered:
            self.bt_service.powered = switch.get_active()
    
    def _on_scan_toggled(self, switch, param):
        if switch.get_active() != self.bt_service.setup_mode:
            self.bt_service.setup_mode = switch.get_active()
    
    def add_toast(self, message):
        self.toast_label.set_text(message)
        self.toast_label.set_visible(True)
        GLib.timeout_add_seconds(2, lambda: self.toast_label.set_visible(False))

class DeviceRow(Gtk.ListBoxRow):
    """A row representing a Bluetooth device."""
    
    def __init__(self, device: BluetoothDevice, bt_service: BluetoothService):
        super().__init__()
        
        self.device = device
        self.bt_service = bt_service
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(6)
        main_box.set_margin_bottom(6)
        self.set_child(main_box)
        
        self.icon = Gtk.Image.new_from_icon_name(self._get_device_icon())
        self.icon.set_pixel_size(32)
        main_box.append(self.icon)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)
        
        self.name_label = Gtk.Label(label=device.name or "Unknown Device")
        self.name_label.set_halign(Gtk.Align.START)
        info_box.append(self.name_label)
        
        self.status_label = Gtk.Label(label=self._get_status_text())
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("dim-label")
        info_box.append(self.status_label)
        
        main_box.append(info_box)
        
        self.connect_button = Gtk.Button()
        self._update_connect_button()
        self.connect_button.connect("clicked", self._on_connect_clicked)
        main_box.append(self.connect_button)

        self.device.connect("property-changed", self._on_device_property_changed)

    def _on_device_property_changed(self, device, prop_name):
        GLib.idle_add(self._update_ui)

    def _update_ui(self):
        self.icon.set_from_icon_name(self._get_device_icon())
        self.name_label.set_label(self.device.name or "Unknown Device")
        self.status_label.set_label(self._get_status_text())
        self._update_connect_button()

    def _get_device_icon(self):
        device_type = self.device.device_type.lower()
        icon_map = {
            "phone": "phone-symbolic",
            "computer": "computer-symbolic",
            "headset": "audio-headphones-symbolic",
            "headphones": "audio-headphones-symbolic",
            "speaker": "audio-speakers-symbolic",
            "keyboard": "input-keyboard-symbolic",
            "mouse": "input-mouse-symbolic",
        }
        return icon_map.get(device_type, "bluetooth-symbolic")
    
    def _get_status_text(self):
        if self.device.connected:
            return "Connected"
        elif self.device.paired:
            return "Paired"
        else:
            return "Available"
    
    def _update_connect_button(self):
        if self.device.connected:
            self.connect_button.set_label("Disconnect")
        elif self.device.paired:
            self.connect_button.set_label("Connect")
        else:
            self.connect_button.set_label("Pair")
    
    def _on_connect_clicked(self, button):
        if self.device.connected:
            self.device.disconnect_from()
        elif self.device.paired:
            self.device.connect_to()
        else:
            self.device.pair_device()