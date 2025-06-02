import gi
gi.require_version('AstalNetwork', '0.1') 
from gi.repository import AstalNetwork as Network

network = Network.get_default()

print(network.get_wifi().get_ssid())