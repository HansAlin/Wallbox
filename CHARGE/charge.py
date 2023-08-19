import datetime
import pandas as pd
import requests
import pytz
from bs4 import BeautifulSoup
from GARO.garo import on_off_Garo


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
		if hour_to_charged > fast_charge_limit:
			stop_charge = now + datetime.timedelta(hours=hour_to_charged)
			charge_schedule = df_sub[df_sub['TimeStamp'] < stop_charge]
		else:
			df_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=fast_charge_limit)]
			charge_schedule = df_sub.nsmallest(hour_to_charged, 'value')
			charge_schedule['TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
			charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	elif pattern == 'auto':
		if hour_to_charged > 10:
			remaining_hours = (hour_to_charged - 10)
			hour_to_charged = 10
		#TODO an algorithm that change the number of remaining hours based
		# on previous price from nordpool
		charge_schedule = df_sub.nsmallest(hour_to_charged, 'value')
		charge_schedule['TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
		charge_schedule = charge_schedule.sort_values(by='TimeStamp')

	elif pattern == 'on':
		#TODO implement
		print("Charge now", end=" ")


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
		response = requests.get('http://192.168.1.141:5000/get_status')
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
	response = requests.post('http://127.0.0.1:5000/button_state', json=state)
	return response.text

def get_now(*args):
	if args:
		now = args[0] + datetime.timedelta(minutes=20)
		print(now, end=" ")
		return now, 2
	now = datetime.datetime.now()
	print(now, end=" ")
	timezone = pytz.timezone('Europe/Stockholm')
	utc_offset = timezone.localize(now).utcoffset().seconds/3600
	return now, utc_offset


def lowTemp():
	"""
	This function get the temperture from a local device
	"""

	try:
		url = 'http://192.168.1.200'
		page = requests.get(url=url)
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