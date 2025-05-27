import gi
import base64
from enum import Enum
from loguru import logger
from dataclasses import dataclass
from typing import cast, Literal, TypedDict, Any, Optional

gi.require_version("Gtk", "4.0")
gi.require_version('GdkPixbuf', '2.0')
gi.require_version("Gdk", "4.0")

from gi.repository import Gio, GLib, GdkPixbuf, GObject, Gdk

def load_dbus_xml(xml_path: str) -> Gio.DBusNodeInfo:
    with open(xml_path, "r") as f:
        xml_content = f.read()
    return Gio.DBusNodeInfo.new_for_xml(xml_content)

NOTIFICATIONS_BUS_NAME = "org.freedesktop.Notifications"
NOTIFICATIONS_BUS_PATH = "/org/freedesktop/Notifications"
NOTIFICATIONS_BUS_IFACE_NODE = load_dbus_xml(
    "./dbus_assets/org.freedesktop.Notifications.xml",
)

class NotificationCloseReason(Enum):
    EXPIRED = 1
    DISMISSED_BY_USER = 2
    CLOSED_BY_APPLICATION = 3
    UNKNOWN = 4

def get_enum_member(enum_class, value):
    """Helper function to get an enum member by value or name."""
    if isinstance(value, enum_class):
        return value
    if isinstance(value, str):
        return enum_class[value.upper()]
    return enum_class(value)

class NotificationImagePixmap:
    @classmethod
    def deserialize(cls, data: tuple[int, int, int, bool, int, int, str]) -> "NotificationImagePixmap":
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
        self.byte_array = GLib.Bytes.new(base64.b64decode(self.byte_array))  # type: ignore
        self._pixbuf = None
        return self

    def __init__(self, raw_variant: GLib.Variant):
        self.width = raw_variant.get_child_value(0).unpack()  # type: ignore
        self.height = raw_variant.get_child_value(1).unpack()  # type: ignore
        self.rowstride = raw_variant.get_child_value(2).unpack()  # type: ignore
        self.has_alpha = raw_variant.get_child_value(3).unpack()  # type: ignore
        self.bits_per_sample = raw_variant.get_child_value(4).unpack()  # type: ignore
        self.channels = raw_variant.get_child_value(5).unpack()  # type: ignore
        self.byte_array = raw_variant.get_child_value(6).get_data_as_bytes()  # type: ignore
        self._pixbuf: GdkPixbuf.Pixbuf | None = None

    def as_pixbuf(self) -> GdkPixbuf.Pixbuf:
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
        if self._pixbuf is None:
            self._pixbuf = self.as_pixbuf()
        return Gdk.Texture.new_for_pixbuf(self._pixbuf)

    def serialize(self) -> tuple[int, int, int, bool, int, int, str]:
        return (
            self.width,
            self.height,
            self.rowstride,
            self.has_alpha,
            self.bits_per_sample,
            self.channels,
            base64.b64encode(cast(bytes, self.byte_array.unref_to_array())).decode("ascii"),
        )

@dataclass
class NotificationAction:
    identifier: str
    label: str
    parent: "Notification"
    def invoke(self):
        return self.parent.invoke_action(self.identifier)

NotificationSerializedData = TypedDict(
    "NotificationSerializedData",
    {   "id": int,
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
    __gsignals__ = {
        "closed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "action-invoked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def app_icon(self) -> str:
        return self._app_icon

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def body(self) -> str:
        return self._body

    @property
    def id(self) -> int:
        return self._id

    @property
    def replaces_id(self) -> int:
        return self._replaces_id

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def urgency(self) -> int:
        return self._urgency

    @property
    def actions(self) -> list[NotificationAction]:
        return self._actions

    @property
    def image_pixmap(self) -> NotificationImagePixmap:
        return self._image_pixmap  # type: ignore

    @property
    def image_file(self) -> str:
        return self._image_file  # type: ignore

    @property
    def image_pixbuf(self) -> GdkPixbuf.Pixbuf:
        if self.image_pixmap:
            return self.image_pixmap.as_pixbuf()
        if self.image_file:
            return GdkPixbuf.Pixbuf.new_from_file(self.image_file)
        return None  # type: ignore
    
    @property
    def image_texture(self) -> Optional[Gdk.Texture]:
        """A `Texture` loaded from either `image-pixmap` or the `image-file` property (GTK4)"""
        if self.image_pixmap:
            return self.image_pixmap.as_texture()
        if self.image_file:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.image_file)
            return Gdk.Texture.new_for_pixbuf(pixbuf)
        return None

    @classmethod
    def deserialize(cls, data: NotificationSerializedData, **kwargs) -> "Notification":
        self = cls.__new__(cls)
        GObject.Object.__init__(self, **kwargs)
        self._id = data["id"]
        self._app_name = data["app-name"]
        self._replaces_id = data["replaces-id"]
        self._app_icon = data["app-icon"]
        self._summary = data["summary"]
        self._body = data["body"]
        self._timeout = data["timeout"]
        self._urgency = data["urgency"]
        self._actions = [NotificationAction(action[0], action[1], self) for action in data["actions"]]
        self._image_file = data["image-file"]
        self._image_pixmap = (NotificationImagePixmap.deserialize(data["image-pixmap"]) 
                              if data["image-pixmap"] else None)
        return self

    def __init__(self, id: int, raw_variant: GLib.Variant, **kwargs):
        kwargs.pop("on_closed", None)
        kwargs.pop("on_action_invoked", None)
        GObject.Object.__init__(self, **kwargs)
        self._id: int = id
        self._app_name: str = raw_variant.get_child_value(0).unpack()  # type: ignore
        self._replaces_id: int = raw_variant.get_child_value(1).unpack()  # type: ignore
        self._app_icon: str = raw_variant.get_child_value(2).unpack()  # type: ignore
        self._summary: str = raw_variant.get_child_value(3).unpack()  # type: ignore
        self._body: str = raw_variant.get_child_value(4).unpack()  # type: ignore
        raw_actions: list[str] = raw_variant.get_child_value(5).unpack()  # type: ignore
        self._actions: list[NotificationAction] = [
            NotificationAction(raw_actions[i], raw_actions[i + 1], self)
            for i in range(0, len(raw_actions), 2)
        ]
        self._hints: GLib.Variant = raw_variant.get_child_value(6)  # type: ignore
        self._timeout: int = raw_variant.get_child_value(7).unpack()  # type: ignore
        self._urgency: int = self.do_get_hint_entry("urgency") or 1  # type: ignore
        self._image_file: str | None = self.do_get_hint_entry("image-path") or self.do_get_hint_entry("image_path")  # type: ignore
        self._image_pixmap: NotificationImagePixmap | None = None
        if raw_image_data := (self.do_get_hint_entry("image-data", False) or self.do_get_hint_entry("icon_data", False)):
            self._image_pixmap = NotificationImagePixmap(raw_image_data)

    def do_get_hint_entry(self, entry_key: str, unpack: bool = True) -> GLib.Variant | Any | None:
        variant = self._hints.lookup_value(entry_key)
        if not unpack or not variant:
            return variant
        return variant.unpack()  # type: ignore
    
    def as_texture(self) -> Gdk.Texture:
        """Load a `Texture` variant of this pixmap for GTK4"""
        if self._texture is not None:
            return self._texture
            
        pixbuf = self.as_pixbuf()
        self._texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        return self._texture
    
    def serialize(self) -> NotificationSerializedData:
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
        print(f"Invoking action: {action} for notification ID: {self._id}")
        return self.emit("action-invoked", action)

    def close(self, reason: Literal["expired", "dismissed-by-user", "closed-by-application", "unknown"] | NotificationCloseReason = NotificationCloseReason.DISMISSED_BY_USER):
        print(f"Closing notification ID: {self._id} with reason: {reason}")
        return self.emit("closed", get_enum_member(NotificationCloseReason, reason))

class Notifications(GObject.Object):
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "notification-added": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "notification-removed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "notification-closed": (GObject.SignalFlags.RUN_FIRST, None, (int, object)),
    }

    @property
    def notifications(self) -> dict[int, Notification]:
        return self._notifications

    def __init__(self, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        self._notifications: dict[int, Notification] = {}
        self._connection: Gio.DBusConnection | None = None
        self._counter = 0
        self.do_register()

    def do_register(self) -> int:
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

    def on_bus_acquired(self, conn: Gio.DBusConnection, name: str, user_data: object = None) -> None:
        self._connection = conn
        for interface in NOTIFICATIONS_BUS_IFACE_NODE.interfaces:
            cast(Gio.DBusInterface, interface)
            if interface.name == name:
                conn.register_object(
                    NOTIFICATIONS_BUS_PATH,
                    interface,
                    self.do_handle_bus_call,  # type: ignore
                )
        return

    def do_handle_bus_call(self, conn: Gio.DBusConnection, sender: str, path: str, interface: str, target: str, params: tuple, invocation: Gio.DBusMethodInvocation, user_data: object = None) -> None:
        match target:
            case "Get":
                prop_name = params[1] if len(params) >= 1 else None
                invocation.return_value(None)
            case "GetAll":
                invocation.return_value(GLib.Variant("(a{sv})", ({},)))
            case "CloseNotification":
                notif_id = int(params[0])
                print(f"Received CloseNotification for ID: {notif_id}")
                self.remove_notification(notif_id)
                invocation.return_value(None)
            case "GetCapabilities":
                invocation.return_value(
                    GLib.Variant("(as)", (
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
                    ))
                )
            case "GetServerInformation":
                invocation.return_value(
                    GLib.Variant("(ssss)", ("fabric", "Fabric-Development", "0.0.2", "1.2"))
                )
            case "Notify":
                notif_id = self.new_notification_id()
                notification = Notification(
                    id=notif_id,
                    raw_variant=cast(GLib.Variant, params),
                    on_closed=self.do_handle_notification_closed,
                    on_action_invoked=self.do_handle_notification_action_invoke,
                )
                print(f"Created notification ID: {notif_id}, Actions: {[action.label for action in notification.actions]}")
                self._notifications[notif_id] = notification
                self.emit("notification-added", notif_id)
                invocation.return_value(GLib.Variant("(u)", (notif_id,)))
        return conn.flush()

    def do_emit_bus_signal(self, signal_name: str, params: GLib.Variant) -> None:
        if self._connection is not None:
            print(f"Emitting DBus signal: {signal_name} with params: {params}")
            self._connection.emit_signal(
                None,
                NOTIFICATIONS_BUS_PATH,
                NOTIFICATIONS_BUS_NAME,
                signal_name,
                params,
            )
        else:
            print(f"Failed to emit DBus signal: {signal_name}, no connection")
        return

    def new_notification_id(self) -> int:
        self._counter += 1
        return self._counter

    def do_handle_notification_action_invoke(self, notification: Notification, action: str):
        print(f"Handling action invoke for notification ID: {notification.id}, action: {action}")
        return self.invoke_notification_action(notification.id, action)

    def do_handle_notification_closed(self, notification: Notification, reason: NotificationCloseReason):
        print(f"Handling notification close for ID: {notification.id}, reason: {reason}")
        return self.close_notification(notification.id, reason)

    def get_notification_from_id(self, notification_id: int) -> Notification | None:
        return self._notifications.get(notification_id)

    def invoke_notification_action(self, notification_id: int, action: str):
        print(f"Invoking notification action for ID: {notification_id}, action: {action}")
        return self.do_emit_bus_signal("ActionInvoked", GLib.Variant("(us)", (notification_id, action)))

    def remove_notification(self, notification_id: int):
        print(f"Removing notification ID: {notification_id}")
        self._notifications.pop(notification_id, None)
        return self.emit("notification-removed", notification_id)

    def close_notification(self, notification_id: int, reason: NotificationCloseReason = NotificationCloseReason.DISMISSED_BY_USER):
        print(f"Closing notification ID: {notification_id}, reason: {reason}")
        return self.emit("notification-closed", notification_id, reason)

    def serialize(self) -> list[NotificationSerializedData]:
        return [notif.serialize() for notif in self._notifications.values()]

    def deserialize(self, data: list[NotificationSerializedData]):
        for notif_data in data:
            self._notifications[notif_data["id"]] = Notification.deserialize(
                data=notif_data,
                on_closed=self.do_handle_notification_closed,
                on_action_invoked=self.do_handle_notification_action_invoke,
            )
            self.emit("notification-added", notif_data["id"])
        self._counter += max(self._notifications.keys() or (1,))
        return

if __name__ == "__main__":
    import sys
    import signal
    from gi.repository import GLib

    notifications = Notifications()

    def format_notification(notif) -> str:
        if notif._image_pixmap:
            pixmap = notif._image_pixmap
            pixmap_details = (f"(width={pixmap.width}, height={pixmap.height}, "
                              f"rowstride={pixmap.rowstride}, has_alpha={pixmap.has_alpha}, "
                              f"bits_per_sample={pixmap.bits_per_sample}, channels={pixmap.channels})")
        else:
            pixmap_details = "None"
        return (f"ID: {notif.id}, App: {notif.app_name}, Summary: {notif.summary}, "
                f"Icon: {notif.app_icon}, Image_file: {notif.image_file}, "
                f"Image_pixmap: {pixmap_details}")

    def log_all_notifications():
        logger.info("Logging all notifications:")
        for notif in notifications._notifications.values():
            logger.info(format_notification(notif))

    def on_notification_joined(obj, notif_id):
        notif = notifications._notifications.get(notif_id)
        if notif:
            logger.debug(f"Notification joined: {notif_id} -> {format_notification(notif)}")
        else:
            logger.debug(f"Notification joined: {notif_id} -> Not found")
        log_all_notifications()

    def on_notification_removed(obj, notif_id):
        logger.debug(f"Notification removed: {notif_id}")
        log_all_notifications()

    notifications.connect("notification-added", on_notification_joined)
    notifications.connect("notification-removed", on_notification_removed)

    loop = GLib.MainLoop()
    if hasattr(GLib, "unix_signal_add"):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, loop.quit)
    else:
        signal.signal(signal.SIGINT, lambda s, f: loop.quit())

    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()