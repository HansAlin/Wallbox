import datetime
import pandas as pd
import numpy as np
import requests
import pytz
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt	
import time

from matplotlib.dates import DateFormatter

from GARO.garo import on_off_Garo, get_Garo_status
from CONFIG.config import low_temp_url, server_url, tz_region, router_url



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
	number_of_history_chunks = max(int(history_hours/furture_hours),1)
	chunk_hours = int(min([history_hours, furture_hours]))

	# Number of hours to use in the future
	fraction_hours = max(int(furture_hours*fraction),1)

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
	print(f"Set time: {set_time}, ", end=" ")
	charge_schedule = charge_schedule.sort_values(by='TimeStamp')
	value_lim = charge_schedule.nlargest(1, 'value')['value'].values[0]

	return charge_schedule, value_lim

def get_on_charge_schedule(nordpool_data, now, hour_to_charged):

		df_sub = nordpool_data[nordpool_data['TimeStamp'] >= datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour)] 
		hours_on = hour_to_charged
		print("Charge now", end=" ")
		charge_schedule = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=hours_on)]
		charge_schedule = charge_schedule.sort_values(by='TimeStamp')
		value_lim = charge_schedule.nlargest(1, 'value')['value'].values[0]

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
		charge_schedule, value_lim = get_on_charge_schedule(nordpool_data, now, hour_to_charged)

	else:
		print("No pattern selected", end=" ")
		charge_schedule = pd.DataFrame()

	print(f"Value lim: {value_lim}")
	print("Charging schedule:")
	print(charge_schedule)
	plot_data_schedule(charge_schedule, nordpool_data, now, save_uniqe_plots=False)
	if not charge_schedule.empty:
		with  open('data/schedule_log.csv', 'a') as f:
			f.write(str({'TimeStamp':now,'schedule':charge_schedule['TimeStamp']} ))
	return charge_schedule

def plot_nordpool_data(nordpool_data):
	hh = DateFormatter('%H')
	x = nordpool_data['TimeStamp'].values
	y = nordpool_data['value'].values
	fig, ax = plt.subplots()
	ax.xaxis.set_major_formatter(hh)
	ax.scatter(x, y)
	ax.set_title(f'Nordpool data')
	vertical_line = datetime.datetime.now()
	ax.axvline(x=vertical_line, color='red')
	ax.set_ylim(min(y), max(y))
	plot_path = f'static/plot_nordpool.png'
	fig.savefig(plot_path)
	plt.close(fig)
	send_image_to_server('static/plot_nordpool.png')
	# print("Save fig!")
	# plt.show()


def plot_data_schedule(charge_schedule, nordpool_data, now, save_uniqe_plots=False):
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
	ax.set_ylim(min(y1), max(y1))
	vertical_line = datetime.datetime.now()
	ax.axvline(x=vertical_line, color='red')
	#TODO remove saving of all schedules after testing
	if save_uniqe_plots:
		plot_path = f'data/plots/plot_{now.year}-{now.month}-{now.day}_{now.hour}:{now.minute}.png'
		fig.savefig(plot_path)
	fig.savefig('static/image.png')
	plt.close(fig)
	send_image_to_server('static/image.png')
	# print("Save fig!")
	# plt.show()


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

def get_button_state():
	"""
		This function gets the state of the button from the server
			
			Returns: data
	"""

	try:
		response = requests.get(server_url + '/get_status', timeout=20)
		if response.status_code ==  200:
						data = response.json()
		else:
						print("Failed to recive data", end=" ")
						data = None
	except requests.exceptions.RequestException as e:
					print("An error occured: ", e, end=" ")
					data = None
	
	print("Web respons:", end=" ")
	if data == None:
		print("None", end=" ")	
		return None
	elif data['auto'] == 1:
		print("Auto = 1", end=" ")
	elif data['fast_smart'] == 1:
		print("Fast smart = 1", end=" ")
	elif data['on'] == 1:
		print("On = 1", end=" ")	
	elif data['full'] == 1:
		print("Full = 1", end=" ")	
	else:
		print("All = 0", end=" ")
	print(f"Hours: {data['hours']}", end=" ")			
			
	return data


def set_button_state(state):
	"""
		This function sets the state of the button on the server
			
			Arguments: state
			
			Returns: response
	"""

	try:
		response = requests.post(server_url + '/set_state', json=state).status_code
		if response == 200:
			print("Successful update state on server!")
		else:
			print("Could not update state on server!")
		return response
	except:
		print("Not able to contact server!")
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

def get_now(*args):
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
	data['auto'] = 0
	data['fast_smart'] = 0
	data['on'] = 0
	data['schedule'] = pd.DataFrame()
	data['charge'] = False
	data['charging'] = True
	data['connected'] = 0
	data['hours'] = 0
	data['set_time'] = 0
	data['fas_value'] = 1
	data['kwh_per_week'] = 50

	return data

def connected_to_lan():
	# initializing URL
	url = router_url
	timeout = 10
	try:
			# requesting URL
			request = requests.get(url,
														timeout=timeout)
			return True
	
	# catching exception
	except (requests.ConnectionError,
					requests.Timeout) as exception:
			print("Internet is off")
			return False

def next_datetime(current: datetime.datetime, hour: int, **kwargs):
    repl = current.replace(hour=hour, **kwargs)
    while repl <= current:
        repl = repl + datetime.timedelta(days=1)
    return repl

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
	txt_str = ''
	txt_str += f"Time: {now}; "
	txt_str += f"Garo: {connected}; "
	txt_str += f"Available: {available}; "
	txt_str += f"Response: "
	if response == None:
		txt_str += "None, "	
	else:
		if response['auto'] == 1:
			txt_str += "Auto = 1, "
		elif response['fast_smart'] == 1:
			txt_str += "Fast smart = 1, "
		elif response['on'] == 1:
			txt_str += "On = 1, "
		elif response['full'] == 1:
			txt_str += "Full = 1, "
		else:
			txt_str += "All = 0, "
		txt_str += f"set_time = {response['set_time']}, "
		txt_str += f"fas_value = {response['fas_value']}, "
		txt_str += f"kwh_per_week = {response['kwh_per_week']}; "

		txt_str += f"Data: "
		txt_str += f"New down load = {data['new_down_load']}, "
		txt_str += f"Auto = {data['auto']}, "
		txt_str += f"Fast smart = {data['fast_smart']}, "
		txt_str += f"On = {data['on']}, "
		txt_str += f"Remaining hours = {data['remaining_hours']}, "
		txt_str += f"Charge = {data['charge']}, "
		txt_str += f"Charging = {data['charging']}, "
		txt_str += f"Connected = {data['connected']}, "
		txt_str += f"Hours = {data['hours']}, "
		txt_str += f"Full = {data['full']}, "
		txt_str += f"AC = {data['ac']}, "
		txt_str += f"Available = {data['available']}, "	
		txt_str += f"Set time = {data['set_time']}, "
		txt_str += f"Fas value = {data['fas_value']}, "
		txt_str += f"kwh per week = {data['kwh_per_week']}; "

		if data['schedule'].empty:
			txt_str += "Schedule: None"
		else:
			txt_str += f"Schedule: YES"

		with open('data/log.txt', 'a') as f:
			f.write(txt_str + '\n')	





