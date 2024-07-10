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
from CONFIG.config import low_temp_url, server_url, tz_region
# from LEAF.leaf import leaf_status


def get_value_lim(nordpool_data, now):
	prev_data = nordpool_data[nordpool_data['TimeStamp'] < now]
	value_lim = prev_data['value'].mean()
	value_lim = max([value_lim, 10])
	return value_lim


def get_chargeSchedule(hour_to_charged, nordpool_data, now, pattern, set_time=None, value_lim=82):

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
	print(f"Getting charging schedule at: {now}", end=" ")

	#TODO Creat a function that calculates the value lim besed on previus week data
	# value_lim = get_value_lim(nordpool_data, now)

	nordpool_data['TimeStamp'] = pd.to_datetime(nordpool_data['TimeStamp']).dt.tz_localize(None)
	df_sub = nordpool_data[nordpool_data['TimeStamp'] >= datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour)] 
	last_time_stamp = df_sub['TimeStamp'].iloc[-1]

	hours_to_last_time_stamp = int((last_time_stamp.tz_localize(None) - now.replace(tzinfo=None)).total_seconds()/3600)
	if hours_to_last_time_stamp > 12:
		hours_to_last_time_stamp = 12

	charge_limit = 12

	value_lim = np.min([value_lim, get_value_lim(nordpool_data, now)])

	if pattern == 'fast_smart':
		# TODO Still uses all data and not a small sub set
		if hour_to_charged > charge_limit:
			stop_charge = now + datetime.timedelta(hours=hour_to_charged)
			charge_schedule = df_sub[df_sub['TimeStamp'] < stop_charge]
		else:
			df_sub_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=set_time)]
			charge_schedule = df_sub_sub.nsmallest(hour_to_charged, 'value')


	elif pattern == 'auto':
		charge_schedule = pd.DataFrame()
		schedule_found = False
		hours_to_charge = hours_to_last_time_stamp
		while not schedule_found:

			df_sub_smallest = df_sub.nsmallest(hours_to_charge, 'value')
			value_sum = df_sub_smallest['value'].sum()
			if value_sum < value_lim:
				charge_schedule = df_sub_smallest
				schedule_found = True

			hours_to_charge = hours_to_charge - 1

	elif pattern == 'full':
		if set_time == None:
			next_hour = (now.hour + 12) % 24
		else:	
			next_hour = set_time
		next_day = next_datetime(now, next_hour)
		next_day = next_day.replace(minute=0, second=0, microsecond=0 )

		if next_day - now > datetime.timedelta(hours=hour_to_charged):
			df_sub_sub = df_sub[df_sub['TimeStamp'] < next_day]
			charge_schedule = df_sub_sub.nsmallest(hour_to_charged, 'value')
		else:
			df_sub_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=(hour_to_charged - 1))]
			charge_schedule = df_sub_sub.nsmallest(hour_to_charged, 'value')

	elif pattern == 'on':
		#TODO test
		hours_on = 16
		print("Charge now", end=" ")
		df_sub_sub = df_sub[df_sub['TimeStamp'] < now + datetime.timedelta(hours=hours_on)]
		charge_schedule = df_sub_sub


	charge_schedule.loc[:, 'TimeStamp'] = pd.to_datetime(charge_schedule['TimeStamp'])
	charge_schedule = charge_schedule.sort_values(by='TimeStamp')


	print(f"Value lim: {value_lim}, Charging schedule:")
	print(charge_schedule)
	plot_data_schedule(charge_schedule, df_sub, now)
	with  open('data/schedule_log.csv', 'a') as f:
		f.write(str({'TimeStamp':now,'schedule':charge_schedule['TimeStamp']} ))
	return pd.DataFrame(charge_schedule['TimeStamp'])	




def plot_data_schedule(charge_schedule, noorpool_data, now):
	hh = DateFormatter('%H')
	x1 = noorpool_data['TimeStamp'].values
	y1 = noorpool_data['value'].values
	fig, ax = plt.subplots()
	ax.xaxis.set_major_formatter(hh)
	ax.scatter(x1, y1 , color='blue')
	x2 = charge_schedule['TimeStamp'].values
	y2 = charge_schedule['value'].values
	ax.scatter(x2, y2, color='green')
	plot_path = f'data/plots/plot_{now.year}-{now.month}-{now.day}_{now.hour}:{now.minute}.png'
	fig.savefig(plot_path)
	fig.savefig('static/image.png')
	send_image_to_server('static/image.png')
	print("Save fig!")
	#plt.show()


def ifCharge(charge_schedule, now):
	charge_schedule = pd.DataFrame(charge_schedule)

	for row in charge_schedule['TimeStamp']:

		t_stamp = row
		if datetime.timedelta(hours=0) <= (now - t_stamp) < datetime.timedelta(hours=1):
			return True

	return False

def changeChargeStatusGaro(charging, charge, connected, available, test):

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

def send_image_to_server(image_path):
    try:
        with open(image_path, 'rb') as img:
            response = requests.post(server_url + '/upload_image', files={'image': img})
        if response.status_code == 200:
            print("Successfully uploaded image to server!")
        else:
            print("Could not upload image to server!")
        return response.status_code
    except:
        print("Not able to contact server!")
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
	This function get the temperture from a local device
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

def next_datetime(current: datetime.datetime, hour: int, **kwargs):
    repl = current.replace(hour=hour, **kwargs)
    while repl <= current:
        repl = repl + datetime.timedelta(days=1)
    return repl