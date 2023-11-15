import datetime
import pandas as pd
import requests
import pytz
from bs4 import BeautifulSoup
from GARO.garo import on_off_Garo
from CONFIG.config import low_temp_url, server_url, tz_region


def get_chargeSchedule(hour_to_charged, nordpool_data, now, pattern):
	"""
	This function creates a charging schedule based on data from nordpool (nordpool_data)
	Arguments:
		hour_to_charge: hours for setting schedule
		nordpool_data: data from nordpool
		now: current time
		pattern: which type of charging pattern available, 'auto', 'fast_smart', 'now'
	Returns:
		schedule
		remaining_hours: if not all charging hours are fitted in the first schedule

	"""
	remaining_hours = 0



	print(f"Getting charging schedule at: {now}", end=" ")

	nordpool_data['TimeStamp'] = pd.to_datetime(nordpool_data['TimeStamp']).dt.tz_localize(None)
	df_sub = nordpool_data[nordpool_data['TimeStamp'] >= datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour)] 

	fast_charge_limit = 12
	if pattern == 'fast_smart':
		# TODO Still uses all data and not a small sub set
		if hour_to_charged > fast_charge_limit:
			stop_charge = now + datetime.timedelta(hours=hour_to_charged)
			charge_schedule = df_sub[df_sub['TimeStamp'] < stop_charge]
		else:
			df_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=fast_charge_limit)]
			charge_schedule = df_sub.nsmallest(hour_to_charged, 'value')
			charge_schedule['TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
			charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	elif pattern == 'auto':
		hour_limit = 12
		if hour_to_charged > hour_limit:
			remaining_hours = (hour_to_charged - hour_limit)
			hour_to_charged = hour_limit
		#TODO an algorithm that change the number of remaining hours based
		# on previous price from nordpool
		# make the first 80 % ours chosen first and then the rest 
		charge_schedule = df_sub.nsmallest(hour_to_charged, 'value')
		charge_schedule['TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
		charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	elif pattern == 'on':
		#TODO test
		hours_on = 16
		print("Charge now", end=" ")
		df_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=hours_on)]
		charge_schedule = df_sub
		charge_schedule['TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
		charge_schedule = charge_schedule.sort_values(by='TimeStamp')


	print(f"Charging schedule {charge_schedule['TimeStamp']}", end=" ")

	print(f'With remaining hours {remaining_hours}', end=" ")
	with  open('data/schedule_log.csv', 'a') as f:
		f.write(str({'TimeStamp':now,'schedule':charge_schedule['TimeStamp']} ))
	return pd.DataFrame(charge_schedule['TimeStamp']), remaining_hours

def ifCharge(charge_schedule, now):
	charge_schedule = pd.DataFrame(charge_schedule)

	for row in charge_schedule['TimeStamp']:

		t_stamp = row
		if datetime.timedelta(hours=0) <= (now - t_stamp) < datetime.timedelta(hours=1):
			return True

	return False

def changeChargeStatusGaro(charging, charge, now, available):
	if charging and not available:
		charging = False

	if charging == True and charge == False:
		turn_on_value = "0"
		charging = False


		response = on_off_Garo(turn_on_value)
		if not response:
			charging = True
			print("Status not changed at GARO!", end=" ")
		else:
			print(f"Garo turned off at: {now}", end=" ")

	if charging == False and charge  == True:
		turn_on_value = "1"
		charging = True

		response = on_off_Garo(turn_on_value)
		if not response:
			charging = False
			print("Status not changed at GARO!", end=" ")
		else:
			print(f"Garo turned on at: {now}", end=" ")

	return charging

def get_button_state():

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
	return data

def set_button_state(state):
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

def get_now(*args):
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
	This function get the temperture from a local device
	"""

	try:
		url = low_temp_url
		page = requests.get(url=url, timeout=20)
		soup = BeautifulSoup(page.content, "html.parser")
		data = soup.find_all("p")[0].text
		temp = data.split(' ')[1]
		temp = float(temp)

		if temp < -20:
			return True
		else:
			return False
	except:
		return False	

def creta_data_file():
	data = {}

	data['nordpool'] = pd.DataFrame()
	data['last_down_load'] = datetime.datetime.now() - datetime.timedelta(hours=24)
	data['new_down_load'] = False 
	data['auto'] = 0
	data['fast_smart'] = 0
	data['on'] = 0
	data['schedule'] = pd.DataFrame()
	data['remaining_hours'] = 0
	data['charge'] = False
	data['charging'] = True
	data['connected'] = 0
	data['hours'] = 0

	return data

def connected_to_lan():
	# initializing URL
	url = "http://router.asus.com/Main_Login.asp"
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
