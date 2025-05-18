#!/bin/bash

# Path to the virtual environment
VENV_PATH="/home/pi/Projects/Wallbox/env"

# Function to check if a command is running in a tmux session
check_and_run() {
    local session_name=$1
    local command=$2

    # Check if the tmux session exists
    tmux has-session -t "$session_name" 2>/dev/null
    if [ $? != 0 ]; then
        # If the session doesn't exist, create it and run the command
        tmux new-session -d -s "$session_name" "source $VENV_PATH/bin/activate && $command"
    else
        # If the session exists, check if the command is running
        tmux capture-pane -t "$session_name" -p | grep -q "$command"
        if [ $? != 0 ]; then
            # If the command is not running, send it to the session
            tmux send-keys -t "$session_name" "source $VENV_PATH/bin/activate && $command" C-m
        fi
    fi
}

# Check and run the Python scripts in their respective sessions
check_and_run "power" "python /home/pi/Projects/Wallbox/energy_main.py"
check_and_run "power_display" "python /home/pi/Projects/Wallbox/energy_display.py"

check_and_run "server" "python /home/pi/Projects/Wallbox/server.py"
check_and_run "main" "python /home/pi/Projects/Wallbox/main.py"

# Then keep the script running so systemd stays happy:
tail -f /dev/null
