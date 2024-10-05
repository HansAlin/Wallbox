from flask import Flask, render_template, request, jsonify, redirect
import os
from werkzeug.utils import secure_filename

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
    'kwh_per_week': 50
}
def update_file(settings):
    try:
        with open('web_data.txt', 'w') as f:
            for key in DEFAULT_SETTINGS:
                f.write(str(settings[key]) + '\n')
    except IOError as e:
        print(f"Error writing to file: {e}")

# Initialize settings from file or use defaults
def load_settings():
    try:
        with open('web_data.txt', 'r') as f:
            # Read lines and convert them to integers
            lines = f.readlines()
            if len(lines) != len(DEFAULT_SETTINGS):
                raise ValueError("File content does not match expected format.")
            settings = {key: int(value.strip()) for key, value in zip(DEFAULT_SETTINGS.keys(), lines)}
    except (FileNotFoundError, ValueError, IndexError):
        # Use default settings if file is missing or content is invalid
        settings = DEFAULT_SETTINGS
        # Optionally, initialize the file with default settings
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
        settings.update({key: 0 for key in settings.keys() if key not in ['hours', 'set_time', 'fas_value', 'kwh_per_week']})
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

# @app.route('/set_state', methods=['POST'])
# def set_state():
#     global auto_Sts, full_Sts, fast_smart_Sts, now_Sts, set_time, hours
#     data = request.get_json()
#     if data:
#         if 'auto' in data:
#             auto_Sts = data['auto']
#         if 'full' in data:
#             full_Sts = data['full']    
#         if 'fast_smart' in data:
#             fast_smart_Sts = data['fast_smart']
#         if 'on' in data:
#             now_Sts = data['on']        
#         if 'hours' in data:
#             hours = data['hours']    
#         if 'set_time' in data:
#             set_time = data['set_time']
#     update_file()
#     return redirect('/')

@app.route('/set_state', methods=['POST'])
def set_state():
    data = request.get_json()
    if data:
        for key in ['auto', 'full', 'fast_smart', 'on', 'hours', 'set_time']:
            if key in data:
                settings[key] = data[key]
    update_file(settings)
    return redirect('/')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return "No image in request", 400
    image = request.files['image']
    filename = secure_filename(image.filename)
    image.save(os.path.join('static', filename))
    return '', 200

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
