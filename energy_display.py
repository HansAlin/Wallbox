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

import os




app = Flask(__name__)
socketio = SocketIO(app)


class DataManager:
    def __init__(self):
        self.data = {}
        self.state = {}

    def read_json_file(self, retries=3, delay=2):
        json_path = 'data/energy_status.json'
        for attempt in range(retries):
            try:
                if os.path.getsize(json_path) < 10:  # Arbitrary small threshold
                    raise ValueError("File too small to be valid JSON")

                with open(json_path, 'r') as file:
                    content = file.read().strip()
                    self.data = json.loads(content) if content else {}
                    break  # success
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                print(f"JSON read attempt {attempt + 1} failed: {e}")
                self.data = {}
                time.sleep(delay)
        else:
            print("Failed to load energy_status.json after multiple attempts")
            self.data = {}

        # Handle pickle file (less likely to fail, but still good to wrap)
        try:
            with open('data/saved_data.pkl', 'rb') as f:
                file_content = f.read()
                self.state = pickle.loads(file_content) if file_content else {}
        except (FileNotFoundError, pickle.UnpicklingError, EOFError) as e:
            print(f"Pickle load failed: {e}")
            self.state = {}

def update_data_periodically():
    while True:
        data_manager.read_json_file()
        time.sleep(20)

@app.route('/')
def index():
    power_current_mean = int(data_manager.data.get('power_current_mean', 0))
    third_highest_power = int(data_manager.data.get('third_highest_power', 0))
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

    # Fontsize
    title_fontsize = 24
    label_fontsize = 20


    # Unzip the data into datetime and power lists
    datetime_list, power_list = zip(*data_manager.data.get('power_current_list', []))
    
    # Convert datetime strings to datetime objects
    datetime_list = [datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f') for datetime_str in datetime_list]

    mean_power = data_manager.data.get('power_current_mean', 0)

    # Two plots in one figure
    fig, axs = plt.subplots(4, 1, figsize=(16, 8))  # Increase figure size
    axs = axs.flatten()

    axs[0].plot(datetime_list, power_list, label='Current power')
    axs[0].set_title('Hour', fontsize=title_fontsize)  # Increase title font size
    axs[0].set_xlabel('Time', fontsize=label_fontsize)  # Increase x-axis label font size
    axs[0].set_ylabel('Power', fontsize=label_fontsize)  # Increase y-axis label font size
    # Horizontal lines for the third highest power
    third_highest_power = data_manager.data.get('third_highest_power', 0)
    axs[0].axhline(third_highest_power, color='red', linestyle='--', label='Third Highest Power')
    axs[0].axhline(mean_power, color='green', linestyle='--', label='Mean Power')
    axs[0].legend()
    axs[0].grid(True)


    # Plot month list is not empty
    if data_manager.data.get('power_month_list'):
        month_list, month_power_list = zip(*data_manager.data.get('power_month_list', []))
        month_list = pd.to_datetime(month_list, format='ISO8601').tolist()
        #month_list = [datetime.strptime(month_str, '%Y-%m-%d %H:%M:%S.%f') for month_str in month_list]
        axs[1].bar(month_list, month_power_list, label='Month', width=0.03)
        # Horizontal lines for the third highest power
        axs[1].axhline(third_highest_power, color='red', linestyle='--', label='Third Highest Power')
        axs[1].set_title('Power Month List', fontsize=title_fontsize)
        axs[1].set_xlabel('Time', fontsize=label_fontsize)
        axs[1].set_ylabel('Power', fontsize=label_fontsize)
        axs[1].legend()

    # Plot cost list
        
    datetime_list, cost_list = zip(*data_manager.data.get('cost_hour_list', []))
    datetime_list = [datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f') for datetime_str in datetime_list]
    axs[2].plot(datetime_list, cost_list, label='Cost')
    axs[2].set_title('Cost', fontsize=title_fontsize)    
    axs[2].set_xlabel('Time', fontsize=label_fontsize)
    axs[2].set_ylabel('Cost', fontsize=label_fontsize)
    axs[2].legend()
    axs[2].grid(True)

    # Plot month cost list if not empty
    if data_manager.data.get('cost_month_list'):
        month_cost_list, month_cost_power_list = zip(*data_manager.data.get('cost_month_list', []))
        month_cost_list = pd.to_datetime(month_cost_list, format='ISO8601').tolist()
        #month_cost_list = [datetime.strptime(month_str, '%Y-%m-%d %H:%M:%S.%f') for month_str in month_cost_list]
        axs[3].bar(month_cost_list, month_cost_power_list, label='Month', width=0.03)
        axs[3].legend()
        axs[3].set_title('Cost Month List', fontsize=title_fontsize)
        axs[3].set_xlabel('Time', fontsize=label_fontsize)
        axs[3].set_ylabel('Cost', fontsize=label_fontsize)
        axs[3].grid(True)
    # Set x-axis date format
   
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
    data_manager = DataManager()
    threading.Thread(target=update_data_periodically, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=True)
