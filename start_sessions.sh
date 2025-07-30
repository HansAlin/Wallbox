#!/bin/bash

# Path to the virtual environment
VENV_PATH="/home/pi/Projects/Wallbox/env"

# Function to check if a command is running in a tmux session
check_and_run() {
    local session_name=$1
    local command=$2

    echo "Checking session: $session_name" >> /home/pi/Projects/Wallbox/log.txt

    # Check if the tmux session exists
    tmux has-session -t "$session_name" 2>/dev/null
    if [ $? != 0 ]; then
        echo "Creating session: $session_name" >> /home/pi/Projects/Wallbox/log.txt
        tmux new-session -d -s "$session_name" "source $VENV_PATH/bin/activate && $command"
    else
        echo "Session $session_name exists, checking command..." >> /home/pi/Projects/Wallbox/log.txt
        tmux capture-pane -t "$session_name" -p | grep -q "$command"
        if [ $? != 0 ]; then
            echo "Command not running in session $session_name, sending keys..." >> /home/pi/Projects/Wallbox/log.txt
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