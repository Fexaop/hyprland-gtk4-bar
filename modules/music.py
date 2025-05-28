from gi.repository import Gtk, GLib, GdkPixbuf, Pango
import urllib.request
import os
import tempfile
from service.mpris import MprisPlayerManager, MprisPlayer
from widgets.progressbar import CustomProgressBar
import modules.icons as icons

class MusicPlayer(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.set_name("music-player")
        
        self.manager = MprisPlayerManager()
        self.manager.connect("player-appeared", self.on_player_appeared)
        self.manager.connect("player-vanished", self.on_player_vanished)
        
        self.players = {}  # {player_name: {'mpris_player': MprisPlayer, 'switcher_button': Gtk.Button, 'label': Gtk.Label, 'active_icon': str, 'inactive_icon': str}}
        self.active_player = None
        self.active_player_name = None
        
        self.track_title = "No Track"
        self.artist_name = "Unknown Artist"
        self.track_image = None
        self.track_length = 0
        self.current_position = 0
        self.playback_status = "stopped"
        self.can_go_previous = False
        self.can_go_next = False
        self.can_pause = False
        
        self.switcher_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.switcher_box.set_size_request(32, -1)
        self.switcher_box.set_valign(Gtk.Align.CENTER)
        self.switcher_box.hide()
        self.append(self.switcher_box)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_hexpand(True)
        self.append(self.stack)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_start(10)
        self.main_box.set_margin_end(10)
        self.main_box.set_margin_top(10)
        self.main_box.set_margin_bottom(10)
        
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_box.set_size_request(380, -1)
        top_box.set_halign(Gtk.Align.CENTER)
        
        self.album_art_image = Gtk.Image()
        self.album_art_image.set_size_request(60, 60)
        self.album_art_image.set_name("album-art")
        top_box.append(self.album_art_image)
        
        track_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        track_info_box.set_valign(Gtk.Align.CENTER)
        track_info_box.set_halign(Gtk.Align.START)
        track_info_box.set_hexpand(True)
        track_info_box.set_size_request(310, -1)
        
        self.track_title_label = Gtk.Label(label=self.track_title)
        self.track_title_label.set_name("track-title")
        self.track_title_label.set_halign(Gtk.Align.START)
        self.track_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.track_title_label.set_size_request(310, -1)
        self.track_title_label.set_xalign(0.0)
        self.track_title_label.set_max_width_chars(30)
        self.track_title_label.set_wrap(False)
        
        self.artist_name_label = Gtk.Label(label=self.artist_name)
        self.artist_name_label.set_name("artist-name")
        self.artist_name_label.set_halign(Gtk.Align.START)
        self.artist_name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_name_label.set_size_request(310, -1)
        self.artist_name_label.set_xalign(0.0)
        self.artist_name_label.set_max_width_chars(30)
        self.artist_name_label.set_wrap(False)
        
        track_info_box.append(self.track_title_label)
        track_info_box.append(self.artist_name_label)
        top_box.append(track_info_box)
        self.main_box.append(top_box)
        
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.progress_box.set_size_request(380, -1)
        
        self.current_time_label = Gtk.Label(label="0:00")
        self.current_time_label.set_name("time-label")
        self.current_time_label.set_size_request(55, -1)
        
        self.progress_bar = CustomProgressBar("music-progress-bar", initial_fraction=0.3, width=260, height=5)
        self.progress_bar.connect("value-changed", self.on_value_changed)
        self.progress_bar.set_valign(Gtk.Align.CENTER)
        self.progress_bar.set_vexpand(False)
        
        self.total_time_label = Gtk.Label(label="0:00")
        self.total_time_label.set_name("time-label")
        self.total_time_label.set_size_request(55, -1)
        
        self.progress_box.append(self.current_time_label)
        self.progress_box.append(self.progress_bar)
        self.progress_box.append(self.total_time_label)
        self.progress_box.set_halign(Gtk.Align.CENTER)
        self.main_box.append(self.progress_box)
        
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_margin_top(5)
        
        # Previous control
        self.previous_box = Gtk.Box()
        self.previous_box.set_name("control-box")
        self.previous_box.set_size_request(40, 40)
        previous_label = Gtk.Label()
        previous_label.set_markup(icons.prev)
        previous_label.add_css_class("control-icon")
        self.previous_box.append(previous_label)
        previous_gesture = Gtk.GestureClick()
        previous_gesture.connect("pressed", self.on_previous_clicked)
        self.previous_box.add_controller(previous_gesture)
        
        # Play/Pause control
        self.play_pause_box = Gtk.Box()
        self.play_pause_box.set_name("play-pause-box")
        self.play_pause_box.set_size_request(40, 40)
        self.play_pause_label = Gtk.Label()
        self.play_pause_label.set_markup(icons.play)
        self.play_pause_label.add_css_class("control-icon")
        self.play_pause_box.append(self.play_pause_label)
        play_pause_gesture = Gtk.GestureClick()
        play_pause_gesture.connect("pressed", self.on_play_pause_clicked)
        self.play_pause_box.add_controller(play_pause_gesture)
        
        # Next control
        self.next_box = Gtk.Box()
        self.next_box.set_name("control-box")
        self.next_box.set_size_request(40, 40)
        next_label = Gtk.Label()
        next_label.set_markup(icons.next)
        self.next_box.append(next_label)
        next_label.add_css_class("control-icon")
        next_gesture = Gtk.GestureClick()
        next_gesture.connect("pressed", self.on_next_clicked)
        self.next_box.add_controller(next_gesture)
        
        controls_box.append(self.previous_box)
        controls_box.append(self.play_pause_box)
        controls_box.append(self.next_box)
        self.main_box.append(controls_box)
        
        self.stack.add_titled(self.main_box, "player", "Player")
        
        self.placeholder = Gtk.Label(label="No media players found")
        self.placeholder.set_margin_top(20)
        self.placeholder.set_margin_bottom(20)
        self.stack.add_titled(self.placeholder, "placeholder", "No Players")
        
        for player in self.manager.players:
            self.add_player(player)
        
        if not self.players:
            self.stack.set_visible_child_name("placeholder")

    def get_player_icon(self, player_name):
        """Return a tuple of (active_icon, inactive_icon) for the player."""
        name = player_name.lower()
        if "spotify" in name:
            return (icons.spotify, icons.spotify_off)
        elif "firefox" in name:
            return (icons.firefox, icons.firefox_off)
        else:
            return (icons.disc, icons.disc_off)

    def create_switcher_button(self, player_name):
        """Create a button with a centered Tabler icon using Pango markup, starting with inactive icon."""
        active_icon, inactive_icon = self.get_player_icon(player_name)
        markup = f'<span font-family="Tabler Icons" font-weight="normal" font-size="16pt">{inactive_icon}</span>'
        label = Gtk.Label()
        label.set_markup(markup)
        label.set_halign(Gtk.Align.CENTER)
        label.set_valign(Gtk.Align.CENTER)
        
        button = Gtk.Button()
        button.set_child(label)
        button.set_size_request(32, 32)
        button.get_style_context().add_class("player-icon")
        button.connect("clicked", self.on_switcher_clicked, player_name)
        
        return button, label, active_icon, inactive_icon

    def on_switcher_clicked(self, button, player_name):
        if player_name in self.players:
            self.set_active_player(player_name)

    def on_player_appeared(self, manager, player):
        self.add_player(player)

    def on_player_vanished(self, manager, player_name):
        if player_name in self.players:
            self.switcher_box.remove(self.players[player_name]['switcher_button'])
            del self.players[player_name]
            if player_name == self.active_player_name:
                if self.players:
                    first_player_name = next(iter(self.players))
                    self.set_active_player(first_player_name)
                else:
                    self.active_player = None
                    self.active_player_name = None
                    self.stack.set_visible_child_name("placeholder")
                    self.switcher_box.hide()

    def add_player(self, player):
        mpris_player = MprisPlayer(player)
        player_name = mpris_player.player_name
        
        switcher_button, label, active_icon, inactive_icon = self.create_switcher_button(player_name)
        self.players[player_name] = {
            'mpris_player': mpris_player,
            'switcher_button': switcher_button,
            'label': label,
            'active_icon': active_icon,
            'inactive_icon': inactive_icon
        }
        self.switcher_box.append(switcher_button)
        
        mpris_player.connect("changed", self.on_player_changed, player_name)
        mpris_player.connect("progress-updated", self.on_progress_updated, player_name)
        
        if len(self.players) == 1:
            self.switcher_box.show()
            self.set_active_player(player_name)
            self.stack.set_visible_child_name("player")
        elif self.active_player_name:
            self.set_active_player(self.active_player_name)

    def set_active_player(self, player_name):
        self.active_player_name = player_name
        self.active_player = self.players[player_name]['mpris_player']
        self.update_player_data()
        self.update_ui()
        for p_name, p_data in self.players.items():
            label = p_data['label']
            icon = p_data['active_icon'] if p_name == self.active_player_name else p_data['inactive_icon']
            markup = f'<span font-family="Tabler Icons" font-weight="normal" font-size="16pt">{icon}</span>'
            label.set_markup(markup)

    def update_player_data(self):
        if not self.active_player:
            self.track_title = "No Track"
            self.artist_name = "Unknown Artist"
            self.track_image = None
            self.track_length = 0
            self.current_position = 0
            self.playback_status = "stopped"
            self.can_go_previous = False
            self.can_go_next = False
            self.can_pause = False
        else:
            self.track_title = self.active_player.title or "No Track"
            self.artist_name = self.active_player.artist or "Unknown Artist"
            self.track_image = self.active_player.arturl
            self.track_length = self.active_player.length or 0
            self.current_position = self.active_player.position or 0
            self.playback_status = self.active_player.playback_status
            self.can_go_previous = self.active_player.can_go_previous
            self.can_go_next = self.active_player.can_go_next
            self.can_pause = self.active_player.can_pause

    def adjust_progress_bar_width(self, show_hours):
        if show_hours:
            time_label_width = 75
            self.current_time_label.set_size_request(time_label_width, -1)
            self.total_time_label.set_size_request(time_label_width, -1)
            progress_bar_width = 380 - (time_label_width * 2) - 10
        else:
            time_label_width = 55
            self.current_time_label.set_size_request(time_label_width, -1)
            self.total_time_label.set_size_request(time_label_width, -1)
            progress_bar_width = 380 - (time_label_width * 2) - 10
        self.progress_bar.set_size_request(progress_bar_width, 5)

    def update_ui(self):
        self.track_title_label.set_label(self.track_title)
        self.artist_name_label.set_label(self.artist_name)
        
        if self.playback_status == "playing":
            self.play_pause_label.set_markup(icons.pause)
        else:
            self.play_pause_label.set_markup(icons.play)
        
        if self.can_go_previous:
            self.previous_box.get_style_context().remove_class("disabled")
        else:
            self.previous_box.get_style_context().add_class("disabled")
        
        if self.can_go_next:
            self.next_box.get_style_context().remove_class("disabled")
        else:
            self.next_box.get_style_context().add_class("disabled")
        
        if self.can_pause:
            self.play_pause_box.get_style_context().remove_class("disabled")
        else:
            self.play_pause_box.get_style_context().add_class("disabled")
        
        if self.track_image:
            self.update_album_art(self.album_art_image, self.track_image)
        else:
            self.album_art_image.clear()
        
        show_hours = self.track_length >= 3600 * 1000000
        self.adjust_progress_bar_width(show_hours)
        
        self.current_time_label.set_label(self.format_time(self.current_position, show_hours))
        self.total_time_label.set_label(self.format_time(self.track_length, show_hours))
        
        if self.track_length > 0:
            progress = self.current_position / self.track_length
            self.progress_bar.set_fraction(progress)
        else:
            self.progress_bar.set_fraction(0)

    def on_player_changed(self, mpris_player, player_name):
        if player_name == self.active_player_name:
            self.update_player_data()
            self.update_ui()

    def on_progress_updated(self, mpris_player, pos_usec, len_usec, player_name):
        if player_name == self.active_player_name:
            if hasattr(self, '_is_seeking') and self._is_seeking:
                return
            self.current_position = pos_usec
            self.track_length = len_usec
            show_hours = self.track_length >= 3600 * 1000000
            self.adjust_progress_bar_width(show_hours)
            self.current_time_label.set_label(self.format_time(self.current_position, show_hours))
            self.total_time_label.set_label(self.format_time(self.track_length, show_hours))
            if self.track_length > 0:
                self.progress_bar.set_fraction(self.current_position / self.track_length)

    def on_previous_clicked(self, gesture, n_press, x, y):
        if self.active_player and self.can_go_previous:
            self.active_player.previous()

    def on_play_pause_clicked(self, gesture, n_press, x, y):
        if self.active_player and self.can_pause:
            self.active_player.play_pause()

    def on_next_clicked(self, gesture, n_press, x, y):
        if self.active_player and self.can_go_next:
            self.active_player.next()

    def update_album_art(self, image_widget, url):
        def load_art():
            try:
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    urllib.request.urlretrieve(url, temp_file.name)
                    def set_image():
                        try:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                temp_file.name, 60, 60, True
                            )
                            image_widget.set_from_pixbuf(pixbuf)
                        except Exception as e:
                            print(f"Error setting album art: {e}")
                            image_widget.clear()
                        finally:
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                        return False
                    GLib.idle_add(set_image)
            except Exception as e:
                print(f"Error loading album art: {e}")
                GLib.idle_add(lambda: image_widget.clear())
        
        import threading
        threading.Thread(target=load_art, daemon=True).start()

    def format_time(self, microseconds, show_hours=False):
        if not microseconds or microseconds < 0:
            return "0:00"
        seconds = int(microseconds // 1000000)
        minutes = seconds // 60
        seconds = seconds % 60
        if show_hours:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def on_value_changed(self, progress_bar, fraction):
        if not self.active_player or not self.active_player.can_seek:
            print(f"Cannot seek - no active player or seeking not supported")
            return
        
        if self.track_length <= 0:
            print(f"Cannot seek - no valid track length")
            return
        
        self._is_seeking = True
        
        new_position = int(fraction * self.track_length)
        self.current_position = new_position
        
        show_hours = self.track_length >= 3600 * 1000000
        self.current_time_label.set_label(self.format_time(self.current_position, show_hours))
        
        if hasattr(self, '_seek_timeout_id') and self._seek_timeout_id:
            GLib.source_remove(self._seek_timeout_id)
        if hasattr(self, '_seek_end_timeout_id') and self._seek_end_timeout_id:
            GLib.source_remove(self._seek_end_timeout_id)
        
        self._seek_timeout_id = GLib.timeout_add(150, self._perform_seek, new_position)
        self._seek_end_timeout_id = GLib.timeout_add(500, self._end_seeking)

    def _perform_seek(self, position):
        try:
            if self.active_player and self.active_player.can_seek:
                self.active_player.position = position
                show_hours = self.track_length >= 3600 * 1000000
                print(f"Seeked to position: {self.format_time(position, show_hours)}")
        except Exception as e:
            print(f"Error seeking to position {position}: {e}")
        self._seek_timeout_id = None
        return False

    def _end_seeking(self):
        self._is_seeking = False
        self._seek_end_timeout_id = None
        return False