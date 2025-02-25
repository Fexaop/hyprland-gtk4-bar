from gi.repository import Gtk, GLib, GdkPixbuf
import dbus
import dbus.mainloop.glib
import urllib.request
import os

class MusicPlayer(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.set_name("music-player")
        
        # Initialize DBus for playerctl
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        self.player = None
        self.connect_to_spotify()

        # Album art and track info container
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_box.set_margin_start(10)
        top_box.set_margin_end(10)
        top_box.set_margin_top(10)
        
        # Album art
        self.album_art = Gtk.Image()
        self.album_art.set_size_request(60, 60)
        self.album_art.set_name("album-art")
        top_box.append(self.album_art)
        
        # Track info
        track_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        track_info.set_valign(Gtk.Align.CENTER)
        
        self.track_name = Gtk.Label(label="Not Playing")
        self.track_name.set_name("track-name")
        self.track_name.set_halign(Gtk.Align.START)
        
        self.artist_name = Gtk.Label(label="")
        self.artist_name.set_name("artist-name")
        self.artist_name.set_halign(Gtk.Align.START)
        
        track_info.append(self.track_name)
        track_info.append(self.artist_name)
        top_box.append(track_info)
        
        self.append(top_box)
        
        # Progress slider with Adjustment
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        progress_box.set_margin_start(10)
        progress_box.set_margin_end(10)
        
        self.current_time = Gtk.Label(label="0:00")
        self.current_time.set_name("time-label")
        
        self.adjustment = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10, page_size=0)
        self.progress_scale = Gtk.Scale(adjustment=self.adjustment)
        self.progress_scale.set_draw_value(False)
        self.progress_scale.set_hexpand(True)
        self.progress_scale.set_name("progress-slider")
        
        self.total_time = Gtk.Label(label="0:00")
        self.total_time.set_name("time-label")
        
        progress_box.append(self.current_time)
        progress_box.append(self.progress_scale)
        progress_box.append(self.total_time)
        
        self.append(progress_box)
        
        # Playback controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_margin_top(5)
        controls_box.set_margin_bottom(10)
        
        previous_button = Gtk.Button(label="⏮")
        previous_button.set_name("control-button")
        
        self.play_button = Gtk.Button(label="▶")
        self.play_button.set_name("play-button")
        
        next_button = Gtk.Button(label="⏭")
        next_button.set_name("control-button")
        
        controls_box.append(previous_button)
        controls_box.append(self.play_button)
        controls_box.append(next_button)
        
        self.append(controls_box)
        
        # Connect signals
        self.play_button.connect("clicked", self.toggle_play)
        previous_button.connect("clicked", self.previous_track)
        next_button.connect("clicked", self.next_track)
        self.progress_scale.connect("change-value", self.on_slider_change)
        
        # Initial state
        self.is_playing = False
        self.is_seeking = False
        self.update_metadata()
        GLib.timeout_add(1000, self.update_progress)  # Update every second

    def connect_to_spotify(self):
        try:
            self.player = self.bus.get_object(
                "org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2"
            )
            self.player_iface = dbus.Interface(
                self.player,
                "org.mpris.MediaPlayer2.Player"
            )
            self.properties = dbus.Interface(
                self.player,
                "org.freedesktop.DBus.Properties"
            )
            self.properties.connect_to_signal("PropertiesChanged", self.on_properties_changed)
        except dbus.exceptions.DBusException:
            print("Spotify not found. Please start Spotify.")
            self.player = None

    def toggle_play(self, button):
        if self.player:
            if self.is_playing:
                self.player_iface.Pause()
            else:
                self.player_iface.Play()
            self.update_play_button()

    def previous_track(self, button):
        if self.player:
            self.player_iface.Previous()

    def next_track(self, button):
        if self.player:
            self.player_iface.Next()

    def on_slider_change(self, scale, scroll, value):
        if self.player:
            self.is_seeking = True
            position = int(value * 1000000)  # Convert to microseconds
            track_id = self.properties.Get("org.mpris.MediaPlayer2.Player", "Metadata").get("mpris:trackid", "")
            self.player_iface.SetPosition(track_id, position)
            self.is_seeking = False
            return True  # Prevent default handling

    def update_play_button(self):
        if self.player:
            status = self.properties.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus")
            self.is_playing = (status == "Playing")
            self.play_button.set_label("⏸" if self.is_playing else "▶")

    def update_metadata(self):
        if self.player:
            try:
                metadata = self.properties.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                track_name = str(metadata.get("xesam:title", "Not Playing"))
                artist_name = ", ".join(metadata.get("xesam:artist", [""]))
                duration = int(metadata.get("mpris:length", 0)) / 1000000  # Convert to seconds
                
                self.track_name.set_label(track_name)
                self.artist_name.set_label(artist_name)
                self.total_time.set_label(self.format_time(int(duration)))
                self.adjustment.set_upper(duration if duration > 0 else 100)

                # Update album art
                art_url = metadata.get("mpris:artUrl", "")
                if art_url:
                    self.update_album_art(art_url)
                else:
                    self.album_art.clear()
            except Exception as e:
                print(f"Error updating metadata: {e}")

    def update_album_art(self, url):
        try:
            temp_file = "/tmp/spotify_album_art.jpg"
            urllib.request.urlretrieve(url, temp_file)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(temp_file, 60, 60, True)
            self.album_art.set_from_pixbuf(pixbuf)
            os.remove(temp_file)
        except Exception as e:
            print(f"Error loading album art: {e}")
            self.album_art.clear()

    def update_progress(self):
        if self.player and self.is_playing and not self.is_seeking:
            try:
                position = self.properties.Get("org.mpris.MediaPlayer2.Player", "Position") / 1000000  # Convert to seconds
                self.current_time.set_label(self.format_time(int(position)))
                self.adjustment.set_value(position)
            except Exception as e:
                print(f"Error updating progress: {e}")
        return True  # Keep the timeout running

    def on_properties_changed(self, interface, changed, invalidated):
        if "PlaybackStatus" in changed:
            self.update_play_button()
        if "Metadata" in changed:
            self.update_metadata()

    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

# Example usage
if __name__ == "__main__":
    win = Gtk.Window()
    win.set_title("Spotify Player")
    win.set_default_size(300, 150)
    
    player = MusicPlayer()
    win.set_child(player)
    
    win.connect("destroy", Gtk.main_quit)
    win.show()
    Gtk.main()