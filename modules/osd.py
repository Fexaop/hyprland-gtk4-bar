import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
import os
from widgets.progressbar import CustomProgressBar
from service.audio import Audio # Import the Audio service
from service.backlight import BacklightService # Import the Backlight service

class Osd(Gtk.Box):
    def __init__(self, notch=None, stack=None, **kwargs):
        super().__init__(
            name="osd",
            spacing=8,
            orientation=Gtk.Orientation.VERTICAL
        )
        self.notch = notch
        self.stack = stack
        self.collapse_timeout_id = None  # Track the timeout for auto-collapse
        self.is_hovered = False  # Track hover state
        self.initial_setup_complete = False  # Track if initial setup is complete
        self.brightness_initialized = False  # Track brightness initialization
        self.volume_initialized = False  # Track volume initialization
        self.previous_brightness = 0  # Will be updated after service initialization
        self.previous_volume = 0  # Will be updated after service initialization
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.ran_once = False  # Track if the widget has been displayed once
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_halign(Gtk.Align.CENTER)
        main_box.set_valign(Gtk.Align.CENTER)
        self.append(main_box)

        # Horizontal box for brightness and volume
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        hbox.set_halign(Gtk.Align.CENTER)
        main_box.append(hbox)

        # Brightness section
        brightness_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        brightness_vbox.set_halign(Gtk.Align.CENTER)
        hbox.append(brightness_vbox)

        self.brightness_label = Gtk.Label(label="Brightness 0%")
        self.brightness_label.set_halign(Gtk.Align.CENTER)
        brightness_vbox.append(self.brightness_label)

        self.brightness_bar = CustomProgressBar("brightness-box")
        self.brightness_bar.set_size_request(150, 10)  # Height set to 10px
        brightness_vbox.append(self.brightness_bar)
        self.brightness_bar.connect("value-changed", self.on_brightness_changed)

        # Volume section
        volume_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        volume_vbox.set_halign(Gtk.Align.CENTER)
        hbox.append(volume_vbox)

        self.volume_label = Gtk.Label(label="Volume 0%")
        self.volume_label.set_halign(Gtk.Align.CENTER)
        volume_vbox.append(self.volume_label)

        self.volume_bar = CustomProgressBar("volume-box")
        self.volume_bar.set_size_request(150, 10)  # Height set to 10px
        volume_vbox.append(self.volume_bar)
        self.volume_bar.connect("value-changed", self.on_volume_bar_interact)

        # Setup hover detection
        self._setup_hover_detection()

        # Load main CSS
        css_file = os.path.join(os.path.dirname(__file__), "osd.css")
        main_css_provider = Gtk.CssProvider()
        main_css_provider.load_from_path(css_file)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            main_css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Initialize Backlight Service
        try:
            self.backlight_service = BacklightService.get_default()
            
            # Initial update for brightness display (without triggering notch)
            self._update_brightness_display_from_service(is_initial=True)
            
            # Set previous_brightness to current brightness fraction
            if self.backlight_service and self.backlight_service.available and self.backlight_service.max_brightness > 0:
                self.previous_brightness = self.backlight_service.brightness / self.backlight_service.max_brightness
            
            # Connect to brightness changes AFTER initial setup
            self.backlight_service.connect("notify::brightness", self._on_backlight_brightness_changed)
            self.backlight_service.connect("notify::available", self._on_backlight_availability_changed)
            
            self.brightness_initialized = True
                
        except Exception as e:
            self.backlight_service = None
            # Set a default/error state for brightness display
            self.update_brightness_label(0, error=True)
            self.brightness_initialized = True

        # Initialize Audio Service
        try:
            self.audio_service = Audio()
            
            # Initial update for volume display (without triggering notch)
            self._update_volume_display_from_service(is_initial=True)
            
            # Set previous_volume to current volume fraction
            if self.audio_service and self.audio_service.speaker:
                self.previous_volume = self.audio_service.speaker.volume / 100.0
            
            # Connect to audio changes AFTER initial setup
            self.audio_service.connect("speaker-changed", self._on_audio_speaker_property_changed)
            self.audio_service.connect("changed", self._on_audio_service_state_changed)
            
            self.volume_initialized = True
        except Exception as e:
            self.audio_service = None
            # Set a default/error state for volume display
            self.update_volume_label(0, False, error=True)
            self.volume_initialized = True

        # Mark initialization as complete
        self.initial_setup_complete = True

    def _setup_hover_detection(self):
        """Setup hover detection for the OSD widget"""
        # Create motion controller for hover detection
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("enter", self._on_mouse_enter)
        motion_controller.connect("leave", self._on_mouse_leave)
        self.add_controller(motion_controller)

    def _on_mouse_enter(self, controller, x, y):
        """Called when mouse enters the OSD area"""
        self.is_hovered = True
        
        # Cancel any pending collapse timeout
        if self.collapse_timeout_id:
            GLib.source_remove(self.collapse_timeout_id)
            self.collapse_timeout_id = None

    def _on_mouse_leave(self, controller):
        """Called when mouse leaves the OSD area"""
        self.is_hovered = False
        
        # Restart the collapse timer if the notch is open
        if self.notch and self.notch.stack and self.notch.stack.get_visible_child_name() == "osd":
            self.collapse_timeout_id = GLib.timeout_add_seconds(2, self._check_and_collapse_notch)

    def _should_open_notch(self, current_brightness=None, current_volume=None):
        """Check if notch should be opened based on value changes"""
        # Only proceed if both services are fully initialized
        if not (self.initial_setup_complete and self.brightness_initialized and self.volume_initialized and self.ran_once):
            print("OSD not fully initialized, skipping notch open.")
            self.ran_once = True
            return False
        
        brightness_changed = False
        volume_changed = False
        
        # Check brightness change
        if current_brightness is not None:
            brightness_changed = abs(current_brightness - self.previous_brightness) > 0.001
            if brightness_changed:
                self.previous_brightness = current_brightness
        
        # Check volume change
        if current_volume is not None:
            volume_changed = abs(current_volume - self.previous_volume) > 0.001
            if volume_changed:
                self.previous_volume = current_volume
        
        return brightness_changed or volume_changed

    def _open_notch_and_schedule_collapse(self, current_brightness=None, current_volume=None):
        """Open the notch and schedule auto-collapse after 2 seconds if values changed"""
        # Check if notch should be opened based on value changes
        should_open = self._should_open_notch(current_brightness, current_volume)
        
        # Only open notch if there was an actual change
        if should_open and self.notch:
            self.notch.open_notch("osd")
            
        # Always handle timeout management if the notch is currently open
        # (either from this change or already open from previous changes)
        if self.notch and self.notch.stack and self.notch.stack.get_visible_child_name() == "osd":
            # Cancel any existing timeout
            if self.collapse_timeout_id:
                GLib.source_remove(self.collapse_timeout_id)
                self.collapse_timeout_id = None
                
            # Only schedule collapse if not currently hovered
            if not self.is_hovered:
                self.collapse_timeout_id = GLib.timeout_add_seconds(2, self._check_and_collapse_notch)

    def _check_and_collapse_notch(self):
        """Check if OSD is still visible and collapse if needed"""
        # Don't collapse if currently hovered
        if self.is_hovered:
            # Reschedule check for later
            self.collapse_timeout_id = GLib.timeout_add_seconds(2, self._check_and_collapse_notch)
            return False
            
        if self.notch.stack and self.notch.stack.get_visible_child_name() == "osd":
            if self.notch:
                self.notch.collapse_notch()
        
        # Clear the timeout ID
        self.collapse_timeout_id = None
        return False  # Don't repeat the timeout
        
    def print_box_size(self):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        return False

    def _update_brightness_display_from_service(self, is_initial=False):
        """Update brightness display from the backlight service."""
        if self.backlight_service and self.backlight_service.available:
            current_brightness = self.backlight_service.brightness
            max_brightness = self.backlight_service.max_brightness
            
            if max_brightness > 0:
                fraction = current_brightness / max_brightness
                
                # Update progress bar only if the value has changed
                if abs(self.brightness_bar.get_fraction() - fraction) > 0.001:
                    self.brightness_bar.set_fraction(fraction)
                
                self.update_brightness_label(fraction)
                
                # Initialize previous_brightness on first run
                if is_initial:
                    self.previous_brightness = fraction
            else:
                self.update_brightness_label(0, error=True)
        else:
            if abs(self.brightness_bar.get_fraction() - 0) > 0.001:
                self.brightness_bar.set_fraction(0)
            self.update_brightness_label(0, error=not self.backlight_service)

    def _on_backlight_brightness_changed(self, backlight_service, pspec):
        """Handle brightness changes from the backlight service."""
        # Calculate current brightness fraction
        current_brightness_fraction = 0
        if self.backlight_service and self.backlight_service.available:
            current_brightness = self.backlight_service.brightness
            max_brightness = self.backlight_service.max_brightness
            if max_brightness > 0:
                current_brightness_fraction = current_brightness / max_brightness
        
        self._update_brightness_display_from_service()
        # Open notch and schedule collapse when brightness changes (only after initialization)
        self._open_notch_and_schedule_collapse(current_brightness=current_brightness_fraction)

    def _on_backlight_availability_changed(self, backlight_service, pspec):
        """Handle backlight availability changes."""
        self._update_brightness_display_from_service()

    def _update_volume_display_from_service(self, is_initial=False):
        if self.audio_service and self.audio_service.speaker:
            volume_percentage = self.audio_service.speaker.volume # float 0-100
            is_muted = self.audio_service.speaker.muted
            
            fraction = volume_percentage / 100.0
            
            # Update progress bar only if the value has changed
            if abs(self.volume_bar.get_fraction() - fraction) > 0.001:
                self.volume_bar.set_fraction(fraction)
            
            self.update_volume_label(fraction, is_muted)
            
            # Initialize previous_volume on first run
            if is_initial:
                self.previous_volume = fraction
        else:
            if abs(self.volume_bar.get_fraction() - 0) > 0.001:
                 self.volume_bar.set_fraction(0)
            self.update_volume_label(0, False, error=not self.audio_service)

    def _on_audio_speaker_property_changed(self, audio_service_instance):
        # This signal means the default speaker (or its properties like volume/mute) changed.
        # Calculate current volume fraction
        current_volume_fraction = 0
        if self.audio_service and self.audio_service.speaker:
            volume_percentage = self.audio_service.speaker.volume
            current_volume_fraction = volume_percentage / 100.0
        
        self._update_volume_display_from_service()
        # Open notch and schedule collapse when volume changes (only after initialization)
        self._open_notch_and_schedule_collapse(current_volume=current_volume_fraction)

    def _on_audio_service_state_changed(self, audio_service_instance):
        # This signal is for general changes in the audio service.
        # It's a good place to ensure the speaker is picked up if it wasn't ready initially.
        self._update_volume_display_from_service()

    def update_brightness_label(self, fraction, error=False):
        if error:
            self.brightness_label.set_label("Brightness N/A")
            return
        percentage = int(fraction * 100)
        self.brightness_label.set_label(f"Brightness {percentage}%")

    def update_volume_label(self, fraction, is_muted=False, error=False):
        if error:
            self.volume_label.set_label("Volume N/A")
            return
        percentage = int(fraction * 100)
        if is_muted:
            self.volume_label.set_label(f"Volume {percentage}% (Muted)")
        else:
            self.volume_label.set_label(f"Volume {percentage}%")

    def on_brightness_changed(self, widget, fraction):
        """Triggered by user interaction with brightness_bar"""
        self.update_brightness_label(fraction)  # Keep label in sync with bar
        
        if self.backlight_service and self.backlight_service.available:
            # Calculate the actual brightness value
            max_brightness = self.backlight_service.max_brightness
            new_brightness = int(fraction * max_brightness)
            
            # Set brightness via the service
            self.backlight_service.set_brightness(new_brightness)

    def on_volume_bar_interact(self, widget, fraction):
        """Triggered by user interaction with volume_bar"""
        percentage = int(fraction * 100)
        if self.audio_service and self.audio_service.speaker:
            self.audio_service.speaker.volume = float(percentage) # Expected by AudioStream
            # Mute state is handled separately, interaction with bar usually means unmuting.
            if self.audio_service.speaker.muted:
                 self.audio_service.speaker.muted = False
        # The actual update of the label and bar fraction will come from the
        # _on_audio_speaker_property_changed callback, ensuring UI reflects actual state.