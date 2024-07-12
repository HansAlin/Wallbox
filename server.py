from flask import Flask, render_template, request, jsonify, redirect
import datetime
import time
from werkzeug.utils import secure_filename
import os


auto_Sts = 1
full_Sts = 0
fast_smart_Sts = 0
now_Sts = 0
set_time = 12
hours = 5
soc = 0
ac = 0

app = Flask(__name__)

@app.route('/')
def index():
	global set_time
	global hours
	global auto_Sts
	global full_Sts
	global fast_smart_Sts
	global now_Sts
	global soc
	global ac

	templateData = {
			'title' : 'Charger',
			'auto' : auto_Sts,
			'full': full_Sts,
			'fast_smart' : fast_smart_Sts,
			'on': now_Sts,
			'hours':hours,
			'set_time': set_time,
			'image_filename': 'image.png',
			'soc': soc,
			'ac': ac
			}

	return render_template('index.html',  **templateData)

@app.route('/<deviceName>/<action>')
def action(deviceName, action):
	global auto_Sts
	global full_Sts
	global fast_smart_Sts
	global now_Sts
	global hours
	global set_time
	global soc
	global ac


	if deviceName == 'auto':

		if action == 'on':
			print(f'Auto is on!')
			auto_Sts = 1
			full_Sts = 0
			fast_smart_Sts = 0
			now_Sts = 0
		if action == 'off':
			print(f'Auto is off!')
			auto_Sts = 0

	if deviceName == 'full':

		if action == 'on':
			print("Charging to full!")
			full_Sts = 1
			auto_Sts = 0
			fast_smart_Sts = 0
			now_Sts = 0
		if action == 'off':
			print("Not charging to full!")
			full_Sts = 0

	if deviceName == 'fast_smart':

		if action == 'on':
			print("Fast smart is on!")
			fast_smart_Sts = 1
			auto_Sts = 0
			full_Sts = 0
			now_Sts = 0
		if action == 'off':
			print("Fast smart is off!")
			fast_smart_Sts = 0

	if deviceName == 'now':

		if action == 'on':
			print("Charging now!")
			now_Sts = 1
			fast_smart_Sts = 0
			full_Sts = 0
			auto_Sts = 0
		if action == 'off':
			print('Not  charging on demand')
			now_Sts = 0

	if deviceName == 'ac':
		
		if action == 'on':
			print("Climate is on and mode to now!")
			ac = 1
			fast_smart_Sts = 0
			full_Sts = 0
			auto_Sts = 0
			now_Sts = 1

		if action == 'off':
			print('Climate is off and mode to auto!')
			ac = 0
			fast_smart_Sts = 0
			full_Sts = 0
			auto_Sts = 1
			now_Sts = 0


	templateData = {
		'auto' : auto_Sts,
		'full': full_Sts,
		'fast_smart' : fast_smart_Sts,
		'on' : now_Sts,
		'hours' : hours,
		'set_time': set_time,
		'soc': soc,
		'ac': ac
		}
	
	return render_template('index.html', **templateData)



@app.route('/get_status', methods=['GET'])
def get_status():
	global auto_Sts
	global fast_smart_Sts
	global now_Sts
	global full_Sts
	global hours
	global set_time
	global soc
	global ac

	templateData = {
			'auto': auto_Sts,
			'full': full_Sts,
			'fast_smart':fast_smart_Sts,
			'on': now_Sts,
			'hours':hours,
			'set_time': set_time,
			'soc': soc,
			'ac': ac
				}
	return jsonify(templateData)  # Convert the templateData dictionary to JSON and return it

@app.route('/set_value', methods=['POST'])
def set_value():
	global hours
	new_value = request.form['hours']
	try:
		hours = int(new_value)
	except ValueError:
		hours ="0"
	return redirect('/')

@app.route('/set_time', methods=['POST'])
def update_time():
    set_time = int(request.form.get('set_time')[:2])  # Extract hours from "HH:00"
    templateData = {
        'title' : 'Charger',
        'auto' : auto_Sts,
        'full': full_Sts,
        'fast_smart' : fast_smart_Sts,
        'on': now_Sts,
        'hours':hours,
        'set_time': set_time,
        'image_filename': 'image.png',
        'soc': soc,
        'ac': ac
    }
    return render_template('index.html',  **templateData)

@app.route('/set_state', methods=['POST'])
def set_state():
	global auto_Sts
	global full_Sts
	global fast_smart_Sts
	global now_Sts
	global set_time
	global hours
	global soc
	global ac

	data = request.get_json()

	if data:
		if 'auto' in data:
			auto_Sts = data['auto']
		if 'full' in data:
			full_Sts = data['full']	
		if 'fast_smart' in data:
			fast_smart_Sts = data['fast_smart']
		if 'on' in data:
			now_Sts = data['on']		
		if 'hours' in data:
			hours = data['hours']	
		if 'set_time' in data:
			set_time = data['set_time']
		if 'soc' in data:
			soc = data['soc']	
		if 'ac' in data:
			ac = data['ac']	

	templateData = {
		'auto' : auto_Sts,
		'full': full_Sts,
		'fast_smart' : fast_smart_Sts,
		'on' : now_Sts,
		'set_time': set_time,
		'hours' : hours,
		'soc': soc,
		'ac': ac
		}		
	
	return render_template('index.html', **templateData)

@app.route('/set_time', methods=['POST'])
def set_time_route():
	global set_time
	selected_time = request.form['set_time']
	set_time, _ = map(int, selected_time.split(':'))  # split the selected time into hours and minutes

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




