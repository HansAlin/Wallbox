from flask import Flask, render_template, request, jsonify, redirect, send_file
import os
import matplotlib
matplotlib.use('Agg') 
from werkzeug.utils import secure_filename
import pickle
import time
import threading
import matplotlib.pyplot as plt

import io
import pandas as pd

app = Flask(__name__)

# Define default settings
DEFAULT_SETTINGS = {
    'auto': 1,
    'full': 0,
    'fast_smart': 0,
    'on': 0,
    'hours': 5,
    'set_time': 12,
    'fas_value': 1,
    'kwh_per_week': 50,
    'status': 'Hej'
}

def update_file(settings):
    try:
        with open('web_data.txt', 'w') as f:
            for key in DEFAULT_SETTINGS:
                f.write(str(settings[key]) + '\n')
    except IOError as e:
        print(f"Error writing to file: {e}")

def read_pkl_file():

    global state
    with open('data/saved_data.pkl', 'rb') as f:
        file_content = f.read()
        state = pickle.loads(file_content)
    state['nordpool']['TimeStamp'] = pd.to_datetime(state['nordpool']['TimeStamp'])	    

def update_periodically():
    while True:
        read_pkl_file()
        time.sleep(20)  # Wait for 20 seconds


# Initialize settings from file or use defaults
def load_settings():
    try:
        with open('web_data.txt', 'r') as f:
            lines = f.readlines()
            if len(lines) != len(DEFAULT_SETTINGS):
                raise ValueError("File content does not match expected format.")
            settings = {}
            for key, value in zip(DEFAULT_SETTINGS.keys(), lines):
                if key == 'status':
                    settings[key] = value.strip()
                else:
                    settings[key] = int(value.strip())
    except (FileNotFoundError, ValueError, IndexError):
        settings = DEFAULT_SETTINGS.copy()
        update_file(settings)
    return settings

# Load settings at startup
settings = load_settings()

@app.route('/')
def index():
    return render_template('index.html', title='Charger', image_filename='image.png', **settings)

@app.route('/<deviceName>/<action>')
def action(deviceName, action):
    if action == 'on':
        settings.update({key: 0 for key in settings.keys() if key not in ['hours', 'set_time', 'fas_value', 'kwh_per_week', 'status']})
        settings[deviceName] = 1
    elif action == 'off':
        settings[deviceName] = 0

    update_file(settings)
    return render_template('index.html', **settings)

@app.route('/get_status', methods=['GET'])
def get_status():
    return jsonify(settings)

@app.route('/set_value', methods=['POST'])
def set_value():
    if 'hours' in request.form:
        try:
            settings['hours'] = int(request.form['hours'])
        except ValueError:
            settings['hours'] = DEFAULT_SETTINGS['hours']

    if 'fas_value' in request.form:
        try:
            settings['fas_value'] = int(request.form['fas_value'])
        except ValueError:
            settings['fas_value'] = DEFAULT_SETTINGS['fas_value']

    if 'kwh_per_week' in request.form:
        try:
            settings['kwh_per_week'] = int(request.form['kwh_per_week'])
        except ValueError:
            settings['kwh_per_week'] = DEFAULT_SETTINGS['kwh_per_week']

    update_file(settings)
    return redirect('/')

@app.route('/set_time', methods=['POST'])
def update_set_time():
    new_time = request.form.get('set_time', '')
    try:
        settings['set_time'] = int(new_time.split(":")[0])
    except ValueError:
        settings['set_time'] = DEFAULT_SETTINGS['set_time']

    update_file(settings)
    return redirect('/')

@app.route('/set_state', methods=['POST'])
def set_state():
    data = request.get_json()
    if data:
        for key in ['auto', 'full', 'fast_smart', 'on', 'hours', 'set_time', 'status']:
            if key in data:
                settings[key] = data[key]
    update_file(settings)
    return jsonify(settings)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return "No image in request", 400
    image = request.files['image']
    filename = secure_filename(image.filename)
    image.save(os.path.join('static', filename))
    return '', 200

@app.route('/plot.png')
def plot_png(): 
    nordpool = state['nordpool']
    value = nordpool['value'].values
    time = nordpool['TimeStamp'].values
    
    schedule = state['schedule']
    # Schedule is not empty mark the schedule times in the plot green
    if not schedule.empty:
        schedule['TimeStamp'] = pd.to_datetime(schedule['TimeStamp'])
        schedule_times = schedule['TimeStamp'].values
    else:
        schedule_times = []

    now = pd.to_datetime('now')

    fig, axs = plt.subplots(1, 1, figsize=(10, 5))
    
    # Plot bars with different colors based on schedule match
    for t, v in zip(time, value):
        if t in schedule_times:
            axs.bar(t, v, width=0.03, color='green')
        else:
            axs.bar(t, v, width=0.03, color='blue')
    axs.axvline(now, color='red', linestyle='--', label='Now')
    axs.set_title('Price Nordpool', fontsize=24)
    axs.set_xlabel('Time', fontsize=20)
    axs.set_ylabel('Öre', fontsize=20)
    axs.legend()
    axs.grid(True)
    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    # Start the periodic update in a separate thread
    threading.Thread(target=update_periodically, daemon=True).start()
    read_pkl_file()
    app.run(debug=True, port=5000, host='0.0.0.0')