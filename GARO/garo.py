
import sys
import os

import requests
from CONFIG.config import url_garo
import json
import random
import time





def get_Garo_status(test=False):  
	"""
	This function check if car is connected to GARO
	Return: 
	connection : connection type
	available : if available


	"""
	if test:
		return 'CONNECTED', 'ALWAYS_OFF'

	status_path = "data/garo_status.json"

	try:
		with open(status_path, 'r') as f:
			data = json.load(f)

		print(f"From Garo: {data['connector']} and {data['mode']}", end=" ")
		if data['connector'] == 'CHARGING_PAUSED':
			data['connector'] = "CONNECTED"
		return data['connector'], data['mode']
	except:
		print("Not able to contact wallbox!", end=" ")
		return None, None
	
def get_soc():
	# First turn on the charger
	mode = get_Garo_status('mode')
	if mode != 'ALWAYS_ON':
		on_off_Garo('1')
	# Delay to allow the charger to start
	time.sleep(30)
	# Get the status of the charger
	state = get_Garo_status('chargeStatus')
	time.sleep(30)
	if mode == 'ALWAYS_OFF':
		on_off_Garo('0')
		print("Charger is turned off after getting SOC.")
	elif mode == 'SCHEMA':
		on_off_Garo('2')
		print("Charger is set to schema after getting SOC.")
	elif mode == 'ALWAYS_ON':
		print("Charger is left on after getting SOC.")


	return state


def update_Garo_state(verbose=False):

	try:
		url = f"{url_garo}/servlet/rest/chargebox/config"
		response = requests.get(url=url, timeout=30)
		config = response.json()
		with open('data/garo_config.json', 'w') as f:
			json.dump(config, f, indent=4)
		if verbose:
			print(json.dumps(config, indent=4))	

	except Exception as e:
		print(f'Not able to get config in GARO! {e}', end=" ")

	try:
		url = f"{url_garo}/servlet/rest/chargebox/meterinfo/EXTERNAL"
		response = requests.get(url=url, timeout=30)
		meterinfo = response.json()
		with open('data/garo_meterinfo.json', 'w') as f:
			json.dump(meterinfo, f, indent=4)
		if verbose:
			print(json.dumps(meterinfo, indent=4))	

	except Exception as e:
		print(f'Not able to get meterinfo in GARO! {e}', end=" ")

	try:
		url = f"{url_garo}/servlet/rest/chargebox/status?_=1"
		response = requests.get(url=url, timeout=30)
		status = response.json()
		with open('data/garo_status.json', 'w') as f:
			json.dump(status, f, indent=4)
		if verbose:
			print(json.dumps(status, indent=4))
	except Exception as e:
		print(f'Not able to get status in GARO! {e}', end=" ")

# def get_Garo_status(state=None, verbose=False):
# 	"""
# 	This function returns the status of the GARO charger
# 	"""
# 	try:
# 		with open('data/garo_status.json', 'r') as f:
# 			data = json.load(f)
# 		if verbose:
# 			print(data)
# 		if state is not None:
# 			status = data.get(state)
# 			if verbose:
# 				print(f"Status of state {state}: {status}", end=" ")
# 	except Exception as e:
# 		print(f'Not able to load status in GARO! {e}', end=" ")
# 		status = None

def get_meterinfo(state, verbose=False):
	"""
	This function returns the status of the GARO charger
	"""
	try:
		with open('data/garo_meterinfo.json', 'r') as f:
			data = json.load(f)
		if verbose:
			print(data)
		if state is not None:
			status = data.get(state)
			if verbose:
				print(f"Status of state {state}: {status}", end=" ")
	except Exception as e:
		print(f'Not able to load meterinfo in GARO! {e}', end=" ")
		data = None		

def get_garo_state():

	try:
		with open('data/garo_config.json', 'r') as f:
			config = json.load(f)
	except Exception as e:
		print(f'Not able to load config in GARO! {e}', end=" ")
		config = None
	try:
		with open('data/garo_meterinfo.json', 'r') as f:
			meterinfo = json.load(f)
	except Exception as e:
		print(f'Not able to load meterinfo in GARO! {e}', end=" ")
		meterinfo = None
	try:
		with open('data/garo_status.json', 'r') as f:
			status = json.load(f)
	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
		status = None

	return config, meterinfo, status

def get_charge_status():
	try:
		with open('data/garo_status.json', 'r') as f:
			data = json.load(f)
			charge_status = data['mainCharger'].get('chargeStatus')
			
	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
		status = None

	return charge_status	

def get_current_power():
	try:
		with open('data/garo_status.json', 'r') as f:
			data = json.load(f)
			power = data['mainCharger'].get('currentChargingPower')

	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
		power = None

	return power	

def get_accumulated_energy(): 

	try:
		with open('data/garo_status.json', 'r') as f:
			data = json.load(f)
			energy = data['mainCharger'].get('accSessionEnergy')

	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
		energy = None

	return energy	

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

	meterinfo_path = "data/garo_meterinfo.json"

	try:
		with open(meterinfo_path, 'r') as f:
			data = json.load(f)

			
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


def get_Garo_current_limit():
	config_path = "data/garo_config.json"

	try:
		with open(config_path, 'r') as f:
			config = json.load(f)

		charge_current = config["reducedCurrentIntervals"][0].get("chargeLimit")
		currentChargingCurrent = config["slaveList"][0].get("currentChargingCurrent")
	except Exception as e:
		print(f'Not able to get current limit in GARO! {e}', end=" ")
		charge_current = 13

	return charge_current, currentChargingCurrent

def set_Garo_current(value, retries=3, delay=2):
	"""
	This function sets the current in GARO with improved error handling and retry logic.
	"""
	# Ensure the value is within the allowed range
	value = max(6, min(value, 13))

	config_url = f"{url_garo}/servlet/rest/chargebox/config"

	# Retry logic for GET request
	for attempt in range(retries):
			try:
					response = requests.get(config_url, timeout=5)
					response.raise_for_status()  # Raise HTTPError for bad responses (4xx, 5xx)
					break
			except requests.exceptions.ConnectionError as e:
					print(f"Connection error: {e}. Retrying ({attempt + 1}/{retries})...")
					time.sleep(delay)
			except requests.exceptions.Timeout as e:
					print(f"Timeout error: {e}. Retrying ({attempt + 1}/{retries})...")
					time.sleep(delay)
			except requests.exceptions.RequestException as e:
					print(f"Failed to get config: {e}")
					return
	else:
			print("Max retries exceeded for GET request.")
			return

	config = response.json()

	# Modify the configuration
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

	post_url = f"{url_garo}/servlet/rest/chargebox/currentlimit"
	headers = {"Content-Type": "application/json"}

	# Retry logic for POST request
	for attempt in range(retries):
			try:
					post_response = requests.post(post_url, headers=headers, data=json.dumps(config), timeout=5)
					post_response.raise_for_status()  # Raise HTTPError for bad responses
					print(f"Successfully set current limit to {value}A")
					return
			except requests.exceptions.ConnectionError as e:
					print(f"Connection error: {e}. Retrying ({attempt + 1}/{retries})...")
					time.sleep(delay)
			except requests.exceptions.Timeout as e:
					print(f"Timeout error: {e}. Retrying ({attempt + 1}/{retries})...")
					time.sleep(delay)
			except requests.exceptions.RequestException as e:
					print(f"Failed to set current limit: {e}")
					return
	else:
			print("Max retries exceeded for POST request.")

def get_charge_current(verbose=False):
	"""
	This function retrieves the current charging current from a local JSON file.
	"""
	status_path = "data/garo_status.json"
	try:
			with open(status_path, 'r') as f:
					data = json.load(f)

			charge_current = data['mainCharger'].get('currentChargingCurrent')
			if verbose:
					print(f"Current charging current: {charge_current}")
			return charge_current
	except FileNotFoundError:
			print(f"Status file not found: {status_path}")
	except json.JSONDecodeError:
			print(f"Error decoding JSON from {status_path}")
	except Exception as e:
			print(f"Unexpected error: {e}")
	return None

def get_status(state, verbose=False):
	"""
	This function returns the status of the GARO charger
	"""

	try:
		with open('data/garo_status.json', 'r') as f:
			data = json.load(f)
		status = data.get(state)
		if verbose:
			print(data)
			print(f"Status of state {state}: {status}", end=" ")
	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
		status = None

	return status



if __name__ == '__main__':
	

	#set_Garo_current(6)
	#get_current_consumtion()
	#on_off_Garo('2')
	# get_Garo_status()
	# value = get_Garo_current_limit()
	# print(value)
	update_Garo_state()

	soc = get_soc()
	print(f"State of charge: {soc}")



  