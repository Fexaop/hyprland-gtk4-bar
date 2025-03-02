
import json
import os
import subprocess
import sched
import time

class HyprlandMonitor:
    def __init__(self, output_file="~/.cache/hypr_info.txt", update_interval=0.5):
        self.output_file = os.path.expanduser(output_file)
        self.update_interval = update_interval
        self.active_window = {}
        self.current_workspace = 1
        self.scheduler = sched.scheduler(time.time, time.sleep)

    def get_hyprland_info(self):
        try:
            window_result = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, check=False
            )
            workspace_result = subprocess.run(
                ["hyprctl", "activeworkspace", "-j"],
                capture_output=True, text=True, check=False
            )
            window_info = {}
            workspace_id = 1
            if window_result.returncode == 0 and window_result.stdout.strip():
                try:
                    window_data = json.loads(window_result.stdout)
                    window_info = {
                        "title": window_data.get("title", ""),
                        "class": window_data.get("class", ""),
                        "app_id": window_data.get("initialClass", "")
                    }
                except json.JSONDecodeError:
                    pass
            if workspace_result.returncode == 0 and workspace_result.stdout.strip():
                try:
                    workspace_data = json.loads(workspace_result.stdout)
                    workspace_id = workspace_data.get("id", 1)
                except json.JSONDecodeError:
                    pass
            return window_info, workspace_id
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"Error getting Hyprland info: {e}")
            return {}, 1

    def _update_info_file(self):
        try:
            with open(self.output_file, "w") as f:
                info = {
                    "workspace": self.current_workspace,
                    "window": self.active_window
                }
                f.write(json.dumps(info, indent=2))
        except Exception as e:
            print(f"Error writing to info file: {e}")

    def check_update(self):
        try:
            window_info, workspace_id = self.get_hyprland_info()
            if window_info != self.active_window or workspace_id != self.current_workspace:
                self.active_window = window_info
                self.current_workspace = workspace_id
                self._update_info_file()
        except Exception as e:
            print(f"Error in check_update: {e}")
        self.scheduler.enter(self.update_interval, 1, self.check_update)

    def start(self):
        self._update_info_file()
        print(f"Hyprland monitor started - writing info to {self.output_file}")
        self.scheduler.enter(self.update_interval, 1, self.check_update)
        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            print("Monitoring stopped.")

if __name__ == "__main__":
    monitor = HyprlandMonitor()
    monitor.start()