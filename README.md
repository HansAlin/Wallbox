# Wallbox

Wallbox is for anyone who has a GARO Wallbox (GLB Fixed cable Wifi) for charging their EV and that has prices on electric power from Nordpool.

The code is currently running on a Raspberry Pi 5 8GB.

## Notes

In the code, there is a function that reads the temperature from a device on my roof. The reason for that is the power should be available when it is low temperature. If you don't implement temperature reader the function just returns False, it is not low temperature.

Remember to set correct timezone, especially if you are using a Raspberry Pi:

```bash
sudo timedatectl set-timezone <Your_Time_Zone>
```

## Config File

Create a config.py file in the same folder as main.py. Example:

```python
# GARO url
url_garo = "http://192.168.1.81:8080"

# NordPool
region = 'SE3'

# URL for the temperature device (optional)
low_temp_url = 'http://192.168.1.200'

# URL for the server (start server.py first)
server_url = 'http://192.168.1.141:5000'

# URL for the router (optional)
router_url = "http://router.asus.com/Main_Login.asp"

tz_region = 'Europe/Stockholm'
```

Change these URLs according to your network and preferences.

## Running the Scripts Automatically on Reboot (systemd + tmux)

1. Make your script executable

```bash
chmod +x /home/pi/Projects/Wallbox/start_sessions.sh
```

2. Create systemd user service folder

```bash
mkdir -p ~/.config/systemd/user
```

3. Create the service file

```bash
nano ~/.config/systemd/user/energy_scripts.service
```

Paste this inside:

```ini
[Unit]
Description=Start Energy Scripts in tmux
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/Projects/Wallbox
ExecStart=/home/pi/Projects/Wallbox/start_sessions.sh
Restart=on-failure
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=/home/pi/Projects/Wallbox/env
Environment=HOME=/home/pi
StandardOutput=journal
StandardError=journal
SyslogIdentifier=energy-scripts
LogLevelMax=info

[Install]
WantedBy=default.target
```

4. Reload systemd and enable the service

```bash
systemctl --user daemon-reload
systemctl --user enable energy_scripts.service
systemctl --user start energy_scripts.service
systemctl --user status energy_scripts.service
```

5. Enable lingering (optional, allows service to run without login)

```bash
sudo loginctl enable-linger pi
```

6. Reboot to test

```bash
sudo reboot
```

## Startup Script (start_sessions.sh)

```bash
#!/bin/bash

# Paths
VENV_PATH="/home/pi/Projects/Wallbox/env"
PROJECT_DIR="/home/pi/Projects/Wallbox"
LOG_DIR="$PROJECT_DIR/logs"

# Create logs folder if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to start a Python script in a loop with logging
start_script() {
    local script_name=$1
    local log_file="$LOG_DIR/${script_name%.py}.log"  # log file named after script, without .py

    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting $script_name" >> "$log_file"

    while true; do
        cd "$PROJECT_DIR"
        source "$VENV_PATH/bin/activate"
        python "$script_name" >> "$log_file" 2>&1
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $script_name crashed, restarting in 5s..." >> "$log_file"
        sleep 5
    done
}

# Start all scripts in background
start_script "energy_main.py" &
start_script "energy_display.py" &
start_script "server.py" &
start_script "main.py" &

# Optional: wait for all background jobs (not strictly needed for systemd)
wait

```

## Viewing Logs

Tail a single script log in real-time

```bash
tail -f ~/Projects/Wallbox/logs/main.log
tail -f ~/Projects/Wallbox/logs/server.log
tail -f ~/Projects/Wallbox/logs/energy_display.log
tail -f ~/Projects/Wallbox/logs/energy_main.log
tail -f ~/Projects/Wallbox/logs/startup.log
```

Tail all logs at once

```bash
tail -f ~/Projects/Wallbox/logs/*.log
```

Check systemd journal (optional)

```bash
journalctl --user -u energy_scripts.service -f
```

## Log Rotation (Keep 2–3 days)

Create a logrotate configuration to prevent logs from filling the SD card:

Create a file /etc/logrotate.d/wallbox with:

```text
/home/pi/Projects/Wallbox/logs/*.log {
daily
rotate 3
missingok
notifempty
compress
delaycompress
copytruncate
}
```

## Best Practices

* Python scripts restart automatically if they crash.
* Logs are separated per script in logs/.
* Use tail -f to view real-time output.
* tmux sessions are optional for interactive debugging.
* Keep SD card space in mind; log rotation prevents filling it up.