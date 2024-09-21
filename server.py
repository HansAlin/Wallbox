from flask import Flask, render_template, request, jsonify, redirect
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Initialize global variables
try:
    with open('web_data.txt', 'r') as f:
        settings = {key: int(value) for key, value in zip(['auto', 'full', 'fast_smart', 'on', 'hours', 'set_time', 'fas_value', 'kwh_per_week'], f.readlines())}
except FileNotFoundError:
    settings = {'auto': 1, 'full': 0, 'fast_smart': 0, 'on': 0, 'hours': 5, 'set_time': 12, 'fas_value': 1, 'kwh_per_week': 50}

def update_file():
    with open('web_data.txt', 'w') as f:
        for key, value in settings.items():
            print(key, value)
            f.write(str(value) + '\n')

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

    update_file()
    return render_template('index.html', **settings)


@app.route('/get_status', methods=['GET'])
def get_status():
    return jsonify(settings)

@app.route('/set_value', methods=['POST'])
def set_value():
    global hours, fas_value, kwh_per_week

    if 'hours' in request.form:
        new_value = request.form['hours']
        try:
            hours = int(new_value)
        except ValueError:
            hours = 0
        settings['hours'] = hours

    if 'fas_value' in request.form:
        fas_value = request.form['fas_value']
        try:
            fas_value = int(fas_value)
        except ValueError:
            fas_value = 1
        settings['fas_value'] = fas_value

    if 'kwh_per_week' in request.form:
        kwh_per_week = request.form['kwh_per_week']
        try:
            kwh_per_week = int(kwh_per_week)
        except ValueError:
            kwh_per_week = 50
        settings['kwh_per_week'] = kwh_per_week

    update_file()
    return redirect('/')

@app.route('/set_time', methods=['POST'])
def set_time():
    global set_time
    new_time = request.form['set_time']
    try:
        # Extract the hour from the submitted time (format: "HH:00")
        set_time = int(new_time.split(":")[0])
    except ValueError:
        set_time = 0

    settings['set_time'] = set_time
    update_file()
    return redirect('/')


@app.route('/set_state', methods=['POST'])
def set_state():
    data = request.get_json()
    if data:
        for key in ['auto', 'full', 'fast_smart', 'on', 'hours', 'set_time']:
            if key in data:
                settings[key] = data[key]
    update_file()
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