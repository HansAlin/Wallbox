#!/bin/bash

# Move to the directory where the script is located
cd $(dirname "$0")

# Log file
LOGFILE=/home/seb/tets/Wallbox/start_sessions.log

# Log the current environment
echo "Starting script at $(date)" >> $LOGFILE
echo "Current directory: $(pwd)" >> $LOGFILE
echo "User: $(whoami)" >> $LOGFILE
echo "Environment variables:" >> $LOGFILE
env >> $LOGFILE

# Function to start a tmux session if it doesn't already exist
start_tmux_session() {
  session_name=$1
  command1=$2
  command2=$3

  if ! tmux has-session -t $session_name 2>/dev/null; then
    tmux new-session -d -s $session_name
    tmux send-keys -t $session_name "$command1" C-m
    tmux send-keys -t $session_name "$command2" C-m
    echo "Started tmux session: $session_name" >> $LOGFILE
  else
    echo "Tmux session $session_name already exists." >> $LOGFILE
  fi
}

# Start tmux sessions
start_tmux_session "server" "source /home/seb/tets/Wallbox/garo/bin/activate" "python /home/seb/tets/Wallbox/server.py"
start_tmux_session "main" "source /home/seb/tets/Wallbox/garo/bin/activate" "python /home/seb/tets/Wallbox/main.py"
start_tmux_session "power" "source /home/seb/tets/Wallbox/garo/bin/activate" "python /home/seb/tets/Wallbox/energy_main.py"
start_tmux_session "power_display" "source /home/seb/tets/Wallbox/garo/bin/activate" "python /home/seb/tets/Wallbox/energy_display.py"

echo "All tmux sessions checked and started if not already running." >> $LOGFILE