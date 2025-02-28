import gi
import base64
from enum import Enum
from loguru import logger
from dataclasses import dataclass
from typing import cast, Literal, TypedDict, Any, Optional, Dict, List, Callable
import os
# Add proper version requirements for all imported libraries
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gio, GLib, GdkPixbuf, Gdk, Gtk, GObject

# Constants
NOTIFICATIONS_BUS_NAME = "org.freedesktop.Notifications"
NOTIFICATIONS_BUS_PATH = "/org/freedesktop/Notifications"

def load_dbus_xml(path: str):
    """Helper function to load DBus XML files"""
    try:
        node_info = Gio.DBusNodeInfo.new_for_xml(open(path).read())
        return node_info
    except FileNotFoundError:
        logger.warning(f"DBus XML file not found: {path}")
        # Provide fallback XML inline for the notification interface
        xml = """
        <node>
            <interface name="org.freedesktop.Notifications">
                <method name="Notify">
                    <arg direction="in" type="s" name="app_name"/>
                    <arg direction="in" type="u" name="replaces_id"/>
                    <arg direction="in" type="s" name="app_icon"/>
                    <arg direction="in" type="s" name="summary"/>
                    <arg direction="in" type="s" name="body"/>
                    <arg direction="in" type="as" name="actions"/>
                    <arg direction="in" type="a{sv}" name="hints"/>
                    <arg direction="in" type="i" name="expire_timeout"/>
                    <arg direction="out" type="u" name="id"/>
                </method>
                <method name="CloseNotification">
                    <arg direction="in" type="u" name="id"/>
                </method>
                <method name="GetCapabilities">
                    <arg direction="out" type="as" name="capabilities"/>
                </method>
                <method name="GetServerInformation">
                    <arg direction="out" type="s" name="name"/>
                    <arg direction="out" type="s" name="vendor"/>
                    <arg direction="out" type="s" name="version"/>
                    <arg direction="out" type="s" name="spec_version"/>
                </method>
                <signal name="NotificationClosed">
                    <arg type="u" name="id"/>
                    <arg type="u" name="reason"/>
                </signal>
                <signal name="ActionInvoked">
                    <arg type="u" name="id"/>
                    <arg type="s" name="action_key"/>
                </signal>
            </interface>
        </node>
        """
        return Gio.DBusNodeInfo.new_for_xml(xml)

def get_enum_member(enum_class, value):
    """Helper function to get enum member from value"""
    if isinstance(value, enum_class):
        return value
    if isinstance(value, str):
        try:
            return enum_class[value.upper().replace("-", "_")]
        except KeyError:
            pass
    if isinstance(value, int):
        try:
            return next(m for m in enum_class if m.value == value)
        except StopIteration:
            pass
    return None

# Create the directory for DBus XML files if needed
def ensure_dbus_assets_directory():
    """Create the dbus_assets directory if it doesn't exist"""
    import os
    dbus_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dbus_assets")
    if not os.path.exists(dbus_dir):
        os.makedirs(dbus_dir)
        logger.info(f"Created directory: {dbus_dir}")
    
    # Create the notification XML file if it doesn't exist
    xml_file = os.path.join(dbus_dir, "org.freedesktop.Notifications.xml")
    if not os.path.exists(xml_file):
        with open(xml_file, "w") as f:
            f.write("""<node>
    <interface name="org.freedesktop.Notifications">
        <method name="Notify">
            <arg direction="in" type="s" name="app_name"/>
            <arg direction="in" type="u" name="replaces_id"/>
            <arg direction="in" type="s" name="app_icon"/>
            <arg direction="in" type="s" name="summary"/>
            <arg direction="in" type="s" name="body"/>
            <arg direction="in" type="as" name="actions"/>
            <arg direction="in" type="a{sv}" name="hints"/>
            <arg direction="in" type="i" name="expire_timeout"/>
            <arg direction="out" type="u" name="id"/>
        </method>
        <method name="CloseNotification">
            <arg direction="in" type="u" name="id"/>
        </method>
        <method name="GetCapabilities">
            <arg direction="out" type="as" name="capabilities"/>
        </method>
        <method name="GetServerInformation">
            <arg direction="out" type="s" name="name"/>
            <arg direction="out" type="s" name="vendor"/>
            <arg direction="out" type="s" name="version"/>
            <arg direction="out" type="s" name="spec_version"/>
        </method>
        <signal name="NotificationClosed">
            <arg type="u" name="id"/>
            <arg type="u" name="reason"/>
        </signal>
        <signal name="ActionInvoked">
            <arg type="u" name="id"/>
            <arg type="s" name="action_key"/>
        </signal>
    </interface>
</node>""")
        logger.info(f"Created DBus XML file: {xml_file}")
    return dbus_dir

# Create directories before loading the XML
ensure_dbus_assets_directory()

# Load DBus interface definitions
NOTIFICATIONS_BUS_IFACE_NODE = load_dbus_xml(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "dbus_assets/org.freedesktop.Notifications.xml")
)

class NotificationCloseReason(Enum):
    """A reason for which a notification was closed"""
    EXPIRED = 1
    DISMISSED_BY_USER = 2
    CLOSED_BY_APPLICATION = 3
    UNKNOWN = 4

class NotificationImagePixmap:
    """A class for storing image data associated with a notification"""

    @classmethod
    def deserialize(
        cls, data: tuple[int, int, int, bool, int, int, str]
    ) -> "NotificationImagePixmap":
        """Load image data from a serialized data tuple and return the newly created Pixmap object"""
        self = cls.__new__(cls)

        (
            self.width,
            self.height,
            self.rowstride,
            self.has_alpha,
            self.bits_per_sample,
            self.channels,
            self.byte_array,
        ) = data

        self.byte_array = GLib.Bytes.new(base64.b64decode(self.byte_array))

        self._pixbuf = None
        self._texture = None

        return self

    def __init__(self, raw_variant: GLib.Variant):
        # manually unpack children so we don't lock up the interpreter
        # trying to unpack hugely sized object recursively
        self.width = raw_variant.get_child_value(0).unpack()
        self.height = raw_variant.get_child_value(1).unpack()
        self.rowstride = raw_variant.get_child_value(2).unpack()
        self.has_alpha = raw_variant.get_child_value(3).unpack()
        self.bits_per_sample = raw_variant.get_child_value(4).unpack()
        self.channels = raw_variant.get_child_value(5).unpack()
        self.byte_array = raw_variant.get_child_value(6).get_data_as_bytes()

        self._pixbuf: Optional[GdkPixbuf.Pixbuf] = None
        self._texture: Optional[Gdk.Texture] = None

    def as_pixbuf(self) -> GdkPixbuf.Pixbuf:
        """Load a `Pixbuf` variant of this pixmap"""
        if self._pixbuf is not None:
            return self._pixbuf

        self._pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            self.byte_array,
            GdkPixbuf.Colorspace.RGB,
            self.has_alpha,
            self.bits_per_sample,
            self.width,
            self.height,
            self.rowstride,
        )
        return self._pixbuf
    
    def as_texture(self) -> Gdk.Texture:
        """Load a `Texture` variant of this pixmap for GTK4"""
        if self._texture is not None:
            return self._texture
            
        pixbuf = self.as_pixbuf()
        self._texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        return self._texture

    def serialize(self) -> tuple[int, int, int, bool, int, int, str]:
        """Serialize this pixmap image into a tuple for ease of carrying and saving"""
        return (
            self.width,
            self.height,
            self.rowstride,
            self.has_alpha,
            self.bits_per_sample,
            self.channels,
            base64.b64encode(cast(bytes, self.byte_array.unref_to_array())).decode(
                "ascii"
            ),
        )

@dataclass
class NotificationAction:
    """A notification action that can be invoked"""
    identifier: str
    label: str
    parent: "Notification"

    def invoke(self):
        "Invoke this action"
        return self.parent.invoke_action(self.identifier)

NotificationSerializedData = TypedDict(
    "NotificationSerializedData",
    {
        "id": int,
        "replaces-id": int,
        "app-name": str,
        "app-icon": str,
        "summary": str,
        "body": str,
        "timeout": int,
        "urgency": int,
        "actions": list[tuple[str, str]],
        "image-file": str | None,
        "image-pixmap": tuple[int, int, int, bool, int, int, str] | None,
    },
)

class Notification(GObject.Object):
    """The notification class holds all the data of a specific notification"""
    
    __gsignals__ = {
        'closed': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        'action-invoked': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self, id: int, raw_variant: GLib.Variant, **kwargs):
        GObject.Object.__init__(self)
        
        # Connect callbacks if provided
        self._on_closed_callback = kwargs.get('on_closed')
        self._on_action_invoked_callback = kwargs.get('on_action_invoked')
        
        # Connect signals to callbacks if provided
        if self._on_closed_callback:
            self.connect('closed', lambda _, reason: self._on_closed_callback(self, reason))
        if self._on_action_invoked_callback:
            self.connect('action-invoked', lambda _, action: self._on_action_invoked_callback(self, action))
        
        self._id: int = id

        self._app_name: str = raw_variant.get_child_value(0).unpack()
        self._replaces_id: int = raw_variant.get_child_value(1).unpack()
        self._app_icon: str = raw_variant.get_child_value(2).unpack()
        self._summary: str = raw_variant.get_child_value(3).unpack()
        self._body: str = raw_variant.get_child_value(4).unpack()

        raw_actions: list[str] = raw_variant.get_child_value(5).unpack()

        self._actions: list[NotificationAction] = [
            NotificationAction(raw_actions[i], raw_actions[i + 1], self)
            for i in range(0, len(raw_actions), 2)
        ]

        self._hints: GLib.Variant = raw_variant.get_child_value(6)
        self._timeout: int = raw_variant.get_child_value(7).unpack()

        self._urgency: int = self.do_get_hint_entry("urgency") or 1

        self._image_file: Optional[str] = self.do_get_hint_entry(
            "image-path"
        ) or self.do_get_hint_entry("image_path")

        self._image_pixmap: Optional[NotificationImagePixmap] = None
        if raw_image_data := (
            self.do_get_hint_entry("image-data", False)
            or self.do_get_hint_entry("icon_data", False)
        ):
            self._image_pixmap = NotificationImagePixmap(raw_image_data)
    
    @classmethod
    def deserialize(cls, data: NotificationSerializedData, **kwargs) -> "Notification":
        """Deserialize a given serialized notification data into a newly created notification object"""
        # Create a dummy variant to pass to __init__
        dummy_variant = GLib.Variant(
            "(sissassa{sv}i)",
            (
                data["app-name"],
                data["replaces-id"],
                data["app-icon"],
                data["summary"],
                data["body"],
                [item for action in data["actions"] for item in action],
                {},  # hints
                data["timeout"],
            )
        )
        
        self = cls(data["id"], dummy_variant, **kwargs)
        
        # Override with serialized data
        self._id = data["id"]
        self._replaces_id = data["replaces-id"]
        self._app_name = data["app-name"]
        self._app_icon = data["app-icon"]
        self._summary = data["summary"]
        self._body = data["body"]
        self._timeout = data["timeout"]
        self._urgency = data["urgency"]
        
        self._actions = [
            NotificationAction(action[0], action[1], self) for action in data["actions"]
        ]
        
        self._image_file = data["image-file"]
        self._image_pixmap = (
            NotificationImagePixmap.deserialize(data["image-pixmap"])
            if data["image-pixmap"]
            else None
        )
        
        return self

    def do_get_hint_entry(
        self, entry_key: str, unpack: bool = True
    ) -> Optional[GLib.Variant | Any]:
        variant = self._hints.lookup_value(entry_key)
        if not unpack or not variant:
            return variant
        return variant.unpack()

    def serialize(self) -> NotificationSerializedData:
        """Serialize this notification into a dictionary that can easily get converted into JSON"""
        return {
            "id": self._id,
            "replaces-id": self._replaces_id,
            "app-name": self._app_name,
            "app-icon": self._app_icon,
            "summary": self._summary,
            "body": self._body,
            "timeout": self._timeout,
            "urgency": self._urgency,
            "actions": [(action.identifier, action.label) for action in self._actions],
            "image-file": self._image_file,
            "image-pixmap": self._image_pixmap.serialize()
            if self._image_pixmap
            else None,
        }

    def invoke_action(self, action: str):
        """Invoke an action via its name"""
        self.emit('action-invoked', action)

    def close(
        self,
        reason: Literal[
            "expired", "dismissed-by-user", "closed-by-application", "unknown"
        ]
        | NotificationCloseReason = NotificationCloseReason.DISMISSED_BY_USER,
    ):
        """Close this notification and notify the sender with a reason"""
        self.emit('closed', get_enum_member(NotificationCloseReason, reason))
    
    # Properties
    @property
    def app_name(self) -> str:
        """The display name of the application sent this notification"""
        return self._app_name

    @property
    def app_icon(self) -> str:
        """An optional application icon name"""
        return self._app_icon

    @property
    def summary(self) -> str:
        """Notification summary/title"""
        return self._summary

    @property
    def body(self) -> str:
        """A multi-line body of text given by the sender (might contain markup)"""
        return self._body

    @property
    def id(self) -> int:
        """The unique identifier of this notification"""
        return self._id

    @property
    def replaces_id(self) -> int:
        """An optional ID of an existing notification that this notification is intended to replace"""
        return self._replaces_id

    @property
    def timeout(self) -> int:
        """Expiration timeout (in milliseconds)"""
        return self._timeout

    @property
    def urgency(self) -> int:
        """Urgency level of this notification"""
        return self._urgency

    @property
    def actions(self) -> list[NotificationAction]:
        """A list of all the action this notification has"""
        return self._actions

    @property
    def image_pixmap(self) -> Optional[NotificationImagePixmap]:
        """Raw image data supplied by the sender (if any)"""
        return self._image_pixmap

    @property
    def image_file(self) -> Optional[str]:
        """The image file path provided by the sender for this notification (if any)"""
        return self._image_file

    @property
    def image_pixbuf(self) -> Optional[GdkPixbuf.Pixbuf]:
        """A `Pixbuf` loaded from either `image-pixmap` or the `image-file` property"""
        if self.image_pixmap:
            return self.image_pixmap.as_pixbuf()
        if self.image_file:
            return GdkPixbuf.Pixbuf.new_from_file(self.image_file)
        return None
        
    @property
    def image_texture(self) -> Optional[Gdk.Texture]:
        """A `Texture` loaded from either `image-pixmap` or the `image-file` property (GTK4)"""
        if self.image_pixmap:
            return self.image_pixmap.as_texture()
        if self.image_file:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.image_file)
            return Gdk.Texture.new_for_pixbuf(pixbuf)
        return None


class Notifications(GObject.Object):
    """A server for watching in-coming notifications from running applications"""
    
    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'notification-added': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'notification-removed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'notification-closed': (GObject.SignalFlags.RUN_FIRST, None, (int, object)),
    }

    def __init__(self, **kwargs):
        GObject.Object.__init__(self)
        self._notifications: Dict[int, Notification] = {}
        self._connection: Optional[Gio.DBusConnection] = None
        self._counter = 0
        
        # Connect notification-added signal to update property
        self.connect('notification-added', self._on_notification_added)
        self.connect('notification-removed', self._on_notification_removed)
        
        # Register DBus service
        self.do_register()

    def _on_notification_added(self, _, notification_id: int):
        """Handler for notification-added signal"""
        notif = self.get_notification_from_id(notification_id)
        self.emit('changed')
    
    def _on_notification_removed(self, _, notification_id: int):
        """Handler for notification-removed signal"""
        self._notifications.pop(notification_id, None)
        self.emit('changed')

    def do_register(self) -> int:  # the bus id
        return Gio.bus_own_name(
            Gio.BusType.SESSION,
            NOTIFICATIONS_BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            self.on_bus_acquired,
            None,
            lambda *_: logger.warning(
                "[Notifications] couldn't own the DBus name, another notifications daemon is probably running."
            ),
        )

    def on_bus_acquired(
        self, conn: Gio.DBusConnection, name: str, user_data: object = None
    ) -> None:
        self._connection = conn
        # we now own the name
        for interface in NOTIFICATIONS_BUS_IFACE_NODE.interfaces:
            cast(Gio.DBusInterface, interface)
            if interface.name == name:
                conn.register_object(
                    NOTIFICATIONS_BUS_PATH,
                    interface,
                    self.do_handle_bus_call,
                )
        return

    def do_handle_bus_call(
        self,
        conn: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        target: str,
        params: tuple,
        invocation: Gio.DBusMethodInvocation,
        user_data: object = None,
    ) -> None:
        match target:
            case "Get":
                prop_name = params[1] if len(params) >= 1 else None
                match prop_name:
                    case _:
                        invocation.return_value(None)
            case "GetAll":
                invocation.return_value(GLib.Variant("(a{sv})", ({},)))

            case "CloseNotification":
                notif_id = int(params[0])
                self.emit('notification-removed', notif_id)
                invocation.return_value(None)

            case "GetCapabilities":
                invocation.return_value(
                    GLib.Variant(
                        "(as)",
                        (
                            [
                                "action-icons",
                                "actions",
                                "body",
                                "body-hyperlinks",
                                "body-images",
                                "body-markup",
                                "icon-static",
                                "persistence",
                            ],
                        ),
                    )
                )

            case "GetServerInformation":
                invocation.return_value(
                    GLib.Variant(
                        "(ssss)", ("hyprgtk4", "Hyprgtk4-Development", "0.1.0", "1.2")
                    )
                )

            case "Notify":
                notif_id = self.new_notification_id()

                self._notifications[notif_id] = Notification(
                    id=notif_id,
                    raw_variant=cast(GLib.Variant, params),
                    on_closed=self.do_handle_notification_closed,
                    on_action_invoked=self.do_handle_notification_action_invoke,
                )
                self.emit('notification-added', notif_id)

                invocation.return_value(GLib.Variant("(u)", (notif_id,)))

        return conn.flush()

    def do_emit_bus_signal(self, signal_name: str, params: GLib.Variant) -> None:
        if self._connection is not None:
            self._connection.emit_signal(
                None,
                NOTIFICATIONS_BUS_PATH,
                NOTIFICATIONS_BUS_NAME,
                signal_name,
                params,
            )
        return

    def new_notification_id(self) -> int:
        """Get the next notification id and increase the internal counter"""
        self._counter += 1
        return self._counter

    def do_handle_notification_action_invoke(
        self, notification: Notification, action: str
    ):
        # a pointer to a function is better than a new lambda on every notification
        return self.invoke_notification_action(notification.id, action)

    def do_handle_notification_closed(
        self, notification: Notification, reason: NotificationCloseReason
    ):
        return self.close_notification(notification.id, reason)

    def get_notification_from_id(self, notification_id: int) -> Optional[Notification]:
        """Lookup a notification via its identifier"""
        return self._notifications.get(notification_id)

    def invoke_notification_action(self, notification_id: int, action: str):
        """Invoke a named action on a notification"""
        return self.do_emit_bus_signal(
            "ActionInvoked", GLib.Variant("(us)", (notification_id, action))
        )

    def remove_notification(self, notification_id: int):
        """Remove a notification (without closing it) from the server"""
        self.emit('notification-removed', notification_id)

    def close_notification(
        self,
        notification_id: int,
        reason: NotificationCloseReason = NotificationCloseReason.DISMISSED_BY_USER,
    ):
        """Close a notification and remove it from the server"""
        self.emit('notification-closed', notification_id, reason)
        self.do_emit_bus_signal(
            "NotificationClosed",
            GLib.Variant(
                "(uu)", (notification_id, cast(NotificationCloseReason, reason).value)
            ),
        )

    def serialize(self) -> list[NotificationSerializedData]:
        """Serializes all notifications in the server"""
        return [notif.serialize() for notif in self._notifications.values()]

    def deserialize(self, data: list[NotificationSerializedData]):
        """Load a list of serialized notifications data"""
        for notif_data in data:
            self._notifications[notif_data["id"]] = Notification.deserialize(
                data=notif_data,
                on_closed=self.do_handle_notification_closed,
                on_action_invoked=self.do_handle_notification_action_invoke,
            )
            self.emit('notification-added', notif_data["id"])

        # Update counter to avoid ID conflicts
        if self._notifications:
            self._counter = max(self._notifications.keys())
        return
    
    @property
    def notifications(self) -> Dict[int, Notification]:
        """A list of all the notifications received by this server"""
        return self._notifications

# Add main function for standalone execution
if __name__ == "__main__":
    import signal
    
    # Initialize GLib main loop
    loop = GLib.MainLoop()
    
    # Create notification server
    notifications = Notifications()
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        loop.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the main loop
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
