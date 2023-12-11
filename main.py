import sys
from selenium import webdriver
import random
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
from LEAF.leaf import leaf_status, start_climat_control, stop_climat_control
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
if (args_count := len(sys.argv)) > 2:
	print(f"No more than one argument expected, got {args_count - 1}")
	print("Program in normal mode!")
	test = False
elif (args_count := len(sys.argv)) == 1:
	print("Program in normal mode!")
	test = False
else:	
	argument = sys.argv[1].lower()
	if argument == "test":
		print("Program in Test mode!")
		test = True
	else:
		print("Program in normal mode!")
		test = False
			


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
ac_timeout = now
# TODO remove after testing
data['ac'] = 0

while True:
	if test:
		time_to_sleep = 5

	now, utc_offset = get_now()

	if not connected_to_lan():
		time.sleep(time_to_sleep)
		continue

	# If it is more than 24 h since last download, download!
	 
	if ( now - data['last_down_load'] > datetime.timedelta(hours=24)) or \
		(data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)) or \
			(now - data['nordpool']['TimeStamp'].iloc[0] < datetime.timedelta(hours=0)) :

		nordpool = getDataNordPool(utc_offset=utc_offset, now=now, prev_data=data['nordpool'])
		
		last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
		new_download = True
		data['nordpool'] = nordpool
		data['last_down_load'] = last_down_load
		data['new_down_load'] = new_download
		
	connected, available = get_Garo_status()
	# Response options
	# connected: "NOT_CONNECTED", "CONNECTED", "DISABLED", 'CHARGING_PAUSED', 'CHARGING_FINISHED', 'CHARGING':
	# available: "ALWAYS_OFF", "ALWAYS_ON", "SCHEMA":
	# TODO might need to implement something that takes care of long periods of 'CHARGING_PAUSED'
		# All theses statements gives that the car is connected in some way!
	# TODO change	data['connected'] != "CONNECTED" to data['connected'] == "NOT_CONNECTED"

	#####################################################################################################
	## TODO just for testing
	#####################################################################################################
	# if test:
	# 	# b = input("Breake? (y/n)")
	# 	# if b.lower() == 'y':
	# 	# 	break 
	# 	connections = ["NOT_CONNECTED", "CONNECTED"] #, "DISABLED", 'CHARGING_PAUSED', 'CHARGING_FINISHED', 'CHARGING']
	# 	get_index = random.randrange(len(connections))
	# 	connected = connections[get_index]
	# 	print()
	# 	print()
	# 	print(f"connected: {connected}")
	# 	get_index = random.randrange(len(connections))
	# 	data['connected'] = connections[get_index]
	# 	print(f"data['connected'] = {data['connected']}")
	# 	availables = ["ALWAYS_OFF", "ALWAYS_ON", "SCHEMA"]
	# 	get_index = random.randrange(len(availables))
	# 	available = availables[get_index]
	# 	print(f"available = {available}")
	# 	remove	= random.randint(0,1)
	# 	if remove:
	# 		data['schedule'] = pd.DataFrame()
	# 		print("Schedule: False")
	# 	elif not data['schedule'].empty:
	# 		print("Schedule: True")	
	# 	else:
	# 		print("Schedule: False")	
	# 	print(f"data['charge'] = {data['charge']}")
		
	# 	time_to_sleep = 5
#########################################################################################################
##########################################################################################################

	if (connected != ("NOT_CONNECTED" or None)):

		if not lowTemp():
			# Respons from webserver
			response = get_button_state()

			# If no response
			if response == None:
				time.sleep(time_to_sleep)
				continue

			status_quo = False

			#########################################################
			# If everthing was like last time										 		#	
			#########################################################
			if response['auto'] == data['auto'] and \
				 response['full'] == data['full'] and \
				 response['fast_smart'] == data['fast_smart'] and \
				 response['on'] == data['on'] and \
				 response['hours'] == data['hours'] and \
				 response['ac'] == data['ac'] and \
				 connected == data['connected']:
				
				# If everything was like last time except that new data is downloaded from nordpool.
				if data['new_down_load'] and data['remaining_hours'] > 0:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=data['remaining_hours'], 
																										nordpool_data=data['nordpool'], 
																										now=now, pattern='auto' )
					data['schedule'] = schedule
					data['remaining_hours'] = remaining_hours

				if  not data['schedule'].empty:
					charge = ifCharge(charge_schedule=data['schedule'], now=now)
				else:
					charge = False
				
				data['charge'] = charge

			######################   AUTO         #########################	
			# The response from webserver have been changed to auto,  		#
			# or the car has been connected			                      		#
			###############################################################
			elif (response['auto'] == 1 and data['auto'] != 1) or \
				  (data['connected'] == "NOT_CONNECTED" and connected != "NOT_CONNECTED" \
					and data['auto'] == 1):
				# TODO remove afters testing
				# if not test:
				hours, soc = leaf_status(now=now, utc=utc_offset)
				# else:
				# 	hours	= random.randint(0,6)
				# 	print(f'Test hours to charge: {hours}')

				if hours > 0:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, 
																										nordpool_data=data['nordpool'], 
																										now=now, pattern='auto' )
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
				_ = set_button_state({'soc':soc})

			##################     FAST SMART       #########################
			# The response from webserver have been changed to fast_smart,	#
			# or the car has been connected and is in fast_smart mode 'on'	#		
			# and was not cached in previous statement										  #
			#################################################################
			elif (response['fast_smart'] == 1 and data['fast_smart'] != 1 ) or \
				(data['connected'] == "NOT_CONNECTED" and connected != "NOT_CONNECTED" \
		 		and data['fast_smart'] == 1 ):

				hours = response['hours']
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, 
																									 nordpool_data=data['nordpool'], 
																									 now=now, pattern='fast_smart')
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			#####################      ON          ##########################
			# The response from webserver have been changed to on,					#
			# or the car has been connected and is in on mode 'on'					#
			# and was not cached in previous statement											#
			#################################################################
			elif (response['on']== 1 and data['on'] != 1) or \
				(data['connected'] == "NOT_CONNECTED" and connected != "NOT_CONNECTED" \
		 		and data['on'] == 1):

				charge = True
				schedule,	remaining_hours = get_chargeSchedule(hour_to_charged=16, 
																									 nordpool_data=data['nordpool'], 
																									 now=now, pattern='on' )
				data['schedule'] = schedule
				data['charge'] = charge
				data['remaining_hours'] = remaining_hours

			######################      FULL     ############################
			# The response from webserver have been changed to full,				#
			# or the car has been connected and is in 'full' mode						#
			# and was not cached in previous statement											#
			#################################################################
			elif (response['full'] == 1 and data['full'] != 1) or \
				(data['connected'] == "NOT_CONNECTED" and connected != "NOT_CONNECTED" \
		 		and data['full'] == 1):

				hours, soc = leaf_status(now=now, utc=utc_offset)

				if hours > 0:
					schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, 
																										nordpool_data=data['nordpool'], 
																										now=now, 
																										pattern='full', 
																										set_time=response['set_time'] )
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

				_ = set_button_state({'soc':soc})

			#################################################################
			# There is remaing hours to charge and new prices have occured 	#
			# and the car is in auto mode																	 	#
			# TODO this might be redundant																 	#
			#################################################################	
			elif data['schedule'].empty and	response['auto'] == 1 and \
				data['remaining_hours'] > 0 and data['new_down_load']:

				hours = remaining_hours
				schedule, remaining_hours = get_chargeSchedule(hour_to_charged=hours, 
																									 df=nordpool, 
																									 now=now, 
																									 pattern='auto' )
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours

			#################################################################
			# The response is off																						#
			#################################################################	
			elif response['auto'] == 0 and response['fast_smart'] == 0 and response['on']== 0:
				schedule = pd.DataFrame()
				remaining_hours = 0
				charge = False
				data['schedule'] = schedule
				data['remaining_hours'] = remaining_hours
				data['charge'] = charge

			
			elif connected == "CHARGING":
				data['charging'] = True
			elif connected == None:
				time.sleep(time_to_sleep)
				print()
				continue	

			####################     CLIMATE CONTROLL    ####################
			# The response from webserver have been changed to ac,					#
			#################################################################
			if (response['ac'] != data['ac'] and \
						connected != "NOT_CONNECTED"):	
				if response['ac'] == 1:
					_ = start_climat_control(test=test)
					data['ac'] = 1
					ac_timeout = now + datetime.timedelta(minutes=59)
				else:	
					stop_climat_control(test=test)

					data['ac'] = 0

			if now > ac_timeout and data['ac'] == 1:
				stop_climat_control(test=test)
				data['ac'] = 0		

			if not data['schedule'].empty:
				charge = ifCharge(charge_schedule=data['schedule'], now=now)
				data['charge'] = charge


			#################################################################
			# Turn status to auto as default																#
			#################################################################
			if (response['on'] == 1 or \
			 		response['full'] == 1 or \
					response['fast_smart'] == 1) and \
						data['schedule'].empty and remaining_hours == 0:
				
				print("Default auto!", end=" ")
				_  = set_button_state({'auto':1,'fast_smart':0,'on':0, 'full':0})

			data['auto'] = response['auto']
			data['full'] = response['full']
			data['fast_smart'] = response['fast_smart']
			data['on'] = response['on']
			data['hours'] = response['hours']
			data['connected'] = connected

		# if low temp
		else:
			print("Low temp!", end=" ")
			charge = True
			data['charge'] = charge


	###################   WHEN CAR IS DISSCONNECTED   ###################
	#																																		#
	##################################################################### 	
	elif connected == "NOT_CONNECTED"  and data['connected'] != "NOT_CONNECTED":
		charge = False
		schedule = pd.DataFrame()
		remaining_hours = 0
		if response['ac'] == 1:
			stop_climat_control(test=test)
			data['ac'] = 0
		print("Default auto!", end=" ")
		data['auto'] = 1
		data['full'] = 0
		data['fast_smart'] = 0
		data['on'] = 0

		data['schedule'] = schedule
		data['remaining_hours'] = remaining_hours
		data['charge'] = charge

	
	# if test:
	# 	print()
	# 	print(f"charge = {charge}")
	# 	print(f"data['charging'] = {data['charging']}")
	charging, connected, available = changeChargeStatusGaro(charging=data['charging'], 
																												 charge=data['charge'], 
																												 now=now, 
																												 connected=connected, 
																												 available=available,
																												 test=test,
																												 utc=utc_offset)
	
		

	# If the schedule is out of date, delete it
	if not data['schedule'].empty:
		if datetime.timedelta(hours=1) + data['schedule']['TimeStamp'].iloc[-1] < now:
			schedule = pd.DataFrame()
			data['schedule'] = schedule
			hours, soc = leaf_status(now=now, utc=utc_offset)
			_ = set_button_state({'soc':soc})


	new_download = False   # After the first loop of new data it turns to old
	data['new_down_load'] = new_download
	data['connected'] = connected
	data['charging'] = charging
	
	
	with open('data/saved_data.pkl', 'wb') as f:
			pickle.dump(data,f)

	print()
	time.sleep(time_to_sleep)
