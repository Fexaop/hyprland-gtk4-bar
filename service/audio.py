import gi
from loguru import logger
from typing import Literal
import sys # For logger setup

gi.require_version("Gtk", "4.0") # Though not directly used, good for GObject apps
gi.require_version("Cvc", "1.0")

from gi.repository import GObject, Gio, GLib # Added GLib for MainLoop

# --- Logger Setup ---
logger.remove() # Remove default handler
logger.add(sys.stderr, level="INFO") # Add a new handler, INFO level is usually good for this

# --- Helper functions (previously from fabric.utils) ---
def snake_case_to_kebab_case(s: str) -> str:
    return s.replace('_', '-')

def get_enum_member_name(enum_value, default: str = "unknown") -> str:
    if hasattr(enum_value, 'value_nick') and isinstance(enum_value.value_nick, str):
        return enum_value.value_nick
    if hasattr(enum_value, 'name') and isinstance(enum_value.name, str):
        return enum_value.name.lower().replace('_', '-')
    return str(enum_value) if enum_value is not None else default


class CvcImportError(ImportError):
    def __init__(self, *args):
        super().__init__(
            "Cvc is not installed, please install it first, you can use automated installer in the git repository",
            *args,
        )

try:
    from gi.repository import Cvc
except ImportError:
    logger.error("Failed to import Cvc. Please ensure it's installed correctly.")
    raise CvcImportError()


class AudioStream(GObject.Object):
    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'closed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(
        self,
        stream: Cvc.MixerStream,
        control: Cvc.MixerControl,
        parent: "Audio",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._old_vol = 0.0
        self._stream = stream
        self._control = control
        self._parent = parent

        cvc_props_to_audiostream_props = {
            "application-id": "application_id",
            "description": "description",
            "icon-name": "icon_name",
            "is-muted": "muted",
            "volume": "volume",
            "state": "state",
            "id": "id",
        }

        for cvc_prop, audiostream_prop_py_name in cvc_props_to_audiostream_props.items():
            self._stream.connect(
                f"notify::{cvc_prop}",
                lambda _obj, _pspec, prop_name=audiostream_prop_py_name: self._on_cvc_stream_property_changed(prop_name)
            )

    def _on_cvc_stream_property_changed(self, py_property_name: str):
        self.notify(py_property_name)
        self.emit("changed")

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def icon_name(self) -> str:
        return self._stream.get_icon_name()

    @GObject.Property(type=int, flags=GObject.ParamFlags.READABLE)
    def id(self) -> int:
        return self._stream.get_id()

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def name(self) -> str:
        return self._stream.get_name()

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def description(self) -> str:
        return self._stream.get_description()

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def application_id(self) -> str:
        return self._stream.get_application_id()

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def state(self) -> str:
        return snake_case_to_kebab_case(
            get_enum_member_name(self._stream.get_state(), default="unknown")
        )

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def control_state(self) -> str:
        return snake_case_to_kebab_case(
            get_enum_member_name(self._control.get_state(), default="unknown")
        )

    @GObject.Property(type=Cvc.MixerStream, flags=GObject.ParamFlags.READABLE)
    def cvc_stream(self) -> Cvc.MixerStream:
        return self._stream

    @GObject.Property(type=Cvc.MixerStream, flags=GObject.ParamFlags.READABLE)
    def stream(self) -> Cvc.MixerStream:
        return self._stream

    @GObject.Property(type=float, flags=GObject.ParamFlags.READWRITE)
    def volume(self) -> float:
        vol_max_norm = self._control.get_vol_max_norm()
        if vol_max_norm == 0:
            return 0.0
        return float((self._stream.get_volume() / vol_max_norm) * 100)

    @volume.setter
    def volume(self, value: float):
        current_percentage_vol = self.volume
        if abs(current_percentage_vol - value) < 0.01 :
             return

        value = max(0.0, value)
        value = min(value, float(self._parent.max_volume))

        self._old_vol = self._stream.get_volume()
        new_cvc_vol = int((value * self._control.get_vol_max_norm()) / 100)

        self._stream.set_volume(new_cvc_vol)
        self._stream.push_volume()
        self.notify("volume")
        self.emit("changed")

    @GObject.Property(type=bool, default=False, nick="is-muted", flags=GObject.ParamFlags.READWRITE)
    def muted(self) -> bool:
        return self._stream.get_is_muted()

    @muted.setter
    def muted(self, value: bool):
        if self._stream.get_is_muted() != value:
            self._stream.set_is_muted(value)
            self._stream.change_is_muted(value)
            self.notify("muted")
            self.emit("changed")

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def type(self) -> str:
        return Audio.get_stream_type(self.stream, default="unknown") # type: ignore

    def close(self):
        logger.debug(f"AudioStream {self.id} ({self.name}) closed signal emitted.")
        self.emit("closed")


class Audio(GObject.Object):
    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'speaker-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'microphone-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'stream-added': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'stream-removed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(
        self,
        max_volume: int = 100,
        controller_name: str = "PyAudioServiceDemo", # Changed name for clarity
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._control = Cvc.MixerControl(name=controller_name)
        self._internal_max_volume = max_volume

        self._streams: dict[int, AudioStream] = {}
        self._stream_connectors: dict[int, int] = {}

        self._internal_speaker: AudioStream | None = None
        self._speaker_connection: int | None = None

        self._internal_microphone: AudioStream | None = None
        self._microphone_connection: int | None = None

        self._control.connect("stream-added", self.on_stream_added)
        self._control.connect("stream-removed", self.on_stream_removed)
        self._control.connect("default-sink-changed", lambda _c, id_num: self.on_default_stream_changed(id_num, "speaker"))
        self._control.connect("default-source-changed", lambda _c, id_num: self.on_default_stream_changed(id_num, "microphone"))
        self._control.connect("notify::state", lambda _c, _p: self.notify("state"))

        logger.info(f"Audio service '{controller_name}' initializing...")
        self._control.open()
        logger.info("Audio service control opened.")


    @GObject.Property(type=AudioStream, flags=GObject.ParamFlags.READABLE)
    def speaker(self) -> AudioStream | None:
        return self._internal_speaker

    @GObject.Property(type=GObject.TYPE_PYOBJECT, flags=GObject.ParamFlags.READABLE)
    def speakers(self) -> list[AudioStream]:
        return self.do_list_stream_type(Cvc.MixerSink)

    @GObject.Property(type=AudioStream, flags=GObject.ParamFlags.READABLE)
    def microphone(self) -> AudioStream | None:
        return self._internal_microphone

    @GObject.Property(type=GObject.TYPE_PYOBJECT, flags=GObject.ParamFlags.READABLE)
    def microphones(self) -> list[AudioStream]:
        return self.do_list_stream_type(Cvc.MixerSource)

    @GObject.Property(type=GObject.TYPE_PYOBJECT, flags=GObject.ParamFlags.READABLE)
    def applications(self) -> list[AudioStream]:
        return self.do_list_stream_type(Cvc.MixerSinkInput)

    @GObject.Property(type=GObject.TYPE_PYOBJECT, flags=GObject.ParamFlags.READABLE)
    def recorders(self) -> list[AudioStream]:
        return self.do_list_stream_type(Cvc.MixerSourceOutput)

    @GObject.Property(type=int, default=100, minimum=0, maximum=200, flags=GObject.ParamFlags.READWRITE)
    def max_volume(self) -> int:
        return self._internal_max_volume

    @max_volume.setter
    def max_volume(self, value: int):
        value = max(0, value)
        if self._internal_max_volume != value:
            logger.info(f"Max volume changed from {self._internal_max_volume} to {value}")
            self._internal_max_volume = value
            self.notify("max_volume")
            self.emit("changed")


    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def state(self) -> str:
        return snake_case_to_kebab_case(
            get_enum_member_name(self._control.get_state(), default="unknown")
        )

    def do_list_stream_type(
        self,
        stream_type_input: Literal[
            "source", "source-output", "sink", "sink-input"
        ] | type[Cvc.MixerSource] | type[Cvc.MixerSourceOutput] | type[Cvc.MixerSink] | type[Cvc.MixerSinkInput] | None = None,
    ) -> list[AudioStream]:
        if not stream_type_input:
            return list(self._streams.values())

        actual_cvc_type: type | None = None
        if isinstance(stream_type_input, str):
            actual_cvc_type = {
                "source": Cvc.MixerSource,
                "source-output": Cvc.MixerSourceOutput,
                "sink": Cvc.MixerSink,
                "sink-input": Cvc.MixerSinkInput,
            }.get(stream_type_input)
        elif isinstance(stream_type_input, type) and issubclass(stream_type_input, Cvc.MixerStream): # type: ignore
             actual_cvc_type = stream_type_input


        rlist = []
        if actual_cvc_type:
            for strm_obj in self._streams.values():
                if isinstance(strm_obj.stream, actual_cvc_type):
                    rlist.append(strm_obj)
        return rlist

    def on_default_stream_changed(self, stream_id: int, stream_kind: Literal["speaker", "microphone"]):
        logger.info(f"[AudioService] Default {stream_kind} changed to ID: {stream_id}")

        old_stream_attr_name = f"_internal_{stream_kind}"
        old_conn_attr_name = f"_{stream_kind}_connection"

        old_strm_instance: AudioStream | None = getattr(self, old_stream_attr_name, None)
        if old_strm_instance is not None:
            logger.debug(f"Disconnecting from old default {stream_kind} stream: {old_strm_instance.name}")
            hndlr_id: int | None = getattr(self, old_conn_attr_name, None)
            if hndlr_id is not None:
                try:
                    old_strm_instance.disconnect(hndlr_id)
                except TypeError:
                    logger.warning(f"Could not disconnect handler {hndlr_id} for old {stream_kind}")
            setattr(self, old_conn_attr_name, None)

        new_strm_instance = self._streams.get(stream_id)
        if not new_strm_instance:
            logger.warning(f"Default {stream_kind} ID {stream_id} not found in known streams.")
            if getattr(self, old_stream_attr_name) is not None:
                setattr(self, old_stream_attr_name, None)
                self.notify(stream_kind)
                self.emit(f"{stream_kind}-changed")
                self.emit("changed")
            return

        logger.info(f"Setting new default {stream_kind} to: {new_strm_instance.name} (ID: {new_strm_instance.id})")
        setattr(self, old_stream_attr_name, new_strm_instance)
        conn_id = new_strm_instance.connect("changed", lambda _s, sk=stream_kind: self._handle_default_stream_property_change(sk))
        setattr(self, old_conn_attr_name, conn_id)

        self.notify(stream_kind)
        self.emit(f"{stream_kind}-changed")
        self.emit("changed")

    def _handle_default_stream_property_change(self, stream_kind: Literal["speaker", "microphone"]):
        # This callback is for when a property *of the default stream itself* changes
        # e.g. default speaker's volume changed
        logger.debug(f"Default {stream_kind}'s properties changed.")
        self.emit(f"{stream_kind}-changed") # Emit that the speaker/mic (as a whole) changed
        self.emit("changed") # General change

    def on_stream_added(self, _control: Cvc.MixerControl, stream_id: int):
        stream = (
            self._control.lookup_stream_id(stream_id)
            or self._control.lookup_output_id(stream_id)
            or self._control.lookup_input_id(stream_id)
        )

        if not stream or stream_id in self._streams:
            if not stream or not Audio.get_stream_type(stream, None):
                 logger.debug(f"Stream added (id: {stream_id}) but it's of unknown type or already processed.")
                 return

        audio_stream = AudioStream(stream, self._control, self)
        self._streams[stream_id] = audio_stream
        connector_id = audio_stream.connect("changed", lambda _as, sid=stream_id: self._handle_individual_stream_change(sid))
        self._stream_connectors[stream_id] = connector_id

        logger.info(
            f"[AudioService] Stream Added: {audio_stream.name} (ID: {stream_id}, Type: {audio_stream.type})"
        )
        self.emit("stream-added", stream_id)
        self.do_notify_property_for_stream_list(stream)
        self.emit("changed")

    def _handle_individual_stream_change(self, stream_id: int):
        # Callback for when a specific AudioStream's 'changed' signal is emitted
        stream = self._streams.get(stream_id)
        if stream:
            logger.debug(f"Individual stream changed: {stream.name} (ID: {stream.id}, Volume: {stream.volume}%, Muted: {stream.muted})")
        self.emit("changed") # General change signal

    def on_stream_removed(self, _control: Cvc.MixerControl, stream_id: int):
        audio_stream = self._streams.pop(stream_id, None)
        if not audio_stream:
            logger.debug(f"Stream removed (id: {stream_id}) but it was not in our tracked list.")
            return

        connector_id = self._stream_connectors.pop(stream_id, None)
        if connector_id is not None:
            try:
                audio_stream.disconnect(connector_id)
            except TypeError:
                 logger.warning(f"Could not disconnect handler {connector_id} for removed stream {stream_id}")

        logger.info(
            f"[AudioService] Stream Removed: {audio_stream.name} (ID: {stream_id}, Type: {audio_stream.type})"
        )

        was_default_speaker = self._internal_speaker == audio_stream
        was_default_microphone = self._internal_microphone == audio_stream

        if was_default_speaker:
            logger.info(f"Removed stream was the default speaker. Clearing default speaker.")
            setattr(self, "_internal_speaker", None)
            if self._speaker_connection is not None:
                 try: audio_stream.disconnect(self._speaker_connection)
                 except TypeError: pass
                 self._speaker_connection = None
            self.notify("speaker")
            self.emit("speaker-changed")

        if was_default_microphone:
            logger.info(f"Removed stream was the default microphone. Clearing default microphone.")
            setattr(self, "_internal_microphone", None)
            if self._microphone_connection is not None:
                try: audio_stream.disconnect(self._microphone_connection)
                except TypeError: pass
                self._microphone_connection = None
            self.notify("microphone")
            self.emit("microphone-changed")

        self.emit("stream-removed", stream_id)
        self.do_notify_property_for_stream_list(audio_stream.stream)
        audio_stream.close()
        self.emit("changed")

    def do_notify_property_for_stream_list(self, cvc_stream: Cvc.MixerStream):
        stream_list_property_name = Audio.get_stream_type(cvc_stream)
        if stream_list_property_name:
            self.notify(stream_list_property_name)

    @staticmethod
    def get_stream_type(
        stream: Cvc.MixerStream,
        default: str | None = None,
    ) -> str | None:
        if isinstance(stream, Cvc.MixerSink):
            return "speakers"
        elif isinstance(stream, Cvc.MixerSinkInput):
            return "applications"
        elif isinstance(stream, Cvc.MixerSource):
            return "microphones"
        elif isinstance(stream, Cvc.MixerSourceOutput):
            return "recorders"
        return default

    def cleanup(self):
        logger.info("Cleaning up Audio service...")
        for stream_id, audio_stream in list(self._streams.items()): # Iterate over a copy
            logger.debug(f"Closing stream: {audio_stream.name} (ID: {stream_id})")
            # Disconnect handlers
            connector_id = self._stream_connectors.pop(stream_id, None)
            if connector_id is not None:
                try: audio_stream.disconnect(connector_id)
                except TypeError: pass
            
            if self._internal_speaker == audio_stream and self._speaker_connection is not None:
                try: audio_stream.disconnect(self._speaker_connection)
                except TypeError: pass
            if self._internal_microphone == audio_stream and self._microphone_connection is not None:
                try: audio_stream.disconnect(self._microphone_connection)
                except TypeError: pass
            
            audio_stream.close()
        self._streams.clear()
        self._stream_connectors.clear()

        if self._control:
            self._control.close() # Close the Cvc.MixerControl
            self._control = None # type: ignore
        logger.info("Audio service cleanup complete.")

# --- Main Application Logic ---
def main():
    loop = GLib.MainLoop()
    audio_service = None

    try:
        audio_service = Audio()

        # --- Connect to signals for demonstration ---
        def on_audio_changed(service):
            logger.info(f"--- Audio Service 'changed' signal ---")
            logger.info(f"Current State: {service.state}")
            logger.info(f"Max Volume: {service.max_volume}")

            if service.speaker:
                logger.info(f"Default Speaker: {service.speaker.name} (Vol: {service.speaker.volume:.0f}%, Muted: {service.speaker.muted})")
            else:
                logger.info("Default Speaker: None")

            if service.microphone:
                logger.info(f"Default Mic: {service.microphone.name} (Vol: {service.microphone.volume:.0f}%, Muted: {service.microphone.muted})")
            else:
                logger.info("Default Mic: None")

            logger.info(f"All Speakers: {[s.name for s in service.speakers]}")
            logger.info(f"All Microphones: {[s.name for s in service.microphones]}")
            logger.info(f"Applications: {[s.name for s in service.applications]}")
            logger.info(f"Recorders: {[s.name for s in service.recorders]}")
            logger.info(f"------------------------------------")


        def on_speaker_changed(service):
            if service.speaker:
                logger.info(f"*** Default Speaker Changed: {service.speaker.name} (ID: {service.speaker.id}) ***")
                # You can connect to the new speaker's 'changed' signal here if needed for fine-grained updates
            else:
                logger.info("*** Default Speaker Changed: None ***")

        def on_microphone_changed(service):
            if service.microphone:
                logger.info(f"*** Default Microphone Changed: {service.microphone.name} (ID: {service.microphone.id}) ***")
            else:
                logger.info("*** Default Microphone Changed: None ***")

        def on_stream_added(service, stream_id):
            stream = service._streams.get(stream_id) # Access internal for immediate info
            if stream:
                logger.info(f">>> Stream Added: {stream.name} (ID: {stream_id}, Type: {stream.type})")
            else:
                logger.info(f">>> Stream Added: ID {stream_id} (details pending)")


        def on_stream_removed(service, stream_id):
            # By the time this is called, stream is already removed from service._streams
            logger.info(f"<<< Stream Removed: ID {stream_id}")


        audio_service.connect("changed", on_audio_changed)
        audio_service.connect("speaker-changed", on_speaker_changed)
        audio_service.connect("microphone-changed", on_microphone_changed)
        audio_service.connect("stream-added", on_stream_added)
        audio_service.connect("stream-removed", on_stream_removed)

        # Initial print of state
        on_audio_changed(audio_service)

        # Example: Change max volume after a few seconds
        # GLib.timeout_add_seconds(5, lambda: audio_service.set_property("max-volume", 120))

        logger.info("Audio service running. Press Ctrl+C to exit.")
        loop.run()

    except KeyboardInterrupt:
        logger.info("Ctrl+C pressed. Exiting...")
    except CvcImportError:
        logger.critical("Cvc could not be imported. Application cannot run.")
        # No need to run loop or cleanup if Cvc is not there
        return
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if audio_service:
            audio_service.cleanup()
        if loop.is_running():
            loop.quit()
        logger.info("Main loop stopped.")

if __name__ == "__main__":
    main()