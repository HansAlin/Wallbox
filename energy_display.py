import socket
import threading
from flask import Flask, render_template_string, send_file
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_socketio import SocketIO, emit
import io
import json
import time
from datetime import datetime
import pandas as pd
import pickle
import pygal
from pygal.style import LightStyle
import cairosvg 

app = Flask(__name__)
socketio = SocketIO(app)

# Global variable to store data
data = {}
state = {}

import json
import pickle

def read_json_file():
    global data
    global state

    # Handle JSON file reading
    try:
        with open('data/energy_status.json', 'r') as file:
            content = file.read().strip()
            if content:  # Check if the file is not empty
                data = json.loads(content)
            else:
                data = {}  # Set data to an empty dictionary if the file is empty
    except FileNotFoundError:
        print("Error: 'data/energy_status.json' file not found.")
        data = {}  # Default to an empty dictionary
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        data = {}  # Default to an empty dictionary

    # Handle pickle file reading
    try:
        with open('data/saved_data.pkl', 'rb') as f:
            file_content = f.read()
            state = pickle.loads(file_content)
    except FileNotFoundError:
        print("Error: 'data/saved_data.pkl' file not found.")
        state = {}  # Default to an empty dictionary
    except pickle.UnpicklingError as e:
        print(f"Error unpickling data: {e}")
        state = {}  # Default to an empty dictionary

def update_data_periodically():
    while True:
        read_json_file()
        time.sleep(20)  # Wait for 1 minute

@app.route('/')
def index():
    power_current_mean = int(data.get('power_current_mean', 0))
    third_highest_power = int(data.get('third_highest_power', 0))
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Power Status</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f4f4f4;
                }
                .header {
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px;
                    text-align: center;
                }
                .content {
                    padding: 20px;
                    text-align: center;
                }
                h1 {
                    font-size: 1em;
                }
                p {
                    font-size: 1em;
                }
                img {
                    width: 100%;
                    height: auto;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Power Status Dashboard</h1>
            </div>
            <div class="content">
                <p>Power Current Mean: {{ power_current_mean }}</p>
                <p>Third Highest Power: {{ third_highest_power }}</p>
                <img src="/plot.png" alt="Power Month List Plot">
            </div>
        </body>
        </html>
    ''', power_current_mean=power_current_mean, third_highest_power=third_highest_power)

@app.route('/plot.png')
def plot_png():
    # Unzip the data into datetime and power lists
    datetime_list, power_list = zip(*data.get('power_current_list', []))
    
    # Convert datetime strings to datetime objects
    datetime_list = [datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f') for datetime_str in datetime_list]

    mean_power = data.get('power_current_mean', 0)

    # Two plots in one figure
    fig, axs = plt.subplots(2, 1, figsize=(16, 8))  # Increase figure size
    axs = axs.flatten()

    axs[0].plot(datetime_list, power_list, label='Current power')
    axs[0].set_title('Hour', fontsize=24)  # Increase title font size
    axs[0].set_xlabel('Time', fontsize=20)  # Increase x-axis label font size
    axs[0].set_ylabel('Power', fontsize=20)  # Increase y-axis label font size
    # Horizontal lines for the third highest power
    third_highest_power = data.get('third_highest_power', 0)
    axs[0].axhline(third_highest_power, color='red', linestyle='--', label='Third Highest Power')
    axs[0].axhline(mean_power, color='green', linestyle='--', label='Mean Power')
    axs[0].legend()
    axs[0].grid(True)


    # Plot month list is not empty
    if data.get('power_month_list'):
        month_list, month_power_list = zip(*data.get('power_month_list', []))
        month_list = pd.to_datetime(month_list, format='ISO8601').tolist()
        #month_list = [datetime.strptime(month_str, '%Y-%m-%d %H:%M:%S.%f') for month_str in month_list]
        axs[1].bar(month_list, month_power_list, label='Month', width=0.03)
        # Horizontal lines for the third highest power
        axs[1].axhline(third_highest_power, color='red', linestyle='--', label='Third Highest Power')
        axs[1].set_title('Power Month List', fontsize=24)
        axs[1].set_xlabel('Time', fontsize=20)
        axs[1].set_ylabel('Power', fontsize=20)
        axs[1].legend()

    # Thight layout
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype='image/png')




def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f"Server is running at http://{local_ip}:5001/")
    print("Ensure your firewall allows incoming connections on port 5000.")
    print("If you are using WSL, use your Windows host IP address to access the server from other devices.")
    # Start the background thread to update data periodically
    threading.Thread(target=update_data_periodically, daemon=True).start()
    # Read the JSON file initially
    read_json_file()
    # Run the Flask application
    app.run(host='0.0.0.0', port=5001, debug=True)