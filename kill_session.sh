#!/bin/bash

# Log file
LOGFILE=/home/seb/tets/Wallbox/stop_sessions.log

# Function to kill a tmux session if it exists
kill_tmux_session() {
  session_name=$1

  if tmux has-session -t $session_name 2>/dev/null; then
    tmux kill-session -t $session_name
    echo "Killed tmux session: $session_name" >> $LOGFILE
  else
    echo "Tmux session $session_name does not exist." >> $LOGFILE
  fi
}

# Kill tmux sessions
kill_tmux_session "server"
kill_tmux_session "main"
kill_tmux_session "power"
kill_tmux_session "power_display"

echo "All specified tmux sessions checked and killed if they existed." >> $LOGFILE