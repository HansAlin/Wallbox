
from selenium import webdriver
# from selenium.webdriver.support.ui import Select
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options
import time
from nordpool import elspot, elbas
from pprint import pprint
import pandas as pd
# from leafpy import Leaf
import requests
import datetime
import pytz
import pickle
from bs4 import BeautifulSoup
from GARO.garo import get_Garo_status, on_off_Garo
from LEAF.leaf import leaf_status
from NordPool.nordPool import getDataNordPool
from CHARGE.charge import get_chargeSchedule, ifCharge, changeChargeStatusGaro, get_button_state, get_now, lowTemp, creta_data_file, set_button_state, connected_to_lan

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


try:
	with open('data/saved_data.pkl', 'rb') as f:
		file_content = f.read()
		data = pickle.loads(file_content)
except:
	data = creta_data_file()
data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'])	
time_to_sleep = 120  # It is needed because asking GARO to often generates problems
print("Start or restart")
now, utc_offset = get_now()
print()
while True:

	now, utc_offset = get_now()

	if not connected_to_lan():
		time.sleep(time_to_sleep)
		continue

	# If it is more than 24 h since last download, download!
	 
	if ( now - data['last_down_load'] > datetime.timedelta(hours=24)) or (data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)):

		nordpool = getDataNordPool(utc_offset=utc_offset, now=now, prev_data=data['nordpool'])
		
		last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
		new_download = True
		data['nordpool'] = nordpool
		data['last_down_load'] = last_down_load
		data['new_down_load'] = new_download
		
	connected, available = get_Garo_status()
	# Response options
	# connected: "NOT_CONNECTED", "CONNECTED", "DISABLED", 'CHARGING_PAUSED':
	# available: "ALWAYS_OFF", "ALWAYS_ON", "SCHEMA":
	# TODO might need to implement something that takes care of long periods of 'CHARGING_PAUSED'
		# All theses statements gives that the car is connected in some way!
	
	if connected != "NOT_CONNECTED":

		if not lowTemp():
			# Respons from webserver
			response = get_button_state()

			# If no response
			if response == None:
				time.sleep(time_to_sleep)
				continue

			status_quo = False

			###############################################
			# If everthing was like last time
			if response['auto'] == data['auto'] and response['fast_smart'] == data['fast_smart'] and response['on'] == data['on'] and response['hours'] == data['hours'] and connected == data['connected']:
				
				# If everything was like last time except that new data is downloaded from nordpool.
				if data['new_down_load'] and data['remaining_hours'] > 0:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=data['remaining_hours'], nordpool_data=data['nordpool'], now=now, pattern='auto' )
					data['schedule'] = schedule
					data['remaining_hours'] = remaining_hours

				if  not data['schedule'].empty:
					charge = ifCharge(charge_schedule=data['schedule'], now=now)
				else:
					charge = data['charge']

				if charge == data['charge']:
					status_quo = True
					
				data['charge'] = charge

			###############################################	
			# The response from webserver have been changed to auto,
			# or the car has been connected			
			elif (response['auto'] == 1 and data['auto'] != 1) or (data['connected'] == "NOT_CONNECTED" and connected == "CONNECTED" and data['auto'] == 1):
				hours, soc = leaf_status(now=now, utc=utc_offset)
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

			###############################################
			# The response from webserver have been changed to fast_smart,
			# or the car has been connected and is in fast_smart mode
			# and was not cached in previous statement
			elif (response['fast_smart'] == 1 and data['fast_smart'] != 1 ) or (data['connected'] == "NOT_CONNECTED" and connected == "CONNECTED" and data['fast_smart'] == 1 ):
				hours = response['hours']
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, nordpool_data=data['nordpool'], now=now, pattern='fast_smart')
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			###############################################
			# The response from webserver have been changed to on,
			# or the car has been connected and is in on mode 'on'
			# and was not cached in previous statement
			elif (response['on']== 1 and data['on'] != 1) or (data['connected'] == "NOT_CONNECTED" and connected == "CONNECTED" ):
				charge = True
				schedule,	remaining_hours = get_chargeSchedule(hour_to_charged=16, nordpool_data=data['nordpool'], now=now, pattern='on' )
				data['schedule'] = schedule
				data['charge'] = charge
				data['remaining_hours'] = remaining_hours

			###############################################
			# There is remaing hours to charge and new prices have occured
			# and the car is in auto mode
			# TODO this might be redundant
			elif data['schedule'].empty and	response['auto'] == 1 and data['remaining_hours'] > 0 and data['new_download']:
				hours = remaining_hours
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, df=nordpool, now=now, pattern='auto' )
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			###############################################
			# The response is off
			elif response['auto'] == 0 and response['fast_smart'] == 0 and response['on']== 0:
				schedule = pd.DataFrame()
				remaining_hours = 0
				charge = False
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours
				data['charge'] = charge

			# if connected == 3:
			# 	# TODO Implement something that change:
			# 	#  auto to on, on server
			# 	# data['auto'] = 1
				
			# 	charge = False
			# 	schedule = pd.DataFrame()
			# 	remaining_hours = 0
			# 	data['schedule'] = schedule
			# 	data['remaining_hours'] = remaining_hours
			# 	data['charge'] = charge

			elif connected == "CHARGING":
				data['charging'] = True
			elif connected == None:
				time.sleep(time_to_sleep)
				print()
				continue	

			if not status_quo and not data['schedule'].empty:
				charge = ifCharge(charge_schedule=data['schedule'], now=now)
				data['charge'] = charge
		
			if (response['on'] == 1 or response['fast_smart']) and data['schedule'].empty:
				# TODO implement change button state on server to auto
				print("Default auto!", end=" ")
				_  = set_button_state({'auto':1,'fast_smart':0,'on':0})

			data['auto'] = response['auto']
			data['fast_smart'] = response['fast_smart']
			data['on'] = response['on']
			data['hours'] = response['hours']

		# if low temp
		else:
			print("Low temp!", end=" ")
			charge = True
			data['charge'] = charge

	else:
		charge = False
		schedule = pd.DataFrame()
		remaining_hours = 0
		data['schedule'] = schedule
		data['remaining_hours'] = remaining_hours
		data['charge'] = charge

	
	
	charging = changeChargeStatusGaro(charging=data['charging'], charge=data['charge'], now=now, available=available)
	if charging != data['charging']:
		print("Charging status is changing!", end=" ")
		time.sleep(4)
		connected, available = get_Garo_status()

	# If the schedule is out of date, delete it
	if not data['schedule'].empty:
		if datetime.timedelta(hours=1) + data['schedule']['TimeStamp'].iloc[-1] < now:
			schedule = pd.DataFrame()
			data['schedule'] = schedule

	new_download = False   # After the first loop of new data it turns to old

	data['connected'] = connected
	data['charging'] = charging
	new_download = False
	
	with open('data/saved_data.pkl', 'wb') as f:
			pickle.dump(data,f)

	print()
	time.sleep(time_to_sleep)
