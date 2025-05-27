# main.py
import sys
import gi
import logging
import math

# --- GTK / LibAdwaita / Playerctl Setup ---
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Playerctl", "2.0") # Ensure this matches helpers

from gi.repository import Gtk, Adw, GLib, Gdk, Pango, Playerctl # Make sure Playerctl is imported

# --- Import Helper Classes ---
try:
    from service.mpris import MprisPlayerManager, MprisPlayer, PlayerctlImportError
except ImportError as e:
    print(f"FATAL: Error importing helper classes: {e}", file=sys.stderr)
    print("Make sure 'playerctl_helpers.py' is in the same directory.", file=sys.stderr)
    sys.exit(1)
except PlayerctlImportError as e:
    # Handle import error from within the helper module itself
    print(f"FATAL: {e}", file=sys.stderr)
    sys.exit(1)


# --- Logging Setup ---
# Configure logging for the main application
# This will also capture logs from the helper module if its logger is set up correctly
logging.basicConfig(level=logging.INFO, # Change to DEBUG for more verbose output
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout) # Log to stdout
logger = logging.getLogger(__name__) # Get logger for this module


# --- Helper Function to Format Time ---
def format_time(microseconds):
    """Converts microseconds to MM:SS format string."""
    if microseconds is None or not isinstance(microseconds, (int, float)) or microseconds < 0:
        return "--:--"
    # Ensure integer division
    seconds_total = int(microseconds // 1_000_000)
    minutes = seconds_total // 60
    seconds = seconds_total % 60
    return f"{minutes:02}:{seconds:02}"


# --- Main Application Window ---
class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing MainWindow...")

        self.player_widgets = {} # player_name -> {'box': Gtk.Widget, 'controls': dict}
        self.player_wrappers = {} # player_name -> MprisPlayer instance
        self._scale_update_locks = {} # player_name -> bool (prevent feedback loop)
        self.manager = None # Initialize manager reference

        self.set_title("MPRIS Player Control (GTK4)")
        self.set_default_size(500, 400) # Adjusted default size

        # --- Main Layout ---
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_top(10)
        self.main_box.set_margin_bottom(10)
        self.main_box.set_margin_start(10)
        self.main_box.set_margin_end(10)

        # --- Scrolled Window ---
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_child(self.main_box)

        # --- Placeholder for No Players ---
        self.no_players_label = Gtk.Label(label="No active media players found.")
        self.no_players_label.set_vexpand(True)
        self.no_players_label.set_halign(Gtk.Align.CENTER)
        self.no_players_label.set_valign(Gtk.Align.CENTER)
        # Make it less prominent using Adwaita style class
        self.no_players_label.add_css_class("dim-label")
        # Add initially, will be hidden when players appear
        self.main_box.append(self.no_players_label)

        self.set_child(scrolled_window)

        # --- Start the Player Manager ---
        try:
            logger.info("Creating MprisPlayerManager instance...")
            self.manager = MprisPlayerManager()
            logger.info("Connecting MainWindow signals to MprisPlayerManager...")
            self.manager.connect("player-appeared", self.on_player_appeared)
            self.manager.connect("player-vanished", self.on_player_vanished) # Connect vanish signal
            logger.info("MPRIS Manager initialized and signals connected.")

            # Initial check for players will happen via manager's init

        except PlayerctlImportError as e: # Catch specific import error
             logger.error(f"Failed to start MPRIS Manager: {e}")
             self.show_error_message(f"Error: {e}\nPlease ensure Playerctl is installed correctly.")
        except Exception as e:
            logger.exception(f"Unexpected error initializing MprisPlayerManager: {e}")
            self.show_error_message(f"Critical Error Initializing Player Manager:\n{e}")

    def show_error_message(self, text):
        """Displays an error message instead of the 'no players' label."""
        # Ensure placeholder is removed if it exists
        if self.no_players_label.get_parent() == self.main_box:
            self.main_box.remove(self.no_players_label)

        # Check if an error label already exists
        existing_error = None
        child = self.main_box.get_first_child()
        while child:
            if "error-label" in child.get_css_classes():
                existing_error = child
                break
            child = child.get_next_sibling()

        if existing_error:
            existing_error.set_label(text) # Update existing error
        else:
            error_label = Gtk.Label(label=text)
            error_label.set_wrap(True)
            error_label.set_vexpand(True)
            error_label.set_halign(Gtk.Align.CENTER)
            error_label.set_valign(Gtk.Align.CENTER)
            error_label.add_css_class("error") # Style as error
            error_label.add_css_class("error-label") # Add marker class
            self.main_box.append(error_label)

    def update_no_players_label_visibility(self):
        """Shows or hides the 'No active media players' label."""
        has_players = bool(self.player_widgets)
        needs_label = not has_players
        is_visible = self.no_players_label.is_visible()
        parent = self.no_players_label.get_parent()

        if needs_label and not parent:
             # Add the label back if needed and not present
             self.main_box.prepend(self.no_players_label) # Add to top
             self.no_players_label.set_visible(True)
             logger.debug("Showing 'No players' label.")
        elif not needs_label and parent:
             # Remove the label if not needed and present
             self.main_box.remove(self.no_players_label)
             logger.debug("Hiding 'No players' label.")
        elif needs_label and parent and not is_visible:
             # Ensure visible if needed and present but hidden
             self.no_players_label.set_visible(True)
             logger.debug("Making 'No players' label visible.")


    def create_player_widget(self, mpris_player: MprisPlayer):
        """Creates a Gtk widget group for a single player."""
        player_name = mpris_player.player_name
        logger.info(f"Creating widget UI for player: {player_name}")

        # Use Adw.PreferencesGroup for a nicer look and separation
        # frame = Adw.PreferencesGroup()
        # frame.set_title(player_name) # Adwaita way
        # Or stick with Gtk.Frame
        frame = Gtk.Frame()
        label_widget = Gtk.Label(xalign=0)
        label_widget.set_markup(f"<b>{GLib.markup_escape_text(player_name)}</b>")
        frame.set_label_widget(label_widget)
        frame.set_label_align(0.05) # Align the label widget itself to the left edge (GTK4 style)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(5)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        frame.set_child(vbox)

        controls = {} # To store references to widgets for easy update

        # --- Metadata Labels ---
        # Use Adw.ActionRow for label + value? Simpler with Gtk.Label for now.
        controls['title_label'] = Gtk.Label(label="Title: N/A", xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=50)
        controls['artist_label'] = Gtk.Label(label="Artist: N/A", xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=50)
        controls['album_label'] = Gtk.Label(label="Album: N/A", xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=50)
        controls['status_label'] = Gtk.Label(label="Status: Unknown", xalign=0)

        vbox.append(controls['title_label'])
        vbox.append(controls['artist_label'])
        vbox.append(controls['album_label'])
        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL, margin_top=5, margin_bottom=5)) # Separator
        vbox.append(controls['status_label'])


        # --- Seek Bar ---
        hbox_seek = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        vbox.append(hbox_seek)

        controls['pos_label'] = Gtk.Label(label="--:--")
        # Range is microseconds. Default upper=1 avoids division by zero if length is initially unknown/zero.
        adj = Gtk.Adjustment(value=0, lower=0, upper=1.0, step_increment=1_000_000, page_increment=10_000_000, page_size=0)
        # Use has_origin=False to prevent the line at zero
        controls['seek_scale'] = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj, digits=0, has_origin=False)
        controls['seek_scale'].set_hexpand(True)
        controls['seek_scale'].set_draw_value(False) # Don't draw numeric value on scale
        controls['seek_scale'].set_tooltip_text("Seek position")
        controls['len_label'] = Gtk.Label(label="--:--")

        hbox_seek.append(controls['pos_label'])
        hbox_seek.append(controls['seek_scale'])
        hbox_seek.append(controls['len_label'])

        # --- Control Buttons ---
        hbox_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_buttons.set_halign(Gtk.Align.CENTER)
        hbox_buttons.set_margin_top(5)
        vbox.append(hbox_buttons)

        controls['prev_button'] = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        controls['prev_button'].set_tooltip_text("Previous")
        controls['play_pause_button'] = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        # Tooltip set dynamically based on state
        controls['next_button'] = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        controls['next_button'].set_tooltip_text("Next")
        controls['shuffle_button'] = Gtk.ToggleButton()
        shuffle_img = Gtk.Image.new_from_icon_name("media-playlist-shuffle-symbolic")
        controls['shuffle_button'].set_child(shuffle_img)
        controls['shuffle_button'].set_tooltip_text("Toggle Shuffle")
        # Add CSS class for potential styling
        controls['shuffle_button'].add_css_class("shuffle-button")


        hbox_buttons.append(controls['prev_button'])
        hbox_buttons.append(controls['play_pause_button'])
        hbox_buttons.append(controls['next_button'])
        hbox_buttons.append(controls['shuffle_button'])


        # --- Connect Signals ---
        logger.debug(f"Connecting UI signals for {player_name}")
        # Player actions -> MprisPlayer methods
        # Use player name to retrieve wrapper in case mpris_player becomes invalid later
        controls['prev_button'].connect("clicked", self.on_control_button_clicked, "previous", player_name)
        controls['play_pause_button'].connect("clicked", self.on_control_button_clicked, "play_pause", player_name)
        controls['next_button'].connect("clicked", self.on_control_button_clicked, "next", player_name)
        # Use a dedicated handler for toggle button to avoid direct lambda issues
        controls['shuffle_button'].connect("toggled", self.on_shuffle_toggled, player_name)

        # Seeking (handle potential feedback loop)
        scale = controls['seek_scale']
        self._scale_update_locks[player_name] = False # Initialize lock
        # Use value-changed and check lock.
        scale.connect("value-changed", self.on_scale_value_changed, player_name)

        logger.debug(f"Finished creating widget UI for {player_name}")
        # Return the main container widget and the controls dictionary
        return frame, controls

    def on_control_button_clicked(self, button, action: str, player_name: str):
        """Generic handler for Previous, Play/Pause, Next buttons."""
        logger.debug(f"Control button '{action}' clicked for {player_name}")
        if player_name in self.player_wrappers:
            player = self.player_wrappers[player_name]
            action_method = getattr(player, action, None)
            if action_method and callable(action_method):
                action_method() # Call the corresponding method on the wrapper
            else:
                logger.error(f"Action '{action}' not found on MprisPlayer wrapper for {player_name}")
        else:
            logger.warning(f"Control button '{action}' clicked, but wrapper for {player_name} not found.")


    def on_shuffle_toggled(self, button: Gtk.ToggleButton, player_name: str):
        """Handles the shuffle toggle button state change."""
        if player_name not in self.player_wrappers:
            logger.warning(f"Shuffle toggled, but wrapper for {player_name} not found.")
            return

        player = self.player_wrappers[player_name]
        is_active = button.get_active() # The new state of the button
        current_player_state = player.shuffle # The current state of the player

        logger.debug(f"Shuffle button toggled for {player_name}. Button active: {is_active}, Player state: {current_player_state}")

        # Only trigger the player action if the button's new state
        # is different from the player's current state. This prevents loops
        # where programmatic updates trigger this handler.
        if is_active != current_player_state:
             logger.info(f"Shuffle button state differs from player state for {player_name}. Calling toggle_shuffle().")
             player.toggle_shuffle()
        else:
             logger.debug(f"Shuffle button state matches player state for {player_name}. No action needed.")


    def on_scale_value_changed(self, scale: Gtk.Scale, player_name: str):
        """Handle scale value change, initiated by user or programmatically."""
        if self._scale_update_locks.get(player_name, False):
            # logger.debug(f"Scale value changed for {player_name} programmatically, ignoring seek.")
            return # Ignore programmatic changes triggered by update_player_widget

        if player_name not in self.player_wrappers:
            logger.warning(f"Scale value changed, but wrapper for {player_name} not found.")
            return

        player = self.player_wrappers[player_name]
        new_position = int(scale.get_value())
        logger.debug(f"User changed scale value for {player_name} to {new_position} us (seeking)")

        if player.can_seek:
            # Use the property setter which handles scheduling and error checking
            player.position = new_position
            # Update the position label immediately for better responsiveness during drag
            if player_name in self.player_widgets:
                 controls = self.player_widgets[player_name]['controls']
                 controls['pos_label'].set_text(format_time(new_position))
        else:
             logger.warning(f"Seek attempted on {player_name}, but player cannot seek.")
             # Optionally reset scale value if seek is not possible?
             # current_pos = player.position or 0
             # scale.get_adjustment().set_value(float(current_pos))


    def update_player_widget(self, mpris_player: MprisPlayer, player_name: str):
        """Updates the UI elements for a specific player based on its current state."""
        # This can be called by 'changed' signal or initially by 'on_player_appeared'
        logger.info(f"[Update UI] update_player_widget called for {player_name}")
        if player_name not in self.player_widgets:
            logger.warning(f"[Update UI] Attempted to update widget for unknown/removed player: {player_name}")
            return False # Indicate update failed / stop GLib.idle_add if applicable

        widget_info = self.player_widgets[player_name]
        controls = widget_info['controls']
        logger.debug(f"[Update UI] Updating widget elements for player: {player_name}")

        # --- Update Labels ---
        # Use GLib markup escape just in case titles/etc contain characters like < > &
        title_text = GLib.markup_escape_text(mpris_player.title or 'N/A')
        artist_text = GLib.markup_escape_text(mpris_player.artist or 'N/A')
        album_text = GLib.markup_escape_text(mpris_player.album or 'N/A')

        controls['title_label'].set_text(title_text)
        controls['title_label'].set_tooltip_text(f"Title: {title_text}")
        controls['artist_label'].set_text(artist_text)
        controls['artist_label'].set_tooltip_text(f"Artist: {artist_text}")
        controls['album_label'].set_text(album_text)
        controls['album_label'].set_tooltip_text(f"Album: {album_text}")
        controls['status_label'].set_text(f"Status: {mpris_player.playback_status.capitalize()}")

        # --- Update Button Sensitivity ---
        controls['prev_button'].set_sensitive(mpris_player.can_go_previous)
        controls['play_pause_button'].set_sensitive(mpris_player.can_pause or mpris_player.can_play)
        controls['next_button'].set_sensitive(mpris_player.can_go_next)
        can_shuffle = mpris_player.can_shuffle # Cache capability
        controls['shuffle_button'].set_sensitive(can_shuffle)

        # --- Update Play/Pause Button Icon ---
        is_playing = mpris_player.playback_status == "playing"
        play_icon = "media-playback-pause-symbolic" if is_playing else "media-playback-start-symbolic"
        controls['play_pause_button'].set_icon_name(play_icon)
        controls['play_pause_button'].set_tooltip_text("Pause" if is_playing else "Play")

        # --- Update Shuffle Button State (using corrected block/unblock) ---
        shuffle_button = controls['shuffle_button']
        handler_id = 0 # Initialize handler ID

        # Find the handler ID without blocking yet
        try:
            # Use handler_find to just get the ID
            handler_id = shuffle_button.handler_find(self.on_shuffle_toggled)
        except Exception as e:
            logger.warning(f"[Update UI] Error finding shuffle handler for {player_name}: {e}")

        # Block the handler if found
        if handler_id > 0:
            shuffle_button.handler_block(handler_id)
            # logger.debug(f"[Update UI] Blocked shuffle handler ({handler_id}) for {player_name}")

        try:
            # --- Set the button state ---
            if can_shuffle: # Only change active state if player supports shuffle
                shuffle_state = mpris_player.shuffle
                # Only update if visual state differs from player state
                if shuffle_button.get_active() != shuffle_state:
                    logger.debug(f"[Update UI] Setting shuffle button active state to {shuffle_state} for {player_name}")
                    shuffle_button.set_active(shuffle_state) # Set the state while blocked
            else: # Ensure button is off if shuffle not supported
                if shuffle_button.get_active():
                    logger.debug(f"[Update UI] Disabling shuffle button (player cannot shuffle) for {player_name}")
                    shuffle_button.set_active(False)
            # --- End of setting state ---
        finally:
            # Unblock the handler if it was found and blocked
            if handler_id > 0:
                shuffle_button.handler_unblock(handler_id)
                # logger.debug(f"[Update UI] Unblocked shuffle handler ({handler_id}) for {player_name}")


        # --- Update Seek Bar ---
        scale = controls['seek_scale']
        pos_label = controls['pos_label']
        len_label = controls['len_label']
        adj = scale.get_adjustment()

        length_us = mpris_player.length
        # Ensure position is an int, default to 0 if None/invalid
        pos_val = mpris_player.position
        position_us = int(pos_val) if isinstance(pos_val, (int, float)) else 0

        can_seek = mpris_player.can_seek
        scale.set_sensitive(can_seek)

        if can_seek and length_us is not None and length_us > 0:
            # logger.debug(f"[Update UI] Updating seek bar for {player_name}: Pos={position_us}, Len={length_us}")
            # Update adjustment upper limit if necessary
            current_upper = adj.get_upper()
            if not math.isclose(current_upper, length_us):
                 logger.debug(f"[Update UI] Setting adjustment upper limit to {length_us} for {player_name}")
                 adj.set_upper(float(length_us)) # Ensure float

            # Update scale value, preventing feedback loop
            self._scale_update_locks[player_name] = True # Lock before setting value
            try:
                # Clamp position just in case it exceeds length briefly
                clamped_position = min(position_us, length_us)
                current_scale_val = adj.get_value()
                # Only update if significantly different to avoid jitter during playback
                # Use a tolerance (e.g., 1 second = 1,000,000 microseconds)
                if abs(current_scale_val - clamped_position) > 1_000_000:
                     logger.debug(f"[Update UI] Setting scale value to {clamped_position} for {player_name} (Diff > 1s)")
                     adj.set_value(float(clamped_position)) # Ensure float
                # else:
                #      logger.debug(f"[Update UI] Scale value for {player_name} is close enough, not updating visually.")

            finally:
                 # Use idle_add to release the lock *after* potential value-changed signal
                 GLib.idle_add(self.release_scale_lock, player_name, priority=GLib.PRIORITY_DEFAULT_IDLE)

            pos_label.set_text(format_time(position_us))
            len_label.set_text(format_time(length_us))
        else:
            # logger.debug(f"[Update UI] Player {player_name} cannot seek or has no length. Disabling/resetting scale.")
            # Cannot seek or no length info
            if not math.isclose(adj.get_upper(), 1.0): # Reset adjustment if needed
                 adj.set_upper(1.0)
            if not math.isclose(adj.get_value(), 0.0):
                 adj.set_value(0.0)
            pos_label.set_text("--:--")
            len_label.set_text("--:--")

        # logger.debug(f"[Update UI] Finished update for {player_name}")
        return False # Return False for GLib.idle_add source funcs

    def release_scale_lock(self, player_name):
        """Callback for GLib.idle_add to release the scale update lock."""
        if player_name in self._scale_update_locks:
             # logger.debug(f"Releasing scale update lock for {player_name}")
             self._scale_update_locks[player_name] = False
        return GLib.SOURCE_REMOVE # Run only once

    # --- Signal Handlers for Manager ---
    def on_player_appeared(self, manager: MprisPlayerManager, playerctl_player: Playerctl.Player):
        """Handles the 'player-appeared' signal from MprisPlayerManager."""
        logger.info(f"[MainWindow Log] === Player Appeared Signal Received ===")
        logger.debug(f"[MainWindow Log] Received player object: {playerctl_player}")
        player_name = None # Initialize
        try:
            # It's crucial to get the name to manage widgets/wrappers
            player_name = playerctl_player.get_property("player-name")
            if not player_name:
                logger.error("[MainWindow Log] CRITICAL: Appeared player has no name! Cannot proceed.")
                return
            logger.info(f"[MainWindow Log] Got player name: '{player_name}'")

        except Exception as e:
            logger.exception(f"[MainWindow Log] CRITICAL: Could not get name for appeared player object {playerctl_player}: {e}")
            return # Stop if we can't get a name

        if player_name in self.player_widgets:
            logger.warning(f"[MainWindow Log] Player '{player_name}' appeared but widget/wrapper already exists. Ignoring.")
            return

        logger.info(f"[MainWindow Log] Creating MprisPlayer wrapper for '{player_name}'.")
        # 1. Create the MprisPlayer wrapper GObject
        try:
            mpris_player = MprisPlayer(player=playerctl_player)
            self.player_wrappers[player_name] = mpris_player
            logger.info(f"[MainWindow Log] Wrapper created. Creating UI widget for '{player_name}'.")
        except Exception as e:
            logger.exception(f"[MainWindow Log] CRITICAL: Failed to create MprisPlayer wrapper for '{player_name}'.")
            return # Stop if wrapper creation fails

        # 2. Create the UI widget for the player
        try:
            player_widget, controls = self.create_player_widget(mpris_player)
            self.player_widgets[player_name] = {'box': player_widget, 'controls': controls}
            logger.info(f"[MainWindow Log] UI widget created: {player_widget}. Appending to main_box.")
        except Exception as e:
             logger.exception(f"[MainWindow Log] CRITICAL: Failed to create UI widget for '{player_name}'. Cleaning up wrapper.")
             # Clean up the wrapper if UI creation failed
             if player_name in self.player_wrappers:
                 # TODO: Add a more formal cleanup method to MprisPlayer if needed
                 del self.player_wrappers[player_name]
             return # Stop processing this player

        # 3. Add the widget to the main layout
        self.main_box.append(player_widget)
        self.update_no_players_label_visibility() # Hide "No players" label
        logger.info(f"[MainWindow Log] Widget appended. Connecting wrapper signals for '{player_name}'.")

        # 4. Connect signals from the MprisPlayer wrapper to UI updates/cleanup
        try:
            mpris_player.connect("changed", self.on_player_changed, player_name)
            mpris_player.connect("exit", self.on_player_exit, player_name)
            logger.info(f"[MainWindow Log] Wrapper signals connected. Scheduling initial UI update for '{player_name}'.")
        except Exception as e:
             logger.exception(f"[MainWindow Log] CRITICAL: Failed to connect signals for wrapper '{player_name}'. Cleaning up.")
             # Clean up widget and wrapper
             self.on_player_vanished(None, player_name) # Simulate vanish
             return

        # 5. Initial UI population
        # Schedule the first update to ensure UI reflects the state *after* the widget is added
        GLib.idle_add(self.update_player_widget, mpris_player, player_name, priority=GLib.PRIORITY_DEFAULT)
        logger.info(f"[MainWindow Log] Initial update scheduled for '{player_name}'. on_player_appeared finished.")
        logger.info(f"[MainWindow Log] =========================================")


    def on_player_vanished(self, manager: MprisPlayerManager | None, player_name: str):
        """Handles player removal, either via manager signal or MprisPlayer exit."""
        # This is the central cleanup point for a player's UI and wrapper reference.
        logger.info(f"[MainWindow Log] --- Player Vanished/Exit Processing START for: '{player_name}' ---")
        if player_name in self.player_widgets:
            widget_info = self.player_widgets[player_name]
            widget_box = widget_info.get('box')
            if widget_box and widget_box.get_parent() == self.main_box:
                logger.info(f"[MainWindow Log] Removing UI widget for '{player_name}'.")
                self.main_box.remove(widget_box)
            else:
                 logger.warning(f"[MainWindow Log] Widget for '{player_name}' found in dict, but not in main_box or already removed.")
            del self.player_widgets[player_name]
            logger.debug(f"[MainWindow Log] Widget dict entry removed for '{player_name}'.")
        else:
             logger.warning(f"[MainWindow Log] Received vanish/exit signal for '{player_name}', but no widget found in dict.")

        if player_name in self.player_wrappers:
            logger.info(f"[MainWindow Log] Deleting wrapper reference for '{player_name}'.")
            # Disconnect signals? The wrapper's exit handler should manage its own Playerctl connections.
            # We just remove our reference to allow GC.
            # TODO: Consider explicitly disconnecting signals connected *in this file* if any remain.
            # For now, assuming wrapper handles its own cleanup upon 'exit' emission.
            del self.player_wrappers[player_name]
        else:
            logger.warning(f"[MainWindow Log] Received vanish/exit signal for '{player_name}', but no wrapper found in dict.")

        if player_name in self._scale_update_locks:
             logger.debug(f"[MainWindow Log] Deleting scale lock entry for '{player_name}'.")
             del self._scale_update_locks[player_name]

        self.update_no_players_label_visibility() # Check if we need to show "No players" label
        logger.info(f"[MainWindow Log] --- Finished Vanish/Exit Processing for: '{player_name}' ---")


    # --- Signal Handlers for Player Wrapper ---
    def on_player_changed(self, mpris_player: MprisPlayer, player_name: str):
        """Handles the 'changed' signal from an MprisPlayer wrapper."""
        # logger.debug(f"[MainWindow Log] Received 'changed' signal from wrapper for '{player_name}'. Scheduling UI update.")
        # Schedule the update to avoid direct work in signal handler and batch updates
        # Check if wrapper still exists before scheduling update
        if player_name in self.player_wrappers:
            # Pass the actual wrapper object to the update function
            GLib.idle_add(self.update_player_widget, self.player_wrappers[player_name], player_name, priority=GLib.PRIORITY_DEFAULT)
        else:
            logger.warning(f"[MainWindow Log] Received 'changed' signal for '{player_name}', but wrapper no longer exists. Ignoring update.")


    def on_player_exit(self, mpris_player: MprisPlayer, exited: bool, player_name: str):
        """Handles the 'exit' signal from an MprisPlayer wrapper."""
        logger.info(f"[MainWindow Log] Received 'exit' signal from wrapper for '{player_name}'. Triggering central vanish/cleanup logic.")
        # Use the same cleanup logic as when the manager reports vanish
        # Pass None for manager as this wasn't triggered by the manager directly
        self.on_player_vanished(None, player_name)


# --- Application Class ---
class PlayerApp(Adw.Application):
    def __init__(self, **kwargs):
        logger.info("Initializing PlayerApp (Adw.Application)...")
        super().__init__(application_id="org.example.mprisplayergtk4", **kwargs)
        self.window = None

    def do_activate(self):
        logger.info("Application activated.")
        # Create the main window if it doesn't exist or hasn't been destroyed
        # Use Gtk.Window.is_destroyed() which is available in GTK4
        if not self.window or self.window.is_destroyed():
             logger.info("Creating MainWindow...")
             try:
                 self.window = MainWindow(application=self)
             except Exception as e:
                  logger.exception("CRITICAL: Failed to create MainWindow in do_activate.")
                  # Show a simple GTK error dialog? Needs GTK to be running.
                  dialog = Gtk.MessageDialog(transient_for=None, modal=True,
                                            message_type=Gtk.MessageType.ERROR,
                                            buttons=Gtk.ButtonsType.OK,
                                            text="Application Error",
                                            secondary_text=f"Could not create the main window:\n{e}")
                  dialog.connect("response", lambda d, r: d.destroy())
                  dialog.present() # Use present() in GTK4
                  return # Don't try to present a non-existent window

        logger.info("Presenting MainWindow.")
        self.window.present() # Use present() in GTK4

    def do_startup(self):
        # Chain up to parent class
        Adw.Application.do_startup(self)
        logger.info("Application startup phase completed.")
        # Things done once per application lifetime (like setting up actions) go here

    def do_shutdown(self):
        logger.info("Application shutting down.")
        # Clean up resources if necessary. GObject usually handles references.
        # Explicitly destroy window? Adw.Application might do this.
        if self.window and not self.window.is_destroyed():
            logger.debug("Destroying main window during shutdown.")
            self.window.destroy()
            self.window = None # Clear reference

        # Chain up to parent class *last*
        Adw.Application.do_shutdown(self)
        logger.info("Application shutdown phase completed.")


# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting application...")
    # Consider setting application flags if needed (e.g., non-unique)
    app = PlayerApp()
    # Run the application, Gtk/Adw handles the main loop
    exit_status = app.run(sys.argv)
    logger.info(f"Application finished with exit status: {exit_status}")
    sys.exit(exit_status)