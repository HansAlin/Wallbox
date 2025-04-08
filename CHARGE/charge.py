import datetime
import pandas as pd
import numpy as np
import requests
import pytz
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt	
import time
import json


from matplotlib.dates import DateFormatter

from GARO.garo import on_off_Garo, get_Garo_status
from CONFIG.config import low_temp_url, server_url, tz_region, router_url, low_price
from SpotPrice.spotprice import getSpotPrice




def get_auto_charge_schedule(nordpool_data, now, fraction):
	"""
		This function creates a charging schedule based on prevous data from nordpool (nordpool_data).
		It takes n lowest value from future data and compares it to the average of the lowest fraction of the history data.
		If the value is lower than the average it is added to the schedule otherwise the next lowest value is checked.

		Arguments:
			nordpool_data: data from nordpool
			now: current time
			fraction: the fraction of the avalibale hours to use in the schedule
		Returns:
			schedule
			value_lim: the value of the last value in the average of the lowest fraction of the history
		
		"""

	# Get future ´data and history data
	history_data = nordpool_data[nordpool_data['TimeStamp'] < now]
	future_data = nordpool_data[nordpool_data['TimeStamp'] >= now]

	# Get the number of hours in the future and history
	furture_hours = len(future_data)
	history_hours = len(history_data)

	# Get the number of history chunks each chunk is furture_hours long
	# unless the history is shorter than the future
	if furture_hours == 0:
		return pd.DataFrame(), 0
	number_of_history_chunks = max(int(history_hours/furture_hours),1)
	chunk_hours = int(min([history_hours, furture_hours]))

	# Number of hours to use in the future
	fraction_hours = min(max(int(furture_hours*fraction),1), furture_hours)

	# Get the average value of the lowest fraction of the history data
	average_values = np.zeros(fraction_hours)

	for i in range(0,chunk_hours*number_of_history_chunks, chunk_hours):
		sub_data = history_data.iloc[i:i+chunk_hours]
		lowest_fraction = sub_data.nsmallest(fraction_hours, 'value')
		average_value = lowest_fraction['value'].values
		average_values += average_value
	
	average_values = average_values/number_of_history_chunks
	value_lim = average_values[-1]

	first_time = True
	charge_schedule = pd.DataFrame(columns=['TimeStamp', 'value'])
	max_hours = 15			# The car is never nedded to be charged more than 15 hours

	for lowest in range(1, furture_hours + 1):
		for average_value in average_values:

			smallest_row = future_data.nsmallest(lowest, 'value').iloc[-1]
			
			if smallest_row['value'] < average_value:
				if first_time:
					charge_schedule = pd.DataFrame(smallest_row).T
					first_time = False
				else:
					charge_schedule.loc[len(charge_schedule)] = smallest_row
				break

			if len(charge_schedule) >= max_hours:
				break

		if len(charge_schedule) >= max_hours:
			break		

	charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	print(f"Auto: {len(charge_schedule)} h", end=' ')

	# Only consider values after 22:00 and before 06:00
	charge_schedule = charge_schedule[charge_schedule['TimeStamp'].dt.hour >= 22]
	charge_schedule = charge_schedule[charge_schedule['TimeStamp'].dt.hour < 6]

	return charge_schedule, value_lim

def get_fast_smart_schedule(nordpool_data, now, hour_to_charged, charge_limit, set_time=None):
	"""
		This function creates a charging schedule based on data from nordpool (nordpool_data)
		It creates a schedule that with in the set_time will charge the car for hour_to_charged hours
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

	df_sub = nordpool_data[nordpool_data['TimeStamp'] >= datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour)] 

			# TODO Still uses all data and not a small sub set
	if hour_to_charged > charge_limit:
		stop_charge = now + datetime.timedelta(hours=hour_to_charged)
		charge_schedule = df_sub[df_sub['TimeStamp'] < stop_charge]
	else:
		df_sub_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=set_time)]
		charge_schedule = df_sub_sub.nsmallest(hour_to_charged, 'value')
	charge_schedule = charge_schedule.sort_values(by='TimeStamp')
	try:
		value_lim = charge_schedule['value'].max()
	except:
		value_lim = 999
	print(f"Fast smart: for {hour_to_charged} h and Set time: {set_time}, ", end=" ")
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
			pattern: which type of charging pattern available, 'auto', 'fast_smart', 'on'
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

	elif pattern == 'on':
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

def plot_data_schedule(charge_schedule, nordpool_data, now, save_uniqe_plots=False):
	try:	
		sub_nordpool_data = nordpool_data[nordpool_data['TimeStamp'] > now - datetime.timedelta(hours=24)] 
		hh = DateFormatter('%H')
		x1 = sub_nordpool_data['TimeStamp'].values
		y1 = sub_nordpool_data['value'].values
		fig, ax = plt.subplots()
		ax.xaxis.set_major_formatter(hh)
		ax.scatter(x1, y1 , color='blue')
		if not charge_schedule.empty:
			x2 = charge_schedule['TimeStamp'].values
			y2 = charge_schedule['value'].values
			ax.scatter(x2, y2, color='green')
		ax.set_title(f'Schedule')
		ax.set_ylim(min(y1)- 0.2, max(y1) + 0.2)
		vertical_line = datetime.datetime.now()
		ax.axvline(x=vertical_line, color='red')
		#TODO remove saving of all schedules after testing
		if save_uniqe_plots:
			plot_path = f'data/plots/plot_{now.year}-{now.month}-{now.day}_{now.hour}:{now.minute}.png'
			fig.savefig(plot_path)
		fig.savefig('static/image.png')
		plt.close(fig)
		send_image_to_server('static/image.png')
	except Exception as e:
		print(f"Could not plot schedule: {e}", end=" ")

def ifCharge(charge_schedule, now):
	charge_schedule = pd.DataFrame(charge_schedule)

	for row in charge_schedule['TimeStamp']:

		t_stamp = row
		if datetime.timedelta(hours=0) <= (now - t_stamp) < datetime.timedelta(hours=1):
			return True

	return False

def get_charge_fraction(fases, kwh_per_week):

	if fases == 1:
		kw = 3 
	elif fases == 3:
		kw = 9
	else:	
		kw = 3
	hours_needed = kwh_per_week/kw
	fraction = hours_needed/(24*4)

	return fraction	 

def changeChargeStatusGaro(charging, charge, connected, available, test):
	"""
		This function changes the status of the GARO charger
		Arguments:
			charging: True if car is currently charging
			charge: True if the car should be charged
			connected: What kind of status the GARO charger has
			available: What kind of status the GARO charger has
			test: True if the function is in test mode and will not change the status of the GARO charger

		Returns:
			charging: True if the car is currently charging
			connected: What kind of status the GARO charger has
			available: What kind of status the GARO charger has
	"""
	if test:
		print("Test mode! nothing will be changed!	", end=" ")
		
	elif available == "ALWAYS_ON" and charge:
		print("Garo already on!", end=" ")

	elif available != "ALWAYS_ON" and charge == False:
		print("Garo already off!", end=" ")

	elif available == "ALWAYS_ON" and charge == False:
		turn_on_value = "0"
		charging = False


		response = on_off_Garo(turn_on_value)

		if not response:
			charging = True
			print("Status not changed at GARO!", end=" ")
		else:
			print(f"Garo turned off!", end=" ")
			# Leaf status not available
			# h, soc = leaf_status(now, utc)
			# _ = set_button_state({'soc':soc})
		time.sleep(4)
		connected, available = get_Garo_status()	

	elif available != "ALWAYS_ON" and charge  == True:
		turn_on_value = "1"
		charging = True

		response = on_off_Garo(turn_on_value)

		if not response:
			charging = False
			print("Status not changed at GARO!", end=" ")
		else:
			print(f"Garo turned on!", end=" ")
			# Leaf status not available
			# h, soc = leaf_status(now, utc)
			# _ = set_button_state({'soc':soc})
		time.sleep(4)
		connected, available = get_Garo_status()	

	return charging, connected, available

def power_constraints(charging_type='auto'):
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
	log_data = get_log()
	power_data = get_power_data()

	nr_phases = log_data['R Fas value'].values[0]
	voltage = power_data['voltage']
	current_power = power_data['power_current_mean']
	third_highest_power = power_data['third_highest_power']
	min_current = 6	#TODO implement such that values comes from GARO
	max_current = 13 #TODO implement such that values comes from GARO

	min_power = min_current * voltage * nr_phases

	now, _ = get_now()
	hour = now.hour
	low_price_time = False
	if hour >= low_price['start'] or hour < low_price['stop']:
		low_price_time = True

	if low_price_time:
		current_power = current_power / 2
		min_power = min_power / 2

	if charging_type != 'auto':
		charge_current = max_current
		print(f"No power constraints, charge current: {charge_current:.2f} A", end=" ")
		return True
	
	if (current_power + min_power) < third_highest_power:
		# OK to charge
		# How much to charge
		charge_power = third_highest_power - current_power
		charge_current = charge_power / (voltage * nr_phases)
		print(f"Power constraints OK, charge current: {charge_current:.2f} A", end=" ")
		return True
	else:
		# Not OK to charge
		# Adjust the current value
		charge_current = 0
		print(f"Power constraints not OK, charge current: {charge_current:.2f} A", end=" ")
		return False
		 

def get_power_data():
	with open('data/energy_status.json', 'r') as file:
		data = json.load(file)
		return data


def get_log():
	try:
		log = pd.read_csv('data/log.csv')
		return log
	except FileNotFoundError:
		return None

def get_button_state():
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

			print("Web respons:", end=" ")
			if data == None:
				print("None", end=" ")	
				return None
			elif data['auto'] == 1:
				new_data['charge_type'] = 'auto'
			elif data['on'] == 1:
				new_data['charge_type'] = 'on'
			elif data['fast_smart'] == 1:
				new_data['charge_type'] = 'fast_smart'	
			else:
				new_data['charge_type'] = 'off'

			print(f"Charge type: {new_data['charge_type']}", end=" ")	
			print(f"Hours: {new_data['hours']}", end=" ")			
					
			return new_data

		else:
			print("Failed to recive data", end=" ")
			return None
	except requests.exceptions.RequestException as e:
			print("An error occured: ", e, end=" ")
			return None
	


def set_button_state(state):
	"""
		This function sets the state of the button on the server
			
			Arguments: state
			
			Returns: response
	"""
	if state == {'charge_type': 'auto'}:
		state = {'auto': 1, 'fast_smart': 0, 'on': 0}
	elif state == {'charge_type': 'fast_smart'}:
		state = {'auto': 0, 'fast_smart': 1, 'on': 0}
	elif state == {'charge_type': 'on'}:
		state = {'auto': 0, 'fast_smart': 0, 'on': 1}
	elif state == {'charge_type': 'off'}:
		state = {'auto': 0, 'fast_smart': 0, 'on': 0}

	try:
		response = requests.post(server_url + '/set_state', json=state).status_code
		if response == 200:
			print("Successful update state on server!", end=" ")
		else:
			print("Could not update state on server!", end=" ")
		return response
	except:
		print("Not able to contact server!", end=" ")
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


def lowTemp():
	"""
		This function get the temperture from a local device if any. 
		If the temperture is below -18 it returns True
		If the temperture is above -18 or the device is not available it returns False
	"""
	temp = get_temp()

	if temp == None:
		return False
	
	if temp < -18:
		return True
	else:
		return False


def get_temp():
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
	data['hours'] = 0
	data['set_time'] = 0
	data['fas_value'] = 1
	data['kwh_per_week'] = 50

	return data

def connected_to_lan(test=False):
	# initializing URL
	url = router_url
	timeout = 10

	if test:
		return True

	try:
			# requesting URL
			request = requests.get(url,
														timeout=timeout)
			return True
	
	# catching exception
	except (requests.ConnectionError,
					requests.Timeout) as exception:
			print("Internet is off", end=' ')
			return False

def next_datetime(current: datetime.datetime, hour: int, **kwargs):
    repl = current.replace(hour=hour, **kwargs)
    while repl <= current:
        repl = repl + datetime.timedelta(days=1)
    return repl

import pandas as pd

def save_log(data, now, connected, available, response):
	"""
	This function saves the log data to a file
	Arguments:
	data: data used in main function to keep track of current status
	now: current time
	connected: status from GARO
	available: status from GARO
	response: status from the server, what user has selected
	"""
	max_lines = 1000

	if response == None:
		response = {}
		response['charge_type'] = None
		response['set_time'] = None
		response['fas_value'] = None
		response['kwh_per_week'] = None
		response['hours'] = None


	data_dict = {
	"Time": now,
	"G Connected": connected,
	"G Available": available,
	"R Charge type": response['charge_type'],
	"R Set time": response['set_time'],
	"R Fas value": response['fas_value'],
	"R kwh per week": response['kwh_per_week'],
	"R Hours": response['hours'],
	"D New down load": data['new_down_load'],
	"D Charge type": data['charge_type'],
	"D Charge": data['charge'],
	"D Charging": data['charging'],
	"D Connected": data['connected'],
	"D Hours": data['hours'],
	"D Available": data['available'],
	"D Set time": data['set_time'],
	"D Fas value": data['fas_value'],
	"D kwh per week": data['kwh_per_week'],
	"D Schedule": "No" if data['schedule'].empty else "YES",
	"D Nordpool data": "No" if data['nordpool'].empty or data['nordpool'].iloc[-1]['TimeStamp'] < now else "YES"
	}

	data_df = pd.DataFrame([data_dict])

	try:
		log = pd.read_csv('data/log.csv')
		log = pd.concat([log, data_df], ignore_index=True)
		if len(log) > max_lines:
			log = log.iloc[-max_lines:]
		log.to_csv('data/log.csv', index=False)
	except FileNotFoundError:
		data_df.to_csv('data/log.csv', index=False)

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
	This function checks if response and data are the same as last time.
	It also checks that the connection state have not gone from not connected
	to connected (connected or the similarities) 
	"""	

	return response['charge_type'] == data['charge_type'] and \
				response['hours'] == data['hours'] and \
				response['set_time'] == data['set_time'] and \
				response['fas_value'] == data['fas_value'] and \
				response['kwh_per_week'] == data['kwh_per_week'] and \
				 not (connected != "NOT_CONNECTED" and data['connected'] == "NOT_CONNECTED")

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

	

if __name__ == '__main__':
	now, _ = get_now()
	one_hour = datetime.timedelta(hours=1)
	print("Time: ", now)
	print("Previous hour: ", now - one_hour)

		#power_constraints()