import datetime
import pandas as pd
import numpy as np
import requests
import pytz
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt	
import time
import json
import os
import portalocker
import sys

# Add the parent folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Test 1
# Add the parent folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Test 1

from matplotlib.dates import DateFormatter

from GARO.garo import on_off_Garo, get_Garo_status, set_Garo_current, get_status, get_config
from CONFIG.config import low_temp_url, server_url, tz_region, router_url, low_price
from SpotPrice.spotprice import getSpotPrice

charge_current = 0


def get_auto_charge_schedule(nordpool_data, now, fraction):
	"""
	This function creates a charging schedule based on previous data from nordpool (nordpool_data).
	It takes the lowest values from future data and compares them to the average of the lowest fraction of the history data.
	If the value is lower than the average, it is added to the schedule; otherwise, the next lowest value is checked.

	Arguments:
			nordpool_data: DataFrame with nordpool data (must include 'TimeStamp' and 'value' columns).
			now: Current time (datetime object).
			fraction: The fraction of the available time to use in the schedule.

	Returns:
			schedule: DataFrame with the charging schedule.
			value_lim: The value of the last value in the average of the lowest fraction of the history.
	"""

	# Ensure TimeStamp is a datetime object
	nordpool_data['TimeStamp'] = pd.to_datetime(nordpool_data['TimeStamp'])

	# Split data into history and future based on the current time
	history_data = nordpool_data[nordpool_data['TimeStamp'] < now]
	future_data = nordpool_data[nordpool_data['TimeStamp'] >= now]

	# Handle case where there is no future data
	if future_data.empty:
		nordpool_data = getSpotPrice(now=now, prev_data=nordpool_data)

	# Normalize history_data to 15-minute intervals
	history_data = history_data.set_index('TimeStamp').resample('15T').mean().reset_index()
	history_data['value'] = history_data['value'].fillna(method='ffill')  # Forward fill as a fallbac

	# Round 'now' to the nearest 15-minute interval
	now = now.replace(second=0, microsecond=0)
	diff = nordpool_data['TimeStamp'].diff().mean()  # Timedelta
	diff_minutes = int(diff.total_seconds() / 60)          # now a float in minutes
	minute = int((now.minute // diff_minutes) * diff_minutes) 

	now = now.replace(minute=minute)
	# Calculate the quantile based on the fraction
	value_lim = history_data['value'].quantile(fraction)

	# Filter future data based on the value limit
	charge_schedule = future_data[future_data['value'] < value_lim]
	charge_schedule = charge_schedule[charge_schedule['TimeStamp'] >= now]
	# Sort the schedule by TimeStamp
	charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	print(f"Auto: {len(charge_schedule)} intervals ({diff_minutes} min each), min data value: {future_data['value'].min():.2f}, limit: {value_lim:.2f}", end=' ')

	return charge_schedule, value_lim

def get_fast_smart_schedule(nordpool_data, now, hour_to_charged, charge_limit, set_time=None):
	"""
	This function creates a charging schedule based on data from nordpool (nordpool_data)
	It creates a schedule that within the set_time will charge the car for hour_to_charged hours
	Arguments:
	nordpool_data: data from nordpool
	now: current time
	hour_to_charged: hours for setting schedule
	charge_limit: value limit for charging, e.g. 89 means that the car will not charge if the value is above 89
	set_time: hours to the car should be charged

	Returns:
	schedule
	value_lim: the value of the last value in the average of the lowest fraction of the history
	"""

	diff = nordpool_data['TimeStamp'].diff().mean()  # Timedelta
	diff_minutes = diff.total_seconds() / 60          # now a float in minutes
	split_per_hour = int(60 / diff_minutes)
	time_lim = now - datetime.timedelta(minutes=int(diff_minutes))
	print(f"Time line: {time_lim}")
	# Filter data starting from the current time
	df_sub = nordpool_data[nordpool_data['TimeStamp'] >= time_lim]



	intervals_to_charge = hour_to_charged * split_per_hour 

	if hour_to_charged > charge_limit:
		# Calculate the stop time based on hour_to_charged
		stop_charge = now + datetime.timedelta(hours=hour_to_charged)
		charge_schedule = df_sub[df_sub['TimeStamp'] <= stop_charge]
	else:

		if set_time is not None:
			set_time_intervals = set_time
		else:
			set_time_intervals = 12

		df_sub = df_sub[df_sub['TimeStamp'] <= now + datetime.timedelta(hours=set_time_intervals)]

	# Select the lowest `intervals_to_charge` values
	charge_schedule = df_sub.nsmallest(intervals_to_charge, 'value')

	# Sort the schedule by timestamp
	charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	# Calculate the maximum value in the schedule
	try:
		value_lim = charge_schedule['value'].max()
	except Exception:
		value_lim = 999

	print(f"Fast smart: {len(charge_schedule)} intervals ({diff_minutes} min each), min data value: {value_lim:.2f}h and Set time: {set_time}, ", end=" ")
	#print(f"Auto: {len(charge_schedule)} intervals ({diff_minutes} min each), min data value: {future_data['value'].min():.2f}, limit: {value_lim}", end=' ')
	return charge_schedule, value_lim

def get_on_charge_schedule(nordpool_data, now, hour_to_charged):

		df_sub = nordpool_data[nordpool_data['TimeStamp'] >= datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour)] 
		hours_on = hour_to_charged
		
		charge_schedule = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=hours_on)]
		charge_schedule = charge_schedule.sort_values(by='TimeStamp')
		try:
			value_lim = charge_schedule['value'].max()
		except:
			value_lim = 999

		print(f"Charge now for {len(charge_schedule)}", end=" ")
		return charge_schedule, value_lim

def get_chargeSchedule(hour_to_charged, nordpool_data, now, pattern, set_time=None, value_lim=82, charge_fraction=0.3):

	"""
		This function creates a charging schedule based on data from nordpool (nordpool_data)
		Arguments:
			hour_to_charge: hours for setting schedule
			nordpool_data: data from nordpool
			now: current time
			pattern: which type of charging pattern available, 'auto', 'fast_smart', 'manual'
			set_time: hours to the car should be charged
			value_lim: the value of the last value in the average of the lowest fraction of the history
			charge_fraction: the fraction of the avalibale hours to use in the schedule

		Returns:
			schedule

	"""
	print(f"Getting charging schedule at: {now}")


	charge_limit = 12

	if pattern == 'fast_smart':
		charge_schedule, value_lim = get_fast_smart_schedule(nordpool_data, now, hour_to_charged, charge_limit, set_time)

	elif pattern == 'auto':
		charge_schedule, value_lim = get_auto_charge_schedule(nordpool_data, now, charge_fraction)

	elif pattern == 'manual':
		hour_to_charged = 16
		charge_schedule, value_lim = get_on_charge_schedule(nordpool_data, now, hour_to_charged)

	else:
		print("No pattern selected", end=" ")
		charge_schedule = pd.DataFrame()

	if charge_schedule.empty:
		return charge_schedule
	
	print(f"Value lim: {value_lim}")
	print("Charging schedule:")
	print(charge_schedule)

	return charge_schedule

def plot_nordpool_data(nordpool_data, now, test=False):
	if test:
		substring = 'test'
	else:
		substring = ''
	try:
		if nordpool_data.empty:
			print("Nordpool data is empty", end=" ")
		else:	
			hh = DateFormatter('%H')
			x = nordpool_data['TimeStamp'].values
			y = nordpool_data['value'].values
			fig, ax = plt.subplots()
			ax.xaxis.set_major_formatter(hh)
			ax.bar(x, y, width=0.03, color='blue')
			ax.set_title(f'Nordpool data, {now}')
			ax.axvline(x=now, color='red')
			ax.set_ylim(min(y) - 0.2, max(y) + 0.2)
			plot_path = f'static/plot_nordpool{substring}.png' 
			fig.savefig(plot_path)
			plt.close(fig)
			send_image_to_server(f'static/plot_nordpool{substring}.png')
	except Exception as e:
		print(f"Could not plot nordpool data: {e}", end=" ")

def ifCharge(charge_schedule, now, time_delta=15):
	"""
		This function if current time (now) is within a schedule time delta (time_delta).

		Arguments:
			charge_schedule (dict/dataframe): Schedule with timestamps where it's OK to charge
			now: The current timestamp
			time_delta: How large each schedule step isinstance

		Returns:
			Bolean: True or False		 
	"""
	charge_schedule = pd.DataFrame(charge_schedule)

	for row in charge_schedule['TimeStamp']:

		t_stamp = row
		if datetime.timedelta(hours=0) <= (now - t_stamp) < datetime.timedelta(minutes=time_delta):
			return True

	return False

def get_charge_fraction(phases, kwh_per_week):
	"""
		This function estimates the fraction of charging time that is needed.

		Arguments: 
			phases: number of phases used in the system
			kwh_per_week: expected amount of needed energy per week
	"""
	if phases == 1:
		kw = 3 
	elif phases == 3:
		kw = 9
	else:	
		kw = 3
	hours_needed = kwh_per_week/kw
	fraction = hours_needed/(24*4)

	return fraction	 


def changeChargeStatusGaro(charging, charge, connected, available, test):
	"""
	Change the GARO charger status safely with timeouts and error handling.
	"""
	#print(f"From changeChargeStatusGaro: connected={connected}, available={available}, charging={charging}, charge={charge}")

	if test:
		print("Test mode! Nothing will be changed.", end=" ")
		return charging, connected, available

	try:
		if connected == 'CHARGING_FINISHED' and available == "ALWAYS_ON":
			turn_on_value = "0"
			charging = False

			response = on_off_Garo(turn_on_value)
			if not response:
					charging = True
					print("Status not changed at GARO!", end=" ")
			else:
					print("Garo turned off!", end=" ")

			connected, available = get_Garo_status()

		elif available == "ALWAYS_ON" and charge:
			#print("Garo already on!", end=" ")
			pass

		elif available != "ALWAYS_ON" and not charge:
			#print("Garo already off!", end=" ")
			pass

		elif available == "ALWAYS_ON" and not charge:
			turn_on_value = "0"
			charging = False

			response = on_off_Garo(turn_on_value)
			if not response:
				charging = True
				print("Status not changed at GARO!", end=" ")
			else:
				print("Garo turned off!", end=" ")

			connected, available = get_Garo_status()

		elif available != "ALWAYS_ON" and charge:
				turn_on_value = "1"
				charging = True

				response = on_off_Garo(turn_on_value)
				if not response:
						charging = False
						print("Status not changed at GARO!", end=" ")
				else:
						print("Garo turned on!", end=" ")

				connected, available = get_Garo_status()

	except Exception as e:
			print(f"Error during GARO status change: {e}")


	return charging, connected, available


def power_constraints(response=None, garo_status=None):
	"""
		This function checks if the current power consumtion is below the third highest value
		in present month. If the power consumtion is below the third highest value with a value that 
		is lowest current value (usually 6 A) times 230 V times the number of phases the car is connected to.
		Like: 6 A * 230 V * 3 = 4.14 kW for a 3 phase connection. For periods between 22:00 and 06:00 the 
		total power consumtion can be twise as high without effect the power constraints.
		The fucntion also adjust the current value as long the power consumtion is below the third highest value.

		Returns:
			True if the power consumtion is below the third highest value
	"""
	global charge_current
	charging_type = response['charge_type']
	max_power = response['max_power']
	power_data = get_power_data()
	
	nr_phases = get_status('nrOfPhases')
	
	min_current = get_config('minCurrentLimit')
	max_current = get_config('maxChargeCurrent')
	current_charging_power = get_status('currentChargingPower')
	pressent_current_limit = get_config('chargeLimit')
	val = get_config('currentChargingCurrent')
	currentChargingCurrent = val / 1000 if val is not None else 0
	voltage = power_data['voltage']
	current_mean_power = power_data['power_current_mean'] # Including charging
	current_power = power_data['power_current_list']
	third_highest_power = power_data['third_highest_power']
	house_power = current_mean_power - current_charging_power
	possible_power = third_highest_power - house_power
	current_mean_power = power_data['power_current_mean'] # Including charging
	third_highest_power = max(power_data['third_highest_power'], max_power) 

	if currentChargingCurrent != None:
		currentChargingCurrent = currentChargingCurrent/1000
	else: 
		currentChargingCurrent = 0	
	house_power = current_mean_power - current_charging_power
	possible_power = third_highest_power - house_power

	if nr_phases == 1:
		max_manual_current = max_current
	elif nr_phases == 3:
		max_manual_current = min_current

	if charging_type == 'manual':
		charge_current = max_manual_current

		if int(pressent_current_limit) != int(charge_current) :
			print(f"\n No power constraints, charge current: {charge_current:.2f} A", end=" ")
			set_Garo_current(charge_current)

		return True

	min_power = min_current * voltage * nr_phases

	print(f"\n Current: mean power: {current_mean_power:.2f} kW", end=' ')
	print(f"charging power: {current_charging_power:.2f} kW", end=' ')
	print(f"household power: {house_power:.2f} kW", end=' ')
	print(f"Possible power: {possible_power:.2f} kW", end=' ')
	print(f"Third highest power: {third_highest_power:.2f} kW", end=' ')
	print(f"Min power: {min_power:.2f} kW", end=' ')


	now, _ = get_now(verbose=False)
	hour = now.hour
	low_price_time = False
	if hour >= low_price['start'] or hour < low_price['stop']:
		low_price_time = True

	if low_price_time:
		current_mean_power = current_mean_power / 2
		min_power = min_power / 2

	possible_power = third_highest_power - house_power - 200 # To get some marginal

	if (current_mean_power < third_highest_power ):

		charge_current = int(possible_power / (voltage * nr_phases))
		charge_current = min(charge_current, max_current)

		print(f"Charge power: {possible_power:.2f} kW, Charge current: {charge_current}", end=" ")

		if charge_current >= min_current:
		
			if pressent_current_limit - 1 < charge_current < pressent_current_limit + 1:
				current = int(pressent_current_limit)
				print(f"Power constraints OK, charge current: {current} A", end=" ")
			else:
				set_Garo_current(int(charge_current))
			return True
		else:
			# Not OK to charge
			# Adjust the current value
			charge_current = 0
			print(f"Power constraints not OK, charge current: {charge_current} A", end=" ")
			# if pressent_current != charge_current:
			# 	set_Garo_current(charge_current)
			return False

	
	else:
		# Not OK to charge
		# Adjust the current value
		charge_current = 0
		print(f"Power constraints not OK, charge current: {charge_current} A", end=" ")
		# if pressent_current != charge_current:
		# 	set_Garo_current(charge_current)
		return False

def get_power_data(retries=3, delay=2):
	path = 'data/energy_status.json'
	for attempt in range(retries):
		try:
			if os.path.getsize(path) < 10:
				raise ValueError("File too small to be valid JSON")

			with open(path, 'r') as file:
				portalocker.lock(file, portalocker.LOCK_SH)
				data = json.load(file)
				portalocker.unlock(file)
				return data
		except (json.JSONDecodeError, ValueError, OSError) as e:
			print(f"Attempt {attempt + 1} failed: {e}")
			time.sleep(delay)

	raise RuntimeError("Failed to read power data after multiple attempts")


def get_button_state(do_print=True):
	"""
		This function gets the state of the button from the server
			
			Returns: data
	"""

	try:
		response = requests.get(server_url + '/get_status', timeout=20)
		if response.status_code ==  200:
			data = response.json()

			new_data = {}
			new_data['hours'] = data['hours']
			new_data['set_time'] = data['set_time']
			new_data['fas_value'] = data['fas_value']
			new_data['kwh_per_week'] = data['kwh_per_week']
			new_data['status'] = data['status']
			new_data['max_power'] = data['max_power']

			# print("Web respons:", end=" ")
			# print("Web respons:", end=" ")
			if data == None:
				print("None", end=" ")	
				return None
			elif data['auto'] == 1:
				new_data['charge_type'] = 'auto'
			elif data['manual'] == 1:
				new_data['charge_type'] = 'manual'
			elif data['fast_smart'] == 1:
				new_data['charge_type'] = 'fast_smart'	
			else:
				new_data['charge_type'] = 'off'
			if do_print:
				print(f"Web status: {new_data['charge_type']}", end="")	
				if new_data['charge_type'] == 'fast_smart':
					print(f" {new_data['hours']} h in {new_data['set_time']}", end="")			
				print(";", end=" ")		
			return new_data

		else:
			print("Failed to recive data", end=" ")
			return None
	except requests.exceptions.RequestException as e:
			print("An error occured: ", e, end=" ")
			return None

def set_button_state(state, current_server_state=None):
	"""
	Set the charge mode on the server safely without overwriting unrelated fields.

	Args:
	state (dict): e.g., {'charge_type': 'auto', 'hours': 5, 'set_time': 12, ...}
	current_server_state (dict, optional): current server state

	Returns:
	HTTP status code or None if failed
	"""
	mode_map = {
	'auto': {'auto': 1, 'fast_smart': 0, 'manual': 0},
	'fast_smart': {'auto': 0, 'fast_smart': 1, 'manual': 0},
	'manual': {'auto': 0, 'fast_smart': 0, 'manual': 1},
	'off': {'auto': 0, 'fast_smart': 0, 'manual': 0}
	}

	if 'charge_type' not in state:
		new_state = {}
	else:
		# Only update the mode flags
		new_state = mode_map.get(state['charge_type']).copy()

	# Include optional user-configurable fields
	for key in ['hours', 'set_time', 'fas_value', 'kwh_per_week', 'status']:
		if key in state:
			new_state[key] = state[key]

	# Auto-fetch current server state if not provided
	if current_server_state is None:
		server_data = get_button_state(do_print=False)
	if server_data:
		current_server_state = {}
	# Only compare the keys we are going to update
	for key in new_state.keys():
		current_server_state[key] = server_data.get(key)

	# Only send update if something actually changed
	if current_server_state and current_server_state == new_state:
		pass
		return 200

	try:
		response = requests.post(server_url + '/set_state', json=new_state).status_code
		if response == 200:
			pass
		else:
			print("Could not update state on server!", end=" ")
		return response
	except Exception as e:
		print(f"Not able to contact server! {e}", end=" ")
	return None



def send_image_to_server(image_path, verbose=False):
	try:
		with open(image_path, 'rb') as img:
			response = requests.post(server_url + '/upload_image', files={'image': img})
		if response.status_code == 200:
			if verbose:
				print("Successfully uploaded image to server!", end=" ")
		else:
			if verbose:
				print("Could not upload image to server!", end=" ")
		return response.status_code
	except:
		if verbose:
			print("Not able to contact server!", end=" ")
		return None

def get_now(*args, verbose=True):
	"""
		This function get the current time and the utc offset
		
			Returns: now, utc_offset

	"""
	if args:
		now = args[0] + datetime.timedelta(minutes=20)
		print(now, end=" ")
		timezone = pytz.timezone(tz_region)
		utc_offset = timezone.localize(now).utcoffset().seconds/3600
		return now, utc_offset
	
	now = datetime.datetime.now()
	if verbose:
		print(now, end=" ")
	timezone = pytz.timezone(tz_region)
	utc_offset = timezone.localize(now).utcoffset().seconds/3600
	return now, utc_offset

class Temp():
	"""
	Utility class for periodically retrieving and evaluating a temperature
	from a local web endpoint.

	The class stores the last time a temperature was fetched and only updates
	the value after `time_laps` seconds have passed. The `lowTemp()` method
	checks whether the temperature is below -18°C, returning True if so,
	and False if the temperature is higher or if the reading fails.

	Attributes:
		time_laps (int): Minimum number of seconds between temperature updates.
		now (datetime): Timestamp of the last successful temperature check.
		temp (float | None): Last retrieved temperature value.

	Methods:
		lowTemp():
			Returns True if the temperature is below -18°C.
			Returns False otherwise or if fetching temperature fails.

		get_temp():
			Attempts to retrieve the temperature from `low_temp_url`.
			Returns a float if successful or None on error.
	"""

	def __init__(self, time_laps=120) -> None:
		self.time_laps = time_laps
		self.now, _ = get_now(verbose=False)
		self.temp = 0

	def lowTemp(self):
		"""
			This function get the temperture from a local device if any. 
			If the temperture is below -18 it returns True
			If the temperture is above -18 or the device is not available it returns False
		"""
		now, _ = get_now(verbose=False)
		if (now - self.now).total_seconds() > self.time_laps:
			self.temp = self.get_temp()

		if self.temp == None:
			return False
		
		if self.temp < -18:
			return True
		else:
			return False


	def get_temp(self):
		try:
			url = low_temp_url
			page = requests.get(url=url, timeout=20)
			soup = BeautifulSoup(page.content, "html.parser")
			data = soup.find_all("p")[0].text
			temp = data.split(' ')[1]
			temp = float(temp)
			return temp
		except:
			return None


def create_data_file():
	data = {}

	data['nordpool'] = pd.DataFrame()
	data['last_down_load'] = datetime.datetime.now() - datetime.timedelta(hours=24)
	data['new_down_load'] = False 
	data['charge_type'] = 'auto'
	data['schedule'] = pd.DataFrame()
	data['charge'] = False
	data['charging'] = True
	data['connected'] = 0
	data['available'] = 0
	data['available'] = 0
	data['hours'] = 0
	data['set_time'] = 0
	data['fas_value'] = 1
	data['kwh_per_week'] = 50

	return data

def save_log(data, now, connected, available, response):
	"""
	Save a log entry to CSV. Handles both normal operation and exceptions.

	Arguments:
	- data: dict containing current state or error info
	- now: current datetime
	- connected: GARO connection status
	- available: GARO availability status
	- response: dict from server / user response
	"""
	max_lines = 1000
	log_path = 'data/log.csv'
	tmp_path = 'data/log_tmp.csv'
	os.makedirs(os.path.dirname(log_path), exist_ok=True)

	# Determine log type
	log_type = "ERROR" if "error" in data else "NORMAL"

	try:
		# Build the log row safely
		data_dict = {
			"Time": now,
			"Type": log_type,
			"G Connected": connected,
			"G Available": available,
			"R Charge type": response.get('charge_type', "None") if response else "None",
			"R Set time": response.get('set_time', "None") if response else "None",
			"R Fas value": response.get('fas_value', "None") if response else "None",
			"R kwh per week": response.get('kwh_per_week', "None") if response else "None",
			"R Hours": response.get('hours', "None") if response else "None",
			"D New down load": data.get('new_down_load', "None"),
			"D Charge type": data.get('charge_type', "None"),
			"D Charge": data.get('charge', "None"),
			"D Charging": data.get('charging', "None"),
			"D Connected": data.get('connected', "None"),
			"D Hours": data.get('hours', "None"),
			"D Available": data.get('available', "None"),
			"D Set time": data.get('set_time', "None"),
			"D Fas value": data.get('fas_value', "None"),
			"D kwh per week": data.get('kwh_per_week', "None"),
			"D Schedule": "No" if data.get('schedule', pd.DataFrame()).empty else "YES",
			"D Nordpool data": "No" if data.get('nordpool', pd.DataFrame()).empty else "YES",
			"Error": data.get('error', ""),
			"Trace": data.get('trace', "")
		}
	except Exception as log_e:
		print(f"⚠️ Failed to prepare log dict: {log_e}")
		return

	data_df = pd.DataFrame([data_dict])

	try:
		if os.path.exists(log_path):
			log = pd.read_csv(log_path)
			log = pd.concat([log, data_df], ignore_index=True)
			if len(log) > max_lines:
				log = log.iloc[-max_lines:]
		else:
			log = data_df
		# Atomic write
		log.to_csv(tmp_path, index=False)
		os.replace(tmp_path, log_path)
	except Exception as file_e:
		print(f"Failed to save log CSV: {file_e}")

def if_download_nordpool_data(data, now, test=False):
	""""
	This function checks if the nordpool data should be downloaded.
	These are the conditions for downloading the data:
	1. The data{'nordpool'} is empty, no data available.
	2. The last download was more than 24 hours ago.
	3. The last nordpool data entry is less than 9 hours ahead of now. In practice
	that means that now.hour is more than 14 since the last entry is at 23:00.
	4. The first entry in the nordpool data is less than 0 hours ago. That means 
	that data is missing. There is a gap in the data.

	"""
	if ( data['nordpool'].empty or \
	now - data['last_down_load'] > datetime.timedelta(hours=24)) or \
	(data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)) or \
		(now - data['nordpool']['TimeStamp'].iloc[0] < datetime.timedelta(hours=0)) :

		nordpool = getSpotPrice(now=now, prev_data=data['nordpool'], test=test)
		plot_nordpool_data(nordpool, now)

		last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
		if nordpool.empty or nordpool.equals(data['nordpool']):
			new_download = False
		else:
			new_download = True
		data['nordpool'] = nordpool
		data['last_down_load'] = last_down_load
		data['new_down_load'] = new_download

	else:
		data['new_down_load'] = False

	return data	

def if_status_quo(data, response, connected):
	"""
	Checks if response and data are the same as last time.
	Ignores transitions while the charger is in active states.
	"""

	same_settings = (
			response['charge_type'] == data['charge_type'] and
			response['hours'] == data['hours'] and
			response['set_time'] == data['set_time'] and
			response['fas_value'] == data['fas_value'] and
			response['kwh_per_week'] == data['kwh_per_week']
	)

	# Only rebuild if user settings changed or if we went from NOT_CONNECTED to CONNECTED
	if not same_settings:
			return False

	# Ignore changes while charging or paused
	if data['connected'] != 'CHARGING' and connected in (
			'CHARGING', 'DISABLED', 'CHARGING_PAUSED', 'CHARGING_FINISHED'
	):
			return True

	# Otherwise, allow schedule rebuild when going from NOT_CONNECTED → CONNECTED
	if data['connected'] == 'NOT_CONNECTED' and connected != 'NOT_CONNECTED':
			return False

	return True


def update_charge_schedule(data, response, now):
	if response['charge_type'] != 'off':
		schedule= get_chargeSchedule(hour_to_charged=response['hours'], 
									nordpool_data=data['nordpool'], 
									now=now, 
									set_time=response['set_time'],
									pattern=response['charge_type'],
									charge_fraction=get_charge_fraction( response['fas_value'], response['kwh_per_week']))
		data['schedule'] = schedule
		print(f"Charge schedule: {len(data['schedule'])} h", end=" ")
	elif response['charge_type'] == 'off':
		data['schedule'] = pd.DataFrame()
		print("Charge schedule: OFF", end=" ")	

	return data	

###################  Not used functions  ###################3
# def plot_data_schedule(charge_schedule, nordpool_data, now, save_uniqe_plots=False):
# 	try:	
# 		sub_nordpool_data = nordpool_data[nordpool_data['TimeStamp'] > now - datetime.timedelta(hours=24)] 
# 		hh = DateFormatter('%H')
# 		x1 = sub_nordpool_data['TimeStamp'].values
# 		y1 = sub_nordpool_data['value'].values
# 		fig, ax = plt.subplots()
# 		ax.xaxis.set_major_formatter(hh)
# 		ax.scatter(x1, y1 , color='blue')
# 		if not charge_schedule.empty:
# 			x2 = charge_schedule['TimeStamp'].values
# 			y2 = charge_schedule['value'].values
# 			ax.scatter(x2, y2, color='green')
# 		ax.set_title(f'Schedule')
# 		ax.set_ylim(min(y1)- 0.2, max(y1) + 0.2)
# 		vertical_line = datetime.datetime.now()
# 		ax.axvline(x=vertical_line, color='red')
# 		#TODO remove saving of all schedules after testing
# 		if save_uniqe_plots:
# 			plot_path = f'data/plots/plot_{now.year}-{now.month}-{now.day}_{now.hour}:{now.minute}.png'
# 			fig.savefig(plot_path)
# 		fig.savefig('static/image.png')
# 		plt.close(fig)
# 		send_image_to_server('static/image.png')
# 	except Exception as e:
# 		print(f"Could not plot schedule: {e}", end=" ")


# def get_log():
# 	try:
# 		log = pd.read_csv('data/log.csv')
# 		return log
# 	except FileNotFoundError:
# 		return None

# def connected_to_lan(test=False):
# 	# initializing URL
# 	url = router_url
# 	timeout = 10

# 	if test:
# 		return True

# 	try:
# 			# requesting URL
# 			request = requests.get(url,
# 														timeout=timeout)
# 			return True
	
# 	# catching exception
# 	except (requests.ConnectionError,
# 					requests.Timeout) as exception:
# 			print("Internet is off", end=' ')
# 			return False

# def next_datetime(current: datetime.datetime, hour: int, **kwargs):
#     repl = current.replace(hour=hour, **kwargs)
#     while repl <= current:
#         repl = repl + datetime.timedelta(days=1)
#     return repl
	

if __name__ == '__main__':
	now, _ = get_now()
	now = now.replace(minute=0, second=0, microsecond=0)
	print(f"Now: {now}", end=' ')
	one_hour = datetime.timedelta(hours=1)
	
	response = get_Garo_status()
	print(response)

	