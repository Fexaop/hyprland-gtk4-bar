import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from service.audio import Audio, AudioStream, CvcImportError
from . import icons

class AudioStack(Gtk.Box):
    """Main Audio management widget."""

    def __init__(self, **kwargs):
        super().__init__(
            name="audio",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL,
            **kwargs
        )

        self.audio_service = None
        self.output_rows = {}
        self.input_rows = {}
        self.app_rows = {}

        try:
            self.audio_service = Audio()
            self._create_ui()
            self.audio_service.connect('changed', self._update_all_ui)
            GLib.idle_add(self._update_all_ui)
        except CvcImportError:
            self._create_error_ui()

    def _create_error_ui(self):
        error_label = Gtk.Label(label="Audio service is unavailable.\nCvc library not found.", halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, vexpand=True)
        self.append(error_label)

    def _create_ui(self):
        """Create the user interface."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        self.append(scrolled)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.set_margin_start(12); content_box.set_margin_end(12)
        content_box.set_margin_top(12); content_box.set_margin_bottom(12)
        scrolled.set_child(content_box)

        # Default device volume controls
        self.speaker_volume_box, self.speaker_volume_slider = self._create_volume_row("Default Output")
        self.speaker_volume_slider_handler = self.speaker_volume_slider.connect("value-changed", self._on_speaker_volume_changed)
        content_box.append(self.speaker_volume_box)

        self.mic_volume_box, self.mic_volume_slider = self._create_volume_row("Default Input")
        self.mic_volume_slider_handler = self.mic_volume_slider.connect("value-changed", self._on_mic_volume_changed)
        content_box.append(self.mic_volume_box)

        # Device Lists
        self.outputs_box, self.outputs_list_box = self._create_titled_list("Output Devices")
        content_box.append(self.outputs_box)

        self.inputs_box, self.inputs_list_box = self._create_titled_list("Input Devices")
        content_box.append(self.inputs_box)

        # Application Mixer
        self.apps_box, self.apps_list_box = self._create_titled_list("Applications")
        content_box.append(self.apps_box)

    def _update_all_ui(self, *args):
        self._update_default_controls()
        self._update_device_lists()
        self._update_applications_list()

    def _update_default_controls(self):
        # Speaker
        speaker = self.audio_service.speaker
        if speaker:
            self.speaker_volume_box.set_visible(True)
            self.speaker_volume_slider.handler_block(self.speaker_volume_slider_handler)
            self.speaker_volume_slider.set_value(speaker.volume)
            self.speaker_volume_slider.handler_unblock(self.speaker_volume_slider_handler)
        else:
            self.speaker_volume_box.set_visible(False)

        # Microphone
        mic = self.audio_service.microphone
        if mic:
            self.mic_volume_box.set_visible(True)
            self.mic_volume_slider.handler_block(self.mic_volume_slider_handler)
            self.mic_volume_slider.set_value(mic.volume)
            self.mic_volume_slider.handler_unblock(self.mic_volume_slider_handler)
        else:
            self.mic_volume_box.set_visible(False)

    def _update_device_lists(self):
        self._update_list(self.audio_service.speakers, self.audio_service.speaker, self.outputs_list_box, self.output_rows)
        self._update_list(self.audio_service.microphones, self.audio_service.microphone, self.inputs_list_box, self.input_rows)

    def _update_list(self, devices, default_device, list_box, row_dict):
        current_ids = list(row_dict.keys())
        for device in devices:
            is_default = default_device and device.id == default_device.id
            if device.id in row_dict:
                row_dict[device.id].update(device, is_default)
                current_ids.remove(device.id)
            else:
                row = AudioDeviceRow(device, is_default, self.audio_service)
                list_box.append(row)
                row_dict[device.id] = row
        
        for id in current_ids:
            row = row_dict.pop(id)
            list_box.remove(row)

    def _update_applications_list(self):
        current_ids = list(self.app_rows.keys())
        apps = self.audio_service.applications
        self.apps_box.set_visible(bool(apps))

        for app in apps:
            if app.id in self.app_rows:
                # Application rows update themselves via signals
                current_ids.remove(app.id)
            else:
                row = ApplicationStreamRow(app)
                self.apps_list_box.append(row)
                self.app_rows[app.id] = row
        
        for id in current_ids:
            row = self.app_rows.pop(id)
            self.apps_list_box.remove(row)
            row.cleanup()

    def _on_speaker_volume_changed(self, slider):
        if self.audio_service.speaker:
            self.audio_service.speaker.volume = slider.get_value()

    def _on_mic_volume_changed(self, slider):
        if self.audio_service.microphone:
            self.audio_service.microphone.volume = slider.get_value()

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
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.add_css_class("boxed-list")
        list_box.set_header_func(self._list_box_separator_header_func)
        box.append(list_box)
        return box, list_box

    def _create_volume_row(self, title):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_start(6); row_box.set_margin_end(6)
        
        icon = Gtk.Image(pixel_size=24)
        row_box.append(icon)

        text_label = Gtk.Label(label=title, halign=Gtk.Align.START)
        row_box.append(text_label)

        slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        slider.set_range(0, self.audio_service.max_volume)
        slider.set_draw_value(False)
        row_box.append(slider)
        
        return row_box, slider

class AudioDeviceRow(Gtk.ListBoxRow):
    def __init__(self, stream: AudioStream, is_default: bool, audio_service: Audio):
        super().__init__()
        self.stream = stream
        self.audio_service = audio_service
        
        gesture = Gtk.GestureClick.new()
        gesture.connect("pressed", self._on_pressed)
        self.add_controller(gesture)

        self._create_ui()
        self.update(stream, is_default)

    def _on_pressed(self, gesture, n_press, x, y):
        if n_press == 2:
            self._on_activate()

    def _create_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.main_box.set_margin_start(12); self.main_box.set_margin_end(12)
        self.main_box.set_margin_top(6); self.main_box.set_margin_bottom(6)
        self.set_child(self.main_box)

        self.icon = Gtk.Image(pixel_size=24)
        self.main_box.append(self.icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.START)
        self.main_box.append(text_box)

        self.name_label = Gtk.Label(halign=Gtk.Align.START)
        text_box.append(self.name_label)

        self.desc_label = Gtk.Label(halign=Gtk.Align.START, css_classes=["dim-label"])
        text_box.append(self.desc_label)

        self.check_icon = Gtk.Image(icon_name="object-select-symbolic", valign=Gtk.Align.CENTER)

    def update(self, stream: AudioStream, is_default: bool):
        self.stream = stream

        icon_name = "audio-card-symbolic"
        if "bluez" in (stream.name or "").lower():
            icon_name = "bluetooth-active-symbolic"
        elif stream.type == "microphones":
            icon_name = "audio-input-microphone-symbolic"

        self.icon.set_from_icon_name(icon_name)
        self.name_label.set_text(stream.description or stream.name)
        self.desc_label.set_visible(False)

        if is_default and not self.check_icon.get_parent():
            self.main_box.append(self.check_icon)
        elif not is_default and self.check_icon.get_parent():
            self.main_box.remove(self.check_icon)

    def _on_activate(self):
        self.audio_service.ignore_osd = True
        stream_type = Audio.get_stream_type(self.stream.stream)
        if stream_type == "speakers":
            self.audio_service._control.set_default_sink(self.stream.stream)
        elif stream_type == "microphones":
            self.audio_service._control.set_default_source(self.stream.stream)

class ApplicationStreamRow(Gtk.ListBoxRow):
    def __init__(self, stream: AudioStream):
        super().__init__()
        self.stream = stream
        self._create_ui()
        self.update()
        self.changed_handler = self.stream.connect("changed", lambda s: self.update())

    def _create_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12); main_box.set_margin_end(12)
        main_box.set_margin_top(6); main_box.set_margin_bottom(6)
        self.set_child(main_box)

        self.icon = Gtk.Image(valign=Gtk.Align.CENTER, pixel_size=32)
        main_box.append(self.icon)

        self.name_label = Gtk.Label(hexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        main_box.append(self.name_label)

        self.volume_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, width_request=100)
        self.volume_slider.set_range(0, self.stream._parent.max_volume)
        self.volume_slider.set_draw_value(False)
        self.slider_handler = self.volume_slider.connect("value-changed", self._on_volume_changed)
        main_box.append(self.volume_slider)

        self.mute_button = Gtk.ToggleButton(valign=Gtk.Align.CENTER)
        self.mute_icon = Gtk.Image()
        self.mute_button.set_child(self.mute_icon)
        self.mute_handler = self.mute_button.connect("toggled", self._on_mute_toggled)
        main_box.append(self.mute_button)

    def update(self):
        if self.stream.icon_name:
            self.icon.set_from_icon_name(self.stream.icon_name)
        else:
            self.icon.set_from_icon_name("audio-card-symbolic")
        
        self.name_label.set_text(self.stream.name)

        self.volume_slider.handler_block(self.slider_handler)
        self.volume_slider.set_value(self.stream.volume)
        self.volume_slider.handler_unblock(self.slider_handler)

        is_muted = self.stream.muted
        self.mute_button.handler_block(self.mute_handler)
        self.mute_button.set_active(is_muted)
        self.mute_button.handler_unblock(self.mute_handler)
        self.mute_icon.set_from_icon_name("audio-volume-muted-symbolic" if is_muted else "audio-volume-high-symbolic")

    def _on_volume_changed(self, slider):
        self.stream.volume = slider.get_value()

    def _on_mute_toggled(self, button):
        self.stream.muted = button.get_active()

    def cleanup(self):
        if self.stream and self.changed_handler:
            self.stream.disconnect(self.changed_handler)
            self.changed_handler = None

