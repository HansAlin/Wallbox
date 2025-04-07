#!/bin/bash

# Start tmux session for server
tmux new-session -d -s server
tmux send-keys -t server 'source garo/bin/activate' C-m
tmux send-keys -t server 'python server.py' C-m

# Start tmux session for main
tmux new-session -d -s main
tmux send-keys -t main 'source garo/bin/activate' C-m
tmux send-keys -t main 'python main.py' C-m

# Start tmux session for power
tmux new-session -d -s power
tmux send-keys -t power 'source garo/bin/activate' C-m
tmux send-keys -t power 'python energy_main.py' C-m

# Start tmux session for power_display
tmux new-session -d -s power_display
tmux send-keys -t power_display 'source garo/bin/activate' C-m
tmux send-keys -t power_display 'python power_display.py' C-m

echo "All tmux sessions started."
