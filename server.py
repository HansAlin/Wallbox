from flask import Flask, render_template, request, jsonify, redirect, send_file
import os
import matplotlib
from matplotlib.figure import Figure
matplotlib.use('Agg') 
from werkzeug.utils import secure_filename
import pickle
import time
import threading
import matplotlib.pyplot as plt
import hashlib
import json



import GARO.garo as garo

import io
import pandas as pd
import numpy as np

app = Flask(__name__)

# Define default settings
DEFAULT_SETTINGS = {
    'auto': 1,
    'fast_smart': 0,
    'manual': 0,
    'hours': 5,
    'set_time': 12,
    'fas_value': 1,
    'kwh_per_week': 50,
    'status': 'Not updated',
    'charging_power': 0,
    'energy': 0,
    'charge_status': 0,
    'max_power': 3000

}

SETTINGS_FILE = 'web_data.txt'
PICKLE_FILE = 'data/saved_data.pkl'
UPDATE_INTERVAL = 20  # seconds
data_lock = threading.Lock()
plot_image = None
last_data_hash = None
last_update = 0
settings_lock = threading.Lock()

settings = {}
state = {}

def update_file(settings):
    """Save settings to file. Caller must hold settings_lock."""
    try:
        print("Saving settings:", settings)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except IOError as e:
        print(f"Error writing to file: {e}")



def read_pkl_file():
    global state, plot_image
    try:
        with open(PICKLE_FILE, 'rb') as f:
            new_state = pickle.load(f)

        with data_lock:
            state = new_state
            if 'nordpool' in state and not state['nordpool'].empty:
                state['nordpool']['TimeStamp'] = pd.to_datetime(state['nordpool']['TimeStamp'])
            else:
                print("Nordpool data is missing or empty.")

            if 'schedule' in state and not state['schedule'].empty:
                state['schedule']['TimeStamp'] = pd.to_datetime(state['schedule']['TimeStamp'])
            else:
                print("Schedule data is missing or empty.")

            plot_image = None  # Clear cached plot

    except (IOError, pickle.UnpicklingError) as e:
        print(f"Error reading pickle file: {e}")
        with data_lock:
            state = {}
            plot_image = None


def read_garo_values():
    global settings
    charging_power = garo.get_current_power()
    energy = garo.get_accumulated_energy()
    charge_status = garo.get_status('chargeStatus')

    with settings_lock:
        settings['charging_power'] = float(charging_power) if hasattr(charging_power, 'item') else charging_power
        settings['energy'] = float(energy) if hasattr(energy, 'item') else energy
        settings['charge_status'] = int(charge_status) if hasattr(charge_status, 'item') else charge_status


def update_periodically():
    global plot_image, last_data_hash
    
    while True:
        read_pkl_file()
        read_garo_values()
        
        # Generate plot in background if data changed
        with data_lock:
            nordpool = state.get('nordpool', pd.DataFrame())
            schedule = state.get('schedule', pd.DataFrame())
        
        if not nordpool.empty:
            current_hash = get_data_hash(nordpool, schedule)
            if current_hash != last_data_hash:
                try:
                    with data_lock:
                        plot_image = generate_plot(nordpool, schedule)
                        last_data_hash = current_hash
                    print(f"Plot regenerated at {time.strftime('%H:%M:%S')}")
                except Exception as e:
                    print(f"Error generating plot: {e}")
            else:
                print("No changes detected, plot not regenerated.")
        
        time.sleep(UPDATE_INTERVAL)

def load_settings():
    """Load settings from file and update global dict in place"""
    global settings
    try:
        with open(SETTINGS_FILE, 'r') as f:
            new_settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        new_settings = DEFAULT_SETTINGS.copy()
        print("⚠ reload settings from file!", new_settings)
        update_file(new_settings)

    # Update the existing dict in place instead of replacing it
    with settings_lock:
        settings.clear()
        settings.update(new_settings)

        # Ensure all default keys exist
        for key, value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = value

    return settings


settings = load_settings()

@app.route('/')
def index():
    global settings
    print("Index route triggered")  # Debug print
    print(f"Settings passed to template: {settings}")
    return render_template('index.html', title='Charger', image_filename='image.png', **settings)

# @app.route('/set_time', methods=['POST'])
# def update_set_time():
#     # 1. Get the raw value
#     new_time = request.form.get('set_time')
#     print(f"DEBUG: Raw form data received: '{new_time}'") 

#     if not new_time:
#         print("DEBUG: Error - Input was empty!")
#         return redirect('/')

#     try:
#         # 2. Clean the data (Handle both "14" and "14:00")
#         clean_time = new_time.split(":")[0]
        
#         with settings_lock:
#             settings['set_time'] = int(clean_time)
#             print(f"DEBUG: Success! Updated settings['set_time'] to: {settings['set_time']}")
#             update_file(settings)
            
#     except Exception as e:
#         # 3. Catch the specific error so we know WHY it failed
#         print(f"DEBUG: CRASH detected! Error: {e}")
#         # Don't reset to default here, so we can see the value persist if it worked partly
        
#     return redirect('/')

@app.route('/set_state', methods=['POST'])
def set_state():
    data = request.get_json()
    if not data:
        return "No data provided", 400

    with settings_lock:
        for key, value in data.items():
            if key in DEFAULT_SETTINGS:
                # Only update non-mode keys
                if key not in ['auto', 'fast_smart', 'manual']:
                    settings[key] = value
        update_file(settings)
    return jsonify(settings), 200


@app.route('/<mode>/<action>')
def toggle_mode(mode, action):
    ALLOWED_MODES = ['auto', 'fast_smart', 'manual']  # better naming
    print('In change state!')
    print(f"Toggling {mode} {action}")  # <- debug
    if mode not in ALLOWED_MODES:
        return f"Invalid mode: {mode}", 400

    if action not in ['on', 'off']:
        return f"Invalid action: {action}", 400

    with settings_lock:
        if action == 'on':
            # Turn all other modes off
            for m in ALLOWED_MODES:
                settings[m] = 0
            settings[mode] = 1
        else:
            settings[mode] = 0
        print('Updating settings!')
        update_file(settings)

    return redirect('/')



@app.route('/get_status', methods=['GET'])
def get_status():
    with settings_lock:
        safe_settings = {k: v for k, v in settings.items()}
    return jsonify(safe_settings)

@app.route('/set_value', methods=['POST'])
def set_value():
    for key in ['hours', 'fas_value', 'kwh_per_week', 'set_time', 'max_power']:
        if key in request.form:
            try:
                if key == 'set_time':
                    clean_time = request.form[key].split(":")[0]
                    settings[key] = int(clean_time)
                else:    
                   settings[key] = int(request.form[key])
            except ValueError:
                settings[key] = DEFAULT_SETTINGS[key]

    update_file(settings)
    return redirect('/')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    with settings_lock:
        for key in ['hours', 'fas_value', 'kwh_per_week', 'set_time', 'max_power']:
            if key in request.form:
                value = request.form[key]
                if key == 'set_time':
                    try:
                        settings[key] = int(value.split(":")[0])
                    except:
                        settings[key] = DEFAULT_SETTINGS[key]
                else:
                    try:
                        settings[key] = int(value)
                    except:
                        settings[key] = DEFAULT_SETTINGS[key]
        update_file(settings)
    return redirect('/')




@app.route('/plot.png')
def plot_png(): 
    global plot_image
    
    # If no cached image, generate one immediately
    if plot_image is None:
        with data_lock:
            nordpool = state.get('nordpool', pd.DataFrame())
            schedule = state.get('schedule', pd.DataFrame())
        
        if nordpool.empty:
            return "No data available", 404
            
        try:
            plot_image = generate_plot(nordpool, schedule)
            print("Plot generated on demand in /plot.png")
        except Exception as e:
            print(f"Error generating plot: {e}")
            return "Error generating plot", 500
    
    return send_file(io.BytesIO(plot_image), mimetype='image/png')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return "No image in request", 400
    image = request.files['image']
    filename = secure_filename(image.filename)
    if filename == '':
        return "Invalid image filename", 400
    image.save(os.path.join('static', filename))
    return '', 200

def generate_plot(nordpool, schedule):
    """Generate plot image and return as bytes"""
    value = nordpool['value'].values
    time = nordpool['TimeStamp'].values
    
    # Convert schedule times to set for O(1) lookup
    schedule_times = set()
    if not schedule.empty:
        schedule_times = set(schedule['TimeStamp'].values)
    
    now = pd.Timestamp.now()
    
    fig = Figure(figsize=(10, 5))
    axs = fig.subplots()
    
    # More efficient plotting - separate green and blue bars
    green_times = []
    green_values = []
    blue_times = []
    blue_values = []
    
    for t, v in zip(time, value):
        if t in schedule_times:
            green_times.append(t)
            green_values.append(v)
        else:
            blue_times.append(t)
            blue_values.append(v)
    
    if len(time) > 1:
        # Average spacing between timestamps
        avg_delta = np.mean(np.diff(time).astype('timedelta64[m]').astype(float))  # minutes
        width = np.timedelta64(int(avg_delta), 'm')
    else:
        width = np.timedelta64(60, 'm')  # fallback 1 hour


    # green_times_shifted = [t + width for t in green_times]
    # blue_times_shifted  = [t + width for t in blue_times]


    # Plot all bars at once
    if green_times:
        axs.bar(green_times, green_values, width=width, color='green', align='edge')
    if blue_times:
        axs.bar(blue_times, blue_values, width=width, color='blue', align='edge')
    
    axs.axvline(now, color='red', linestyle='--', label=f'Now: {now.strftime("%H:%M")}')
    axs.set_title('Price Nordpool', fontsize=24)
    axs.set_xlabel('Time', fontsize=20)
    axs.set_ylabel('Öre', fontsize=20)
    axs.legend()
    axs.grid(True)
    fig.tight_layout()
    
    img = io.BytesIO()
    fig.savefig(img, format='png', dpi=100)  # Lower DPI for faster generation
    img.seek(0)
    img_data = img.read()

    
    return img_data

def get_data_hash(nordpool, schedule):
    """Generate hash to detect data changes"""
    if nordpool.empty:
        return "empty"
    
    # Convert DataFrames to strings for hashing
    nordpool_str = nordpool.to_csv(index=False)
    schedule_str = schedule.to_csv(index=False) if not schedule.empty else ""
    
    # Create hash from the combined string
    data_str = nordpool_str + schedule_str
    return hashlib.md5(data_str.encode()).hexdigest()

if __name__ == '__main__':
    # FIX: Prevent double execution of thread
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        threading.Thread(target=update_periodically, daemon=True).start()
        
    read_pkl_file()
    # FIX: use_reloader=False is safer if you are using threads in main
    app.run(debug=True, port=5000, host='0.0.0.0', use_reloader=False)