import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio
from service.network import NetworkManager, AccessPoint

class NetworkStack(Gtk.Box):
    """Main Network management widget."""

    def __init__(self, notch, **kwargs):
        super().__init__(
            name="network",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL
        )
        self._create_ui()
        self.network_manager = NetworkManager()
        self.ethernet_signal_connected = False
        # Connect to the central signal that indicates a change in device availability
        self.network_manager.signals.connect('device-ready', self._on_device_ready)

    def _on_device_ready(self, _):
        """
        Called when network devices are ready or when a device is added/removed.
        This method re-evaluates the available managers and updates the UI accordingly.
        """
        # If the ethernet manager no longer exists, reset the signal flag
        if not self.network_manager.ethernet_manager:
            self.ethernet_signal_connected = False

        # Setup WiFi signals if the manager is available
        if self.network_manager.wifi_manager:
            # Note: In a more complex app, you'd manage signal handler IDs
            # to prevent connecting multiple times. For now, we rely on GObject's behavior.
            self.network_manager.wifi_manager.signals.connect('wifi-changed', self._update_wifi_ui)
            self.network_manager.wifi_manager.signals.connect('wifi-enabled-changed', self._update_wifi_ui)
            self.wifi_switch.set_sensitive(True)
        else:
            self.wifi_switch.set_sensitive(False)

        # Setup Ethernet signals if the manager is available and not already connected
        if self.network_manager.ethernet_manager and not self.ethernet_signal_connected:
            self.network_manager.ethernet_manager.signals.connect('ethernet-changed', self._update_ethernet_ui)
            self.ethernet_signal_connected = True

        # Perform a full UI update
        GLib.idle_add(self._update_ethernet_ui)
        GLib.idle_add(self._update_wifi_ui)


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

        # Ethernet Section
        self.ethernet_box, self.ethernet_list_box = self._create_titled_list("Wired")
        self.ethernet_status_row = self._create_info_row("Ethernet", "Disconnected")
        ethernet_list_row = Gtk.ListBoxRow()
        ethernet_list_row.set_child(self.ethernet_status_row.box)
        self.ethernet_list_box.append(ethernet_list_row)
        content_box.append(self.ethernet_box)
        self.ethernet_box.set_visible(False) # Hide if no ethernet manager

        # WiFi Section
        wifi_titled_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wifi_titled_box.add_css_class("network-section")
        wifi_title_label = Gtk.Label()
        wifi_title_label.set_markup(f"<b>Wireless</b>")
        wifi_title_label.set_halign(Gtk.Align.START)
        wifi_title_label.set_margin_bottom(6)
        wifi_titled_box.append(wifi_title_label)
        
        wifi_box = Gtk.ListBox()
        wifi_box.set_selection_mode(Gtk.SelectionMode.NONE)
        wifi_box.add_css_class("boxed-list")
        wifi_box.set_header_func(self._list_box_separator_header_func)
        wifi_titled_box.append(wifi_box)
        content_box.append(wifi_titled_box)


        # WiFi toggle switch
        self.wifi_switch_row = self._create_switch_row("Wi-Fi", "Enable wireless adapter")
        self.wifi_switch = self.wifi_switch_row.switch
        self.wifi_switch.connect("notify::active", self._on_wifi_toggled)
        self.wifi_switch.set_sensitive(False) # Disabled until device is ready
        wifi_list_row = Gtk.ListBoxRow()
        wifi_list_row.set_child(self.wifi_switch_row.box)
        wifi_box.append(wifi_list_row)

        # WiFi AP List
        self.ap_list_box = Gtk.ListBox()
        self.ap_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.ap_list_box.add_css_class("boxed-list")
        self.ap_list_box.set_header_func(self._list_box_separator_header_func)
        content_box.append(self.ap_list_box)

        self.no_aps_row = self._create_info_row("No networks found", "Scanning for wireless networks...")
        self.no_aps_list_row = Gtk.ListBoxRow()
        self.no_aps_list_row.set_child(self.no_aps_row.box)

        self.ap_rows = {}

        self.toast_label = Gtk.Label()
        self.toast_label.set_visible(False)
        self.toast_label.add_css_class("toast")
        main_box.append(self.toast_label)

    def add_toast(self, message):
        self.toast_label.set_text(message)
        self.toast_label.set_visible(True)
        GLib.timeout_add_seconds(3, lambda: self.toast_label.set_visible(False))

    def _list_box_separator_header_func(self, row, before):
        if before:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def _create_titled_list(self, title):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("network-section")
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
        row_box.set_margin_start(12); row_box.set_margin_end(12); row_box.set_margin_top(6); row_box.set_margin_bottom(6)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); text_box.set_hexpand(True); text_box.set_valign(Gtk.Align.CENTER)
        title_label = Gtk.Label(label=title); title_label.set_halign(Gtk.Align.START); text_box.append(title_label)
        if subtitle:
            subtitle_label = Gtk.Label(label=subtitle); subtitle_label.set_halign(Gtk.Align.START); subtitle_label.add_css_class("dim-label"); text_box.append(subtitle_label)
        row_box.append(text_box)
        switch = Gtk.Switch(); switch.set_valign(Gtk.Align.CENTER); row_box.append(switch)
        class SwitchRow:
            def __init__(self, box, switch): self.box = box; self.switch = switch
            def set_active(self, active): self.switch.set_active(active)
            def set_sensitive(self, sensitive): self.switch.set_sensitive(sensitive)
        return SwitchRow(row_box, switch)

    def _create_info_row(self, title, subtitle=""):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_start(12); row_box.set_margin_end(12); row_box.set_margin_top(6); row_box.set_margin_bottom(6)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); text_box.set_hexpand(True); text_box.set_valign(Gtk.Align.CENTER)
        title_label = Gtk.Label(label=title); title_label.set_halign(Gtk.Align.START); text_box.append(title_label)
        subtitle_label = None
        if subtitle:
            subtitle_label = Gtk.Label(label=subtitle); subtitle_label.set_halign(Gtk.Align.START); subtitle_label.add_css_class("dim-label"); text_box.append(subtitle_label)
        row_box.append(text_box)
        class InfoRow:
            def __init__(self, box, title_label, subtitle_label): self.box = box; self.title_label = title_label; self.subtitle_label = subtitle_label
            def set_title(self, title): self.title_label.set_text(title)
            def set_subtitle(self, subtitle):
                if self.subtitle_label: self.subtitle_label.set_text(subtitle)
        return InfoRow(row_box, title_label, subtitle_label)

    def _update_ethernet_ui(self, *args):
        """Update the Ethernet UI based on the provided state."""
        if not self.network_manager.ethernet_manager:
            self.ethernet_box.set_visible(False)
            return

        state = None
        # The signal passes the state as a string argument. We look for it
        # in the arguments passed to handle the signal call correctly.
        for arg in args:
            if isinstance(arg, str) and arg in ['connected', 'disconnected']:
                state = arg
                break
        
        # If no state was found in args (e.g., initial call from idle_add),
        # get the current state directly from the manager.
        if state is None:
            state = self.network_manager.ethernet_manager.connection_state

        self.ethernet_box.set_visible(True)
        iface = self.network_manager.ethernet_manager.iface

        if state == 'connected':
            self.ethernet_status_row.set_title("Connected")
            self.ethernet_status_row.set_subtitle(iface)
        else: # 'disconnected'
            self.ethernet_status_row.set_title("Disconnected")
            self.ethernet_status_row.set_subtitle("Cable is unplugged")

    def _update_wifi_ui(self, *args):
        """Update the WiFi UI based on the current state."""
        if not self.network_manager.wifi_manager:
            # Clean up UI if no wifi manager is present
            for row in list(self.ap_rows.values()):
                self.ap_list_box.remove(row)
            self.ap_rows.clear()
            if self.no_aps_list_row.get_parent():
                self.ap_list_box.remove(self.no_aps_list_row)
            self.no_aps_row.set_title("Wi-Fi is disabled")
            self.no_aps_row.set_subtitle("Turn on Wi-Fi to see available networks")
            if not self.no_aps_list_row.get_parent():
                self.ap_list_box.append(self.no_aps_list_row)
            return

        wifi = self.network_manager.wifi_manager
        wifi_info = self.network_manager.get_connection_info()['wifi']

        # Update toggle
        if self.wifi_switch.get_active() != wifi_info['enabled']:
            self.wifi_switch.set_active(wifi_info['enabled'])

        # Update AP list
        for row in list(self.ap_rows.values()):
            self.ap_list_box.remove(row)
        self.ap_rows.clear()

        if not wifi_info['enabled']:
            if self.no_aps_list_row.get_parent():
                self.ap_list_box.remove(self.no_aps_list_row)
            self.no_aps_row.set_title("Wi-Fi is disabled")
            self.no_aps_row.set_subtitle("Turn on Wi-Fi to see available networks")
            if not self.no_aps_list_row.get_parent():
                self.ap_list_box.append(self.no_aps_list_row)
            return

        access_points = wifi.get_access_points()
        unique_aps = {ap.ssid: ap for ap in sorted(access_points, key=lambda x: x.strength, reverse=True) if ap.ssid}
        
        if unique_aps:
            if self.no_aps_list_row.get_parent():
                self.ap_list_box.remove(self.no_aps_list_row)
            for ssid, ap in unique_aps.items():
                self._add_ap_row(ap)
        else:
            if not self.no_aps_list_row.get_parent():
                self.ap_list_box.append(self.no_aps_list_row)
            self.no_aps_row.set_title("No networks found")
            self.no_aps_row.set_subtitle("Scanning for wireless networks...")

    def _add_ap_row(self, ap: AccessPoint):
        if ap.ssid in self.ap_rows:
            self.ap_rows[ap.ssid]._update_ui(ap)
            return
        
        row = AccessPointRow(ap, self.network_manager.wifi_manager)
        self.ap_list_box.append(row)
        self.ap_rows[ap.ssid] = row

    def _on_wifi_toggled(self, switch, param):
        if self.network_manager and self.network_manager.wifi_manager:
            if switch.get_active() != self.network_manager.wifi_manager.enabled:
                self.network_manager.wifi_manager.enabled = switch.get_active()

class AccessPointRow(Gtk.ListBoxRow):
    """A row representing a WiFi Access Point."""

    def __init__(self, ap: AccessPoint, wifi_manager):
        super().__init__()
        self.ap = ap
        self.wifi_manager = wifi_manager
        self._create_ui()
        self._update_ui(ap)

    def _create_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12); main_box.set_margin_end(12); main_box.set_margin_top(6); main_box.set_margin_bottom(6)
        self.set_child(main_box)

        self.icon = Gtk.Image()
        self.icon.set_pixel_size(24)
        main_box.append(self.icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)

        self.ssid_label = Gtk.Label()
        self.ssid_label.set_halign(Gtk.Align.START)
        info_box.append(self.ssid_label)

        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("dim-label")
        info_box.append(self.status_label)
        main_box.append(info_box)

        self.connect_button = Gtk.Button()
        self.connect_button.connect("clicked", self._on_connect_clicked)
        main_box.append(self.connect_button)

    def _update_ui(self, ap: AccessPoint):
        self.ap = ap
        self.icon.set_from_icon_name(self.ap.icon_name)

        if self.ap.is_active:
            self.ssid_label.set_text("Connected")
            self.status_label.set_text(f"{self.ap.ssid} ({self.ap.strength}%)")
            self.connect_button.set_label("Disconnect")
            self.connect_button.set_sensitive(True)
        else:
            self.ssid_label.set_text(self.ap.ssid)
            self.status_label.set_text(f"Strength: {self.ap.strength}%")
            self.connect_button.set_label("Connect")
            self.connect_button.set_sensitive(True)

    def _on_connect_clicked(self, button):
        if self.ap.is_active:
            self.wifi_manager.disconnect()
        else:
            saved_conn = self.wifi_manager.find_connection_by_ssid(self.ap.ssid)
            if saved_conn:
                 self.wifi_manager.connect_to_ap(self.ap.ssid)
            else:
                self._show_password_dialog()

    def _show_password_dialog(self):
        parent_window = self.get_ancestor(Gtk.Window)
        dialog = Gtk.Window(title=f"Connect to {self.ap.ssid}", transient_for=parent_window, modal=True, resizable=False)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=20, margin_bottom=20, margin_start=20, margin_end=20)
        
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
            self.connect_button.set_sensitive(False)
            self.connect_button.set_label("Connecting...")
            self.wifi_manager.connect_to_ap(self.ap.ssid, password, self._on_connect_callback)

        password_entry.connect('activate', do_connect_action)
        connect_btn.connect('clicked', do_connect_action)
        
        dialog.set_child(main_box)
        dialog.present()

    def _on_connect_callback(self, success, message):
        GLib.idle_add(self._update_connect_button_state, success, message)

    def _update_connect_button_state(self, success, message):
        self.connect_button.set_sensitive(True)
        if not success:
            stack = self.get_ancestor(NetworkStack)
            if stack and hasattr(stack, 'add_toast'):
                stack.add_toast(f"Connection failed: {message}")

