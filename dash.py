# dash.py
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


def create_dashboard_content():
    grid = Gtk.Grid()
    grid.set_column_spacing(10)
    grid.set_row_spacing(10)
    grid.set_margin_top(10)
    grid.set_margin_bottom(10)
    grid.set_margin_start(10)
    grid.set_margin_end(10)

    # Calendar
    calendar = Gtk.Calendar()
    grid.attach(calendar, 0, 0, 1, 1)

    # Notification History (Placeholder)
    notification_label = Gtk.Label(label="Notification History")
    notification_label.set_halign(Gtk.Align.START)
    notification_label.set_hexpand(True)
    notification_scrolled = Gtk.ScrolledWindow()
    notification_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    notification_list = Gtk.ListBox()
    notification_scrolled.set_child(notification_list)

    # Add some placeholder items
    for i in range(5):
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=f"Notification {i+1}", hexpand=True, halign=Gtk.Align.START)
        row.set_child(label)
        notification_list.append(row)

    grid.attach(notification_label, 1, 0, 1, 1)
    grid.attach(notification_scrolled, 1, 1, 1, 1)

    # Do Not Disturb (Placeholder)
    dnd_label = Gtk.Label(label="Do Not Disturb")
    dnd_switch = Gtk.Switch()
    dnd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    dnd_box.append(dnd_label)
    dnd_box.append(dnd_switch)
    dnd_box.set_halign(Gtk.Align.CENTER)

    grid.attach(dnd_box, 0, 2, 2, 1)

    return grid