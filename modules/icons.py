# Parameters
font_family: str = 'tabler-icons'
font_weight: str = 'normal'

span: str = f"<span font-family='{font_family}' font-weight='{font_weight}'>"

#Panels
apps: str = "&#xf1fd;"
dashboard: str = "&#xea87;"
chat: str = "&#xf59f;"
wallpapers: str = "&#xeb01;"
windows: str = "&#xefe6;"

# Bar
colorpicker: str = "&#xebe6;"
media: str = "&#xf00d;"

# Circles
temp: str = "&#xeb38;"
disk: str = "&#xea88;"
battery: str = "&#xea38;"
memory: str = "&#xfa97;"
cpu: str = "&#xef8e;"

# AIchat
reload: str = "&#xf3ae;"
detach: str = "&#xea99;"

# Wallpapers
add: str = "&#xeb0b;"
sort: str = "&#xeb5a;"
circle: str = "&#xf671;"

# Chevrons
chevron_up: str = "&#xea62;"
chevron_down: str = "&#xea5f;"
chevron_left: str = "&#xea60;"
chevron_right: str = "&#xea61;"

# Power
lock: str = "&#xeae2;"
suspend: str = "&#xece7;"
logout: str = "&#xeba8;"
reboot: str = "&#xeb13;"
shutdown: str = "&#xeb0d;"

# Applets
wifi: str = "&#xeb52;"
bluetooth: str = "&#xea37;"
night: str = "&#xeaf8;"
coffee: str = "&#xef0e;"
dnd: str = "&#xea35;"

wifi_off: str = "&#xecfa;"
bluetooth_off: str = "&#xeceb;"
night_off: str = "&#xf162;"
dnd_off: str = "&#xece9;"

# Bluetooth
bluetooth_connected: str = "&#xecea;"
bluetooth_disconnected: str = "&#xf081;"

# Player
pause: str = "&#xf690;"
play: str = "&#xf691;"
stop: str = "&#xf695;"
skip_back: str = "&#xf693;"
skip_forward: str = "&#xf694;"
prev: str = "&#xf697;"
next: str = "&#xf696;"
shuffle: str = "&#xf000;"
repeat: str = "&#xeb72;"
music: str = "&#xeafc;"
rewind_backward_5: str = "&#xfabf;"
rewind_forward_5: str = "&#xfac7;"

# Volume
vol_off: str = "&#xf1c3;"
vol_mute: str = "&#xeb50;"
vol_medium: str = "&#xeb4f;"
vol_high: str = "&#xeb51;"

# Overview
circle_plus: str = "&#xea69;"

# Pins
copy_plus: str = "&#xfdae;"

# Confirm
accept: str = "&#xea5e;"
cancel: str = "&#xeb55;"
trash: str = "&#xeb41;"

# Config
config: str = "&#xeb20;"

# Icons
firefox: str = "&#x100c6;"
firefox_off: str = "&#xec2c;"
chromium: str = "&#xec18;"
spotify: str = "&#xfe86;"
spotify_off: str = "&#xed03;"
disc: str = "&#x1003e;"
disc_off: str = "&#xea90;"

# Misc
dot: str = "&#xf698;"
xbox = "&#xeb55;"
exceptions: list[str] = ['font_family', 'font_weight', 'span']

def apply_span() -> None:
    global_dict = globals()
    for key in global_dict:
        if key not in exceptions and not key.startswith('__'):
            global_dict[key] = f"{span}{global_dict[key]}</span>"

apply_span()

