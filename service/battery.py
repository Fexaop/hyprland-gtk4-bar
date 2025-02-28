#!/usr/bin/env python3
import json
import subprocess
import sys
import os
import signal

shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    shutdown_flag = True
    print(json.dumps({"Charge State": "Shutdown", "Battery Percentage": "N/A", "Time": "Service terminated"}))
    sys.exit(0)

def get_battery_info():
    if shutdown_flag:
        return {"Charge State": "Shutdown", "Battery Percentage": "N/A", "Time": "Service terminated"}
    
    try:
        acpi_output = subprocess.check_output(['acpi', '-b'], text=True).strip()
        parts = acpi_output.split(', ')

        status = "Unknown"
        if "Charging" in parts[0]:
            status = "Charging"
        elif "Discharging" in parts[0]:
            status = "Discharging"
        elif "Full" in parts[0]:
            status = "Full"

        percentage = parts[1].strip() if len(parts) >= 2 else "0%"
        time_info = "N/A"
        if len(parts) >= 3:
            time_raw = parts[2].strip()
            time_info = (
                f"Time to empty: {time_raw.replace(' remaining', '')}" if "remaining" in time_raw else
                f"Time to full: {time_raw.replace(' until charged', '')}" if "until charged" in time_raw else
                "N/A"
            )
            
        return {
            "Charge State": status,
            "Battery Percentage": percentage,
            "Time": time_info
        }
        
    except Exception as e:
        return {
            "Charge State": "Error",
            "Battery Percentage": "N/A",
            "Time": f"Error: {str(e)}"
        }

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not os.path.exists('/usr/bin/acpi'):
        print("Install Acpi, Gandu")
        sys.exit(1)
    print(json.dumps(get_battery_info()))

if __name__ == '__main__':
    main()