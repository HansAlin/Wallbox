import requests
from CONFIG.config import url_garo

import random

def get_Garo_status(test=False):
	"""
	This function check if car is connected to GARO
	Return: 
	connection : connection type
	available : if available


	"""
	if test:
		return 'CONNECTED', 'ALWAYS_OFF'

	try:
		url = url_garo + '/servlet/rest/chargebox/status?_=1'
		response = requests.get(url=url, timeout=30)
		data = response.json()

		print(f"From Garo: {data['connector']} and {data['mode']}", end=" ")
		if data['connector'] == 'CHARGING_PAUSED':
			data['connector'] = "CONNECTED"
		return data['connector'], data['mode']
	except:
		print("Not able to contact wallbox!", end=" ")
		return None, None
	
def get_current_consumtion(test=False):
	"""
	This function check the power consumtion
	Return: 
	power : power consumtion in kW
	"""
	# TODO remove
	# For raspberry pi 
	# r'/usr/bin/chromedriver'
	
	if test:
		return {'fas1': random.random()*10, 'fas2': random.random()*10, 'fas3': random.random()*10}	

	meterinfo_url = url_garo + '/servlet/rest/chargebox/meterinfo/EXTERNAL'

	try:
		response = requests.get(meterinfo_url)
		# Check response
		if response.status_code != 200:
				raise Exception(f"Failed to get meter info: {response.status_code}, {response.text}")

		# Parse JSON
		data = response.json()
			
		phase1Current = data.get('phase1Current')
		phase2Current = data.get('phase2Current')
		phase3Current = data.get('phase3Current')
		readTime = data.get('readTime')
 

		phase1Current = float(phase1Current)/10
		phase2Current = float(phase2Current)/10
		phase3Current = float(phase3Current)/10

		print(f'1: {phase1Current:>5.1f} A, 2: {phase2Current:>5.1f} A, 3: {phase3Current:>5.1f} A, {readTime}', end=" ")

		return {'fas1':phase1Current, 'fas2':phase2Current, 'fas3':phase3Current, 'readTime':readTime}
	except Exception as e:
		print(f'Not able to update status in GARO!', end=" ")




def on_off_Garo(value):
	"""
	This function takes the argument value and sets 
	the Garo Charger to: "1" = on, "0" = off, "2" = Schedule
	"""	

	if value == '1':
		value = 'ALWAYS_ON'
	elif value == '0':
		value = 'ALWAYS_OFF'
	elif value == '2':
		value = 'SCHEMA'

	# The URL to which the POST request will be sent
	url = url_garo + '/servlet/rest/chargebox/mode/' + value

	# Optional: Data you want to send with the request (if any)
	# For example, if you need to send a specific payload, include it here.
	# If no data is needed, you can omit this or send an empty dictionary.
	data = {
			'mode': value  # The data to send (if required by the API)
	}
	try:
		# Sending a POST request to the URL
		response = requests.post(url, data=data)

		# Check if the request was successful
		if response.status_code == 200:
				print('Request successful!')
				print('Response:', response.text)  # Optional: print the response from the server
		else:
				print(f'Error: {response.status_code}')
				print('Response:', response.text)  # Print response to debug
	except requests.exceptions.RequestException as e:
		print(f"Error occurred: {e}")
		return None


def set_Garo_current(value):
	"""
	This function sets the current in GARO
	"""    
	# Value has to be between 6 and 13
	if value < 6:
		value = 6
	elif value > 13:
		value = 13

	config_url = f"{url_garo}/servlet/rest/chargebox/config"

	response = requests.get(config_url)
	if response.status_code != 200:
			raise Exception(f"Failed to get config: {response.status_code}, {response.text}")

	config = response.json()

	# Step 2: Modify only what you need
	config["reducedIntervalsEnabled"] = True
	config["reducedCurrentIntervals"] = [
			{
					"schemaId": 1,
					"start": "00:00:00",
					"stop": "23:59:59",
					"weekday": 8,  # possibly "every day"
					"chargeLimit": value  # new current limit
			}
	]

	# Step 3: POST the updated config
	post_url = f"{url_garo}/servlet/rest/chargebox/currentlimit"
	headers = {"Content-Type": "application/json"}

	post_response = requests.post(post_url, headers=headers, data=json.dumps(config))

	#  Check the response
	if post_response.status_code == 200:
		print(f"Successfully set current limit to {value}A", end=" ")	
	else:
		print(f"Failed to set current limit: {post_response.status_code}", end=" ")





if __name__ == '__main__':
	

	#set_Garo_current(6)
	#get_current_consumtion()
	#on_off_Garo('2')
	get_Garo_status()

  