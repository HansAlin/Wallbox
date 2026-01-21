import sys
import os
import sys
import requests
import json
import random
import time
from filelock import FileLock 
from filelock import FileLock, Timeout as FileLockTimeout
import time
import threading

from CONFIG.config import url_garo

garo_lock = threading.Lock()

def get_Garo_status(test=False, timeout=5):
	"""
	Safely read Garo charger status from JSON file.

	Returns:
		(connection, available)
		- connection: "CONNECTED", "NOT_CONNECTED", etc.
		- available: "ALWAYS_ON", "ALWAYS_OFF", etc.
	"""

	if test:
		return 'CONNECTED', 'ALWAYS_OFF'

	status_path = "data/garo_status.json"

	# Early exit if file doesn't exist
	if not os.path.exists(status_path):
		print("Status file missing!", end=" ")
		return None, None

	try:
		# Use a short timeout for file I/O — by checking modification
		start_time = time.time()
		while True:
			try:
				with open(status_path, 'r') as f:
					data = json.load(f)
				break  # success
			except json.JSONDecodeError:
				# file may still be being written to — retry a few times
				if time.time() - start_time > timeout:
					print("Timeout waiting for valid GARO status file!", end=" ")
					return None, None
				time.sleep(0.1)

		connector = data.get('connector')
		mode = data.get('mode')

		print(f"From Garo: {connector}, {mode}, {data.get('currentChargingCurrent')/1000:.1f} A", end="; ")

		# Normalize state
		if connector == 'CHARGING_PAUSED':
			connector = "CONNECTED"

		return connector, mode

	except Exception as e:
		print(f"Not able to read GARO status: {e}", end=" ")
		return None, None


def fetch_and_save_data(url, output_file, verbose=False, network_timeout=15, lock_timeout=5):
	"""
	Fetch data from a URL and save it safely to a file.
	Handles network timeouts, file locks, and atomic writes.
	"""
	try:
		# --- Fetch from network ---
		response = requests.get(url=url, timeout=network_timeout)
		response.raise_for_status()
		data = response.json()

		# --- Ensure directory exists ---
		os.makedirs(os.path.dirname(output_file), exist_ok=True)

		# --- Safe atomic write with file lock ---
		lock_file = f"{output_file}.lock"
		tmp_file = f"{output_file}.tmp"

		with FileLock(lock_file, timeout=lock_timeout):
				with open(tmp_file, 'w') as f:
						json.dump(data, f, indent=4)
				os.replace(tmp_file, output_file)

		if verbose:
				print(f"✅ Saved data to {output_file}")
				print(json.dumps(data, indent=4))

	except FileLockTimeout:
		print(f"Could not acquire file lock for {output_file} within {lock_timeout}s.")
	except requests.Timeout:
		print(f"Network timeout fetching {url} after {network_timeout}s.")
	except requests.RequestException as e:
		print(f"Network error fetching {url}: {e}")
	except json.JSONDecodeError:
		print(f"Failed to decode JSON response from {url}.")
	except Exception as e:
		print(f"Unexpected error: {e}")


def update_Garo_state(verbose=False):

	try:
			fetch_and_save_data(f"{url_garo}/servlet/rest/chargebox/config", 'data/garo_config.json', verbose)
	except Exception as e:
			print(f'Not able to get config in GARO! {e}', end=" ")

	try:
			fetch_and_save_data(f"{url_garo}/servlet/rest/chargebox/meterinfo/EXTERNAL", 'data/garo_meterinfo.json', verbose)
	except Exception as e:
			print(f'Not able to get meterinfo in GARO! {e}', end=" ")

	try:
			fetch_and_save_data(f"{url_garo}/servlet/rest/chargebox/status?_=1", 'data/garo_status.json', verbose)
	except Exception as e:
			print(f'Not able to get status in GARO! {e}', end=" ")


def get_current_power():
	power = None
	try:
		with garo_lock:
			with open('data/garo_status.json', 'r') as f:
				data = json.load(f)
				power = data['mainCharger'].get('currentChargingPower')
	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
	return power

def get_accumulated_energy():
	energy = None
	try:
		with garo_lock:
			with open('data/garo_status.json', 'r') as f:
				data = json.load(f)
				energy = data['mainCharger'].get('accSessionEnergy')
	except Exception as e:
		print(f'Not able to load status in GARO! {e}', end=" ")
	return energy


def get_current_consumption(test=False):
	"""
	This function check the power consumtion
	Return: 
	power : power consumtion in kW
	"""

	if test:
		return {'fas1': random.random()*10, 'fas2': random.random()*10, 'fas3': random.random()*10}	

	meterinfo_path = "data/garo_meterinfo.json"

	try:
		with garo_lock:
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


def on_off_Garo(value, timeout=10):
	"""
	Set the Garo Charger mode safely.
	Arguments:
		value: "1" = on, "0" = off, "2" = schedule
		timeout: max seconds to wait for network response
	Returns:
		True if request succeeded, False otherwise
	"""

	mode_map = {'1': 'ALWAYS_ON', '0': 'ALWAYS_OFF', '2': 'SCHEMA'}
	value = mode_map.get(value, value)

	url = f"{url_garo}/servlet/rest/chargebox/mode/{value}"
	data = {'mode': value}
	time.sleep(60)
	try:
		response = requests.post(url, data=data, timeout=timeout)
		response.raise_for_status()  # raises for HTTP errors (e.g., 404, 500)
		return True

	except requests.Timeout:
		print(f"Timeout while sending command to GARO ({value})")
		return False

	except requests.RequestException as e:
		print(f"Network error while sending command to GARO ({value}): {e}")
		return False

	except Exception as e:
		print(f"Unexpected error in on_off_Garo: {e}")
		return False


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


def get_status(key, verbose=False):
	try:
		with garo_lock:
			with open('data/garo_status.json', 'r') as f:
				data = json.load(f)

		# Check top level
		if key in data:
			return data[key]

		# Check inside updateStatus (dict)
		if "updateStatus" in data and isinstance(data["updateStatus"], dict):
			if key in data["updateStatus"]:
				return data["updateStatus"][key]

		# Check inside mainCharger (dict)
		if "mainCharger" in data and isinstance(data["mainCharger"], dict):
			if key in data["mainCharger"]:
				return data["mainCharger"][key]

		if verbose:
			print(f"Key '{key}' not found")

		return None

	except Exception as e:
		print(f"ERROR reading config: {e}")
		return None


def get_config(key, verbose=False):
	try:
		with garo_lock:
			with open('data/garo_config.json', 'r') as f:
				data = json.load(f)

			# First check top level
			if key in data:
				return data[key]


			if "reducedCurrentIntervals" in data and isinstance(data["reducedCurrentIntervals"], list):
				if key in data["reducedCurrentIntervals"][0]:
					return data["reducedCurrentIntervals"][0][key]

			# Then check inside slaveList if present
			if "slaveList" in data and isinstance(data["slaveList"], list):
				for slave in data["slaveList"]:
					if key in slave:
						return slave[key]

			if verbose:
				print(f"Key '{key}' not found")

			return None

	except Exception as e:
		print(f"ERROR reading config: {e}")
	return None


def get_meterinfo(state, verbose=False):
	"""
	This function returns the status of the GARO charger
	"""
	with garo_lock:
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




##############  Not used functions  ################
# def get_Garo_current_limit():
# 	config_path = "data/garo_config.json"

# 	try:
# 		with open(config_path, 'r') as f:
# 			config = json.load(f)

# 		charge_current = config["reducedCurrentIntervals"][0].get("chargeLimit")
# 		currentChargingCurrent = config["slaveList"][0].get("currentChargingCurrent")
# 	except Exception as e:
# 		print(f'Not able to get current limit in GARO! {e}', end=" ")
# 		charge_current = 13

# 	return charge_current, currentChargingCurrent

# def get_charge_current(verbose=False):
# 	"""
# 	This function retrieves the current charging current from a local JSON file.
# 	"""
# 	"""
# 	This function retrieves the current charging current from a local JSON file.
# 	"""
# 	status_path = "data/garo_status.json"
# 	try:
# 			with open(status_path, 'r') as f:
# 					data = json.load(f)
# 			with open(status_path, 'r') as f:
# 					data = json.load(f)

# 			charge_current = data['mainCharger'].get('currentChargingCurrent')
# 			if verbose:
# 					print(f"Current charging current: {charge_current}")
# 			return charge_current
# 	except FileNotFoundError:
# 			print(f"Status file not found: {status_path}")
# 	except json.JSONDecodeError:
# 			print(f"Error decoding JSON from {status_path}")
# 	except Exception as e:
# 			print(f"Unexpected error: {e}")
# 	return None

# def get_garo_state():
# 	with garo_lock:
# 		try:
# 			with open('data/garo_config.json', 'r') as f:
# 				config = json.load(f)
# 		except Exception as e:
# 			print(f'Not able to load config in GARO! {e}', end=" ")
# 			config = None
# 		try:
# 			with open('data/garo_meterinfo.json', 'r') as f:
# 				meterinfo = json.load(f)
# 		except Exception as e:
# 			print(f'Not able to load meterinfo in GARO! {e}', end=" ")
# 			meterinfo = None
# 		try:
# 			with open('data/garo_status.json', 'r') as f:
# 				status = json.load(f)
# 		except Exception as e:
# 			print(f'Not able to load status in GARO! {e}', end=" ")
# 			status = None

# 	return config, meterinfo, status

# def get_charge_status():
#     charge_status = None
#     try:
#         with garo_lock:
#             with open('data/garo_status.json', 'r') as f:
#                 data = json.load(f)
#                 charge_status = data['mainCharger'].get('chargeStatus')
#     except Exception as e:
#         print(f'Not able to load status in GARO! {e}', end=" ")
#     return charge_status

# def get_soc():
# 	# First turn on the charger
# 	mode = get_Garo_status('mode')
# 	if mode != 'ALWAYS_ON':
# 		on_off_Garo('1')
# 	# Delay to allow the charger to start
# 	time.sleep(30)
# 	# Get the status of the charger
# 	state = get_Garo_status('chargeStatus')
# 	time.sleep(30)
# 	if mode == 'ALWAYS_OFF':
# 		on_off_Garo('0')
# 		print("Charger is turned off after getting SOC.")
# 	elif mode == 'SCHEMA':
# 		on_off_Garo('2')
# 		print("Charger is set to schema after getting SOC.")
# 	elif mode == 'ALWAYS_ON':
# 		print("Charger is left on after getting SOC.")


# 	return state


if __name__ == '__main__':

	update_Garo_state()

	m = get_Garo_status()
	print(m)



  