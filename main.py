
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from nordpool import elspot, elbas
from pprint import pprint
import pandas as pd
from leafpy import Leaf
import requests
import datetime
import pytz
import pickle
from bs4 import BeautifulSoup

print()
"""
Leafpy: Current url in auth.py is url = "https://gdcportalgw.its-mo.com/api_v210707_NE/gdc/UserLoginRequest.php"
        and in leaf.py BASE_URL = 'https://gdcportalgw.its-mo.com/api_v210707_NE/gdc/'
        these two url:s might have changed
        And in auth.py following changes have to be made:
        From:
            if region_code == 'NE':
              custom_sessionid = r.json()['vehicleInfo'][0]['custom_sessionid']
            else:
              custom_sessionid = r.json()['VehicleInfoList']['vehicleInfo'][0]['custom_sessionid']
            VIN = r.json()['CustomerInfo']['VehicleInfo']['VIN']
        To: 
            custom_sessionid = r.json()['VehicleInfoList']['vehicleInfo'][0]['custom_sessionid']
	          VIN = r.json()['CustomerInfo']['VehicleInfo']['VIN']
"""




### Turn on of charger ######
def on_off_Garo(value):
	"""
	This function takes the argument value and sets 
	the Garo Charger to: "1" = on, "0" = off, "2" = Schedule
	"""	
	# For raspberry pi 
	# r'/usr/bin/chromedriver'

	options =  webdriver.ChromeOptions()
	options.add_argument('--headless')
	options.add_argument('--log-level=OFF')
	options.add_argument('--disable-infobars')
	options.add_argument('--disable-gpu')
	options.add_experimental_option('excludeSwitches', ['disable-logging'])

	try:
		# For raspberry pi /usr/bin/chromedriver
		#driver = webdriver.Chrome(r'/usr/bin/chromedriver', options=options)
		driver = webdriver.Chrome(options=options)
		
		driver.get("http://192.168.1.81:8080/serialweb/")
		time.sleep(20)

		x = driver.find_element(by=By.ID, value="controlmode")
		drop = Select(x)
		drop.select_by_value(value)
		driver.close()
		driver.quit()
		return True
	except:
		print('No connection to GARO:', end=" ")
		return False

def get_Garo_status():
	"""
	This function check if car is connected to GARO
	Return: 
	connection : connection type
	available : if available


	"""
	try:
		url = 'http://192.168.1.81:8080/servlet/rest/chargebox/status?_=1'
		response = requests.get(url=url)
		data = response.json()


		if data['mode'] == "ALWAYS_OFF":
			available = 0
		elif data['mode'] == "ALWAYS_ON":
			available = 1
		elif data['mode'] == "SCHEMA":
			available = 2
		else:
			print("Error reading values from GARO wallbox!")
			available = None

		if data['connector'] == "NOT_CONNECTED":
			connection = 0
		# TODO might need to implement something that takes care of long periods of 'CHARGING_PAUSED'
		# All theses statements gives that the car is connected in some way!  
		elif data['connector'] == "CONNECTED" or data['connector'] == "DISABLED" or data['connector'] == 'CHARGING_PAUSED':
			connection = 1
		elif data['connector'] == "CHARGING"  :
			connection = 2
		elif data['connector'] == 'CHARGING_FINISHED':
			connection = 3
		else:
			print("Error reading values from GARO wallbox!")
			connection = None


		return connection, available

	except:
		print("No available to contact wallbox!", end=" ")
		return None, None
  
## Get data from NordPool #####
def getDataNordPool(utc_offset, now, prev_data):

	print(f"Downloaded data from Nordpool at: {now}", end=" ")
	"""
	"""
	# TODO remove redundant code and eliminate repeated code!
	try:
		if prev_data.empty:
			prices_bas = elbas.Prices()
			
			end_date = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
			prices = prices_bas.hourly(end_date=end_date, areas=['SE3'])
			last = prices['areas']['SE3']['Last']
			pprint(last)
			timestamp = []
			price = []
			for element in last:
				timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
				price.append(element['value'])
			df = pd.DataFrame({'TimeStamp':timestamp, 'value':price}) 
			df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

			with open('data/log_nordpool.pkl', 'wb') as f:
				pickle.dump(df,f)
			
			return df


		else:
			prices_spot = elspot.Prices()

			prices = prices_spot.hourly(areas=['SE3'])
			pprint(prices)
			timestamp = []
			price = []
			values = prices['areas']['SE3']['values']
			for element in values:
					timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
					price.append(element['value'])
			new_data = pd.DataFrame({'TimeStamp':timestamp, 'value':price})
		
			new_data['TimeStamp'] = pd.to_datetime(new_data['TimeStamp']).dt.tz_localize(None)

			first_time_stamp = new_data['TimeStamp'].iloc[0]
			value = new_data['value'].iloc[0]
	
			prev_data['TimeStamp'] = pd.to_datetime(prev_data['TimeStamp'])
			last_time_stamp = prev_data['TimeStamp'].iloc[-1]
			t = type(value)
			if value < 100000:		# Sometimes the returned values from Nordpool have inf values
				last_day = last_time_stamp.day
				one_day = datetime.timedelta(hours=24)
				first_day = first_time_stamp.day
				
				#if last_time_stamp.day + datetime.timedelta(hours=24) == first_time_stamp.day:
				if last_day + 1 == first_day:
					with open('data/log_nordpool.pkl', 'rb') as f:
						log_nordpool = pickle.load(f)
					concat_df = pd.concat([prev_data, new_data], axis=0, ignore_index=True)
					log_nordpool = pd.concat([log_nordpool, new_data], axis=0, ignore_index=True)

					concat_df = concat_df.reset_index(drop=True)
					log_nordpool = log_nordpool.reset_index(drop=True)
					concat_df = concat_df.iloc[-96:,]
	
					with open('data/log_nordpool.pkl', 'wb') as f:
						pickle.dump(log_nordpool,f)
					log_nordpool.to_csv('data/log_nordpool.csv')
					
					return concat_df
				else:
					# If not the new data is aligned with the old data
					# Try to compacted the code!
					prices_bas = elbas.Prices()
					
					end_date = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
					prices = prices_bas.hourly(end_date=end_date, areas=['SE3'])
					last = prices['areas']['SE3']['Last']
					pprint(last)
					timestamp = []
					price = []
					for element in last:
						timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
						price.append(element['value'])
					df = pd.DataFrame({'TimeStamp':timestamp, 'value':price}) 
					df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

					with open('data/log_nordpool.pkl', 'wb') as f:
						pickle.dump(df,f)
					
					return df
					

			return prev_data
	except:
		print("Could not get data from Nordpool:")	
		return prev_data


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

def leaf_status():
	try:
		leaf = Leaf(username='hansalin@gmail.com', password='L@ngdrag00', region_code='NE')
		r = leaf.BatteryStatusRecordsRequest()
	except:
		return -1
	soc = int(r['BatteryStatusRecords']['BatteryStatus']['SOC']['Value'])
	if soc == 100:
		return 0
	# TODO fix this
	charging_hours = int(r['BatteryStatusRecords']['TimeRequiredToFull200']['HourRequiredToFull'])

	if charging_hours != 0:
		charging_hours = charging_hours + 1
	pprint(r)
	# TODO This might be needed to uncomment
	# leaf.BatteryRemoteChargingRequest()
	print(f"Charging hours: {charging_hours}", end=" ")
	return charging_hours

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

try:
	with open('data/saved_data.pkl', 'rb') as f:
		file_content = f.read()
		data = pickle.loads(file_content)
except:
	data = creta_data_file()
data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'])	
time_to_sleep = 120
print("Start or restart")
now, utc_offset = get_now()
print()
while True:

	# Time TODO remove if statement and replace with now


	now, utc_offset = get_now()

	# If it is more than 24 h since last download, download!
	 
	if ( now - data['last_down_load'] > datetime.timedelta(hours=24)) or (data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)):

		nordpool = getDataNordPool(utc_offset=utc_offset, now=now, prev_data=data['nordpool'])
		
		
		last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
		new_download = True
		data['nordpool'] = nordpool
		data['last_down_load'] = last_down_load
		data['new_down_load'] = new_download
		



	connected, available = get_Garo_status()
	
	if connected != 0:

		if not lowTemp():
			# Respons from webserver
			response = get_button_state()
			print(f"Respons: {response}", end=" ")
			# If no response
			if response == None:
				time.sleep(time_to_sleep)
				continue

			status_quo = False
			
			if response['auto'] == data['auto'] and response['fast_smart'] == data['fast_smart'] and response['on'] == data['on'] and response['hours'] == data['hours'] and connected == data['connected']:
				if data['new_down_load'] and data['remaining_hours'] > 0 and data['schedule'].empty:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=data['remaining_hours'], nordpool_data=data['nordpool'], now=now, pattern='auto' )
					data['schedule'] = schedule
					data['remaining_hours'] = remaining_hours

				if  not data['schedule'].empty:
					charge = ifCharge(charge_schedule=data['schedule'], now=now)
				else:
					charge = data['charge']
				data['charge'] = charge
				status_quo = True
				print("Status quo!", end=" ")

			elif (response['auto'] == 1 and data['auto'] != 1):
				hours = leaf_status()
				if hours > 0:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, nordpool_data=data['nordpool'], now=now, pattern='auto' )
				elif hours == 0:
					schedule = pd.DataFrame()
					remaining_hours = 0
					charge = False
					data['charge'] = charge
				else:
					with open('data/saved_data.pkl', 'wb') as f:
						pickle.dump(data,f)
					time.sleep(time_to_sleep)
					continue

				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			elif (response['fast_smart'] == 1 and data['fast_smart'] != 1) :
				hours = response['hours']
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, nordpool_data=data['nordpool'], now=now, pattern='fast_smart')
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			elif response['on']== 1 and data['on'] != 1:
				charge = True
				schedule = pd.DataFrame()
				remaining_hours = 0
				data['charge'] = charge
				data['remaining_hours'] = remaining_hours

			elif data['schedule'].empty and	response['auto'] == 1 and data['remaining_hours'] > 0 and data['new_download']:
				hours = remaining_hours
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, df=nordpool, now=now, pattern='auto' )
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			elif response['auto'] == 0 and response['fast_smart'] == 0 and response['on']== 0:
				schedule = pd.DataFrame()
				remaining_hours = 0
				charge = False
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours
				data['charge'] = charge

			if connected == 3:
				# TODO Implement something that change:
				#  auto to on, on server
				# data['auto'] = 1
				print("Car connected but charge finnished by car!", end=" ")
				charge = False
				schedule = pd.DataFrame()
				remaining_hours = 0
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours
				data['charge'] = charge

			if connected == 2:
				data['charging'] = True

			if not status_quo and not data['schedule'].empty:
				charge = ifCharge(charge_schedule=data['schedule'], now=now)
				data['charge'] = charge

			data['auto'] = response['auto']
			data['fast_smart'] = response['fast_smart']
			data['on'] = response['on']
			data['hours'] = response['hours']

		# if low temp
		else:
			print("Low temp!")
			charge = True
			data['charge'] = charge

	elif connected == 0:
		print("Car not connected!", end=" ")
		charge = False
		schedule = pd.DataFrame()
		remaining_hours = 0
		data['schedule'] = schedule
		data['remaining_hours'] = remaining_hours
		data['charge'] = charge




	elif connected == None:
		time.sleep(time_to_sleep)
		continue

		
	
	charging = changeChargeStatusGaro(charging=data['charging'], charge=data['charge'], now=now, available=available)
	if charging != data['charging']:
		time.sleep(4)
		connected, available = get_Garo_status()
	if charging:
		print("Charging!", end=" ")
	else:
		print("Not charging!", end=" ")


	if not data['schedule'].empty:
		if datetime.timedelta(hours=1) + data['schedule']['TimeStamp'].iloc[-1] < now:
			schedule = pd.DataFrame()
			data['schedule'] = schedule



	new_download = False   # After the first loop of new data it turns to old

	data['connected'] = connected
	data['charging'] = charging
	new_download = False
	
	# data['charging'] = charging
	

	with open('data/saved_data.pkl', 'wb') as f:
			pickle.dump(data,f)

	# try:
	# 	with open('data/data_log.pkl', 'rb') as f:
	# 		file_content = f.read()
	# 		data_log = pickle.loads(file_content)

	# 		data_log['last_down_load'].append(data['last_down_load'])
	# 		data_log['new_down_load'].append(data['new_down_load'])
	# 		data_log['auto'].append(data['auto'])
	# 		data_log['fast_smart'].append(data['fast_smart'])
	# 		data_log['on'].append(data['on'])
	# 		data_log['remaining_hours'].append(data['remaining_hours'])
	# 		data_log['charge'].append(data['charge'])
	# 		data_log['charging'].append(data['charging'])
	# 		data_log['connected'].append(data['connected'])
	# 		data_log['hours'].append(data['hours'])
	# 		data_log['TimeStamp'].append(data['TimeStamp'])

	# 	with open('data/data_log.pkl', 'wb') as f:
	# 		pickle.dump(data_log,f)
	# except:
	# 	with open('data/data_log.pkl', 'wb') as f:
	# 		pickle.dump(data,f)


	print()
	time.sleep(time_to_sleep)
