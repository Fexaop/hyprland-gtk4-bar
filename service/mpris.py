import contextlib
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Playerctl', '2.0')
from gi.repository import Gtk, GObject, Playerctl, GLib, Gdk # Add Gdk
from loguru import logger
import os # Add os

# Updated MprisPlayer class
class MprisPlayer(GObject.Object):
    __gsignals__ = {
        "exit": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "progress-updated": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_INT64, GObject.TYPE_INT64)), # pos_usec, len_usec
    }

    def __init__(self, player: Playerctl.Player, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        self._signal_connectors = {}
        self._player = player
        self._progress_timer_id = None  # Store timer ID

        for sn in ["playback-status", "loop-status", "shuffle", "volume", "seeked"]:
            self._signal_connectors[sn] = self._player.connect(
                sn, lambda *args, sn=sn: self.notifier(sn, args)
            )
        self._signal_connectors["exit"] = self._player.connect("exit", self.on_player_exit)
        self._signal_connectors["metadata"] = self._player.connect(
            "metadata", lambda *args: self.update_status()
        )
        GLib.idle_add(lambda *args: self.update_status_once())
        # Start the progress update timer
        self._progress_timer_id = GLib.timeout_add(500, self._update_progress_tick)


    def _update_progress_tick(self):
        """Called periodically to update and emit progress."""
        if not self._player:
            return False # Stop timer if player is gone

        try:
            pos_usec = self._player.get_position()
        except Exception:
            pos_usec = 0

        len_usec = self.length or 0 # Use the existing length property

        # Emit the signal
        self.emit("progress-updated", pos_usec, len_usec)

        # Keep the timer running only if player is playing
        # return self.playback_status == "playing" # Option 1: Only update when playing
        return True # Option 2: Always update to show paused state correctly

    @property
    def player(self) -> Playerctl.Player:
        return self._player

    @property
    def player_name(self) -> str:
        return self.player.get_property("player-name")

    @property
    def position(self) -> int:
        return self.player.get_property("position")

    @position.setter
    def position(self, new_pos: int):
        self.player.set_position(new_pos)

    @property
    def metadata(self) -> dict:
        return self.player.get_property("metadata")

    @property
    def arturl(self) -> str | None:
        if "mpris:artUrl" in self.metadata.keys():
            return self.metadata["mpris:artUrl"]
        return None

    @property
    def length(self) -> int | None:
        if "mpris:length" in self.metadata.keys():
            return self.metadata["mpris:length"]  # Returns microseconds
        return None

    @property
    def length_str(self) -> str:
        """Convert length from microseconds to a human-readable string."""
        if self.length is not None:
            seconds = self.length // 1000000
            minutes, seconds = divmod(seconds, 60)
            return f"{minutes:02d}:{seconds:02d}"
        return "N/A" # Keep this for direct access if needed elsewhere

    @property
    def artist(self) -> str:
        artist = self.player.get_artist()
        if isinstance(artist, (list, tuple)):
            return ", ".join(artist)
        return artist

    @property
    def album(self) -> str:
        return self.player.get_album()

    @property
    def title(self) -> str:
        try:
            return self.player.get_title()
        except AttributeError:
            return ""

    @property
    def shuffle(self) -> bool:
        return self.player.get_property("shuffle")

    @shuffle.setter
    def shuffle(self, do_shuffle: bool):
        self.notifier("shuffle")
        self.player.set_shuffle(do_shuffle)

    @property
    def playback_status(self) -> str:
        return {
            Playerctl.PlaybackStatus.PAUSED: "paused",
            Playerctl.PlaybackStatus.PLAYING: "playing",
            Playerctl.PlaybackStatus.STOPPED: "stopped",
        }.get(self.player.get_property("playback_status"), "unknown")

    @property
    def loop_status(self) -> str:
        return {
            Playerctl.LoopStatus.NONE: "none",
            Playerctl.LoopStatus.TRACK: "track",
            Playerctl.LoopStatus.PLAYLIST: "playlist",
        }.get(self.player.get_property("loop_status"), "unknown")

    @loop_status.setter
    def loop_status(self, status: str):
        loop_status = {
            "none": Playerctl.LoopStatus.NONE,
            "track": Playerctl.LoopStatus.TRACK,
            "playlist": Playerctl.LoopStatus.PLAYLIST,
        }.get(status)
        if loop_status:
            self._player.set_loop_status(loop_status)

    @property
    def can_go_next(self) -> bool:
        return self.player.get_property("can_go_next")

    @property
    def can_go_previous(self) -> bool:
        return self.player.get_property("can_go_previous")

    @property
    def can_seek(self) -> bool:
        return self.player.get_property("can_seek")

    @property
    def can_pause(self) -> bool:
        return self.player.get_property("can_pause")

    @property
    def can_shuffle(self) -> bool:
        try:
            self.player.set_shuffle(self.player.get_property("shuffle"))
            return True
        except Exception:
            return False

    @property
    def can_loop(self) -> bool:
        try:
            self.player.set_loop_status(self.player.get_property("loop_status"))
            return True
        except Exception:
            return False

    def update_status(self):
        def notify_property(prop):
            if getattr(self, prop, None) is not None:
                self.notifier(prop)
        for prop in ["metadata", "title", "artist", "arturl", "length"]:
            GLib.idle_add(lambda p=prop: (notify_property(p), False))
        for prop in ["can-seek", "can-pause", "can-shuffle", "can-go-next", "can-go-previous"]:
            GLib.idle_add(lambda p=prop: (self.notifier(p), False))

    def update_status_once(self):
        def notify_all():
            for prop in list(self.__dict__.keys()):
                self.notifier(prop)
            return False
        GLib.idle_add(notify_all, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def notifier(self, name: str, args=None):
        """Emit the 'changed' signal without notifying undefined properties."""
        def notify_and_emit():
            self.emit("changed")
            return False
        GLib.idle_add(notify_and_emit, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def on_player_exit(self, player):
        # Stop the progress timer
        if self._progress_timer_id:
            GLib.source_remove(self._progress_timer_id)
            self._progress_timer_id = None

        for id in list(self._signal_connectors.values()):
            with contextlib.suppress(Exception):
                self._player.disconnect(id)
        del self._signal_connectors
        GLib.idle_add(lambda: (self.emit("exit", True), False))
        del self._player

    def toggle_shuffle(self):
        if self.can_shuffle:
            GLib.idle_add(lambda: (setattr(self, 'shuffle', not self.shuffle), False))

    def play_pause(self):
        if self.can_pause:
            GLib.idle_add(lambda: (self._player.play_pause(), False))

    def next(self):
        if self.can_go_next:
            GLib.idle_add(lambda: (self._player.next(), False))

    def previous(self):
        if self.can_go_previous:
            GLib.idle_add(lambda: (self._player.previous(), False))

# MprisPlayerManager class (unchanged)
class MprisPlayerManager(GObject.Object):
    __gsignals__ = {
        "player-appeared": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "player-vanished": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        self._manager = Playerctl.PlayerManager.new()
        self._manager.connect("name-appeared", self.on_name_appeared)
        self._manager.connect("name-vanished", self.on_name_vanished)
        self.add_players()

    def on_name_appeared(self, manager, player_name: Playerctl.PlayerName):
        logger.info(f"[MprisPlayer] {player_name.name} appeared")
        new_player = Playerctl.Player.new_from_name(player_name)
        manager.manage_player(new_player)
        self.emit("player-appeared", new_player)

    def on_name_vanished(self, manager, player_name: Playerctl.PlayerName):
        logger.info(f"[MprisPlayer] {player_name.name} vanished")
        self.emit("player-vanished", player_name.name)

    def add_players(self):
        for player in self._manager.get_property("player-names"):
            self._manager.manage_player(Playerctl.Player.new_from_name(player))

    @property
    def players(self):
        return self._manager.get_property("players")

