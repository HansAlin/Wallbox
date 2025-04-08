import sys
import os
import time
import pandas as pd
import datetime

import pickle
from GARO.garo import get_Garo_status

import CHARGE.charge as cc 

if os.getenv('PYTHONDEBUG', '0') == '1':
    test = True
else:
		argument = sys.argv[0].lower()
		if argument == "test":
			print("Program in Test mode!")
			test = True
		else:
			print("Program in normal mode!")
			test = False	
test = False
if test:
	print("Test mode")
	test_debug = cc.debug.TestDebug()
else:
	print("Normal mode")

try:
	with open('data/saved_data.pkl', 'rb') as f:
		file_content = f.read()
		data = pickle.loads(file_content)

except:
	data = cc.create_data_file()

try:
	data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'])	
except:
	data['nordpool'] = pd.DataFrame()

now, utc_offset = cc.get_now()
time_to_sleep = 15  # It is needed because asking GARO to often generates problems
print("Start or restart")

print()

if 'set_time' not in data:
	data['set_time'] = 0
if 'fas_value' not in data:
	data['fas_value'] = 1
if 'kwh_per_week' not in data:
	data['kwh_per_week'] = 50

if test:
	time_to_sleep = 0.1

_ = cc.set_button_state({'charge_type':data['charge_type'],
											'hours':data['hours'],
											'set_time':data['set_time'],
											'fas_value':data['fas_value'],
											'kwh_per_week':data['kwh_per_week']

})

while True:
	now, utc_offset = cc.get_now()
	
	if not cc.connected_to_lan(test=test):
		time.sleep(time_to_sleep)
		continue

	# Download data if neccecary
	data = cc.if_download_nordpool_data(data, now, test=test) 
	# if ( data['nordpool'].empty or \
	# 	now - data['last_down_load'] > datetime.timedelta(hours=24)) or \
	# 	(data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)) or \
	# 		(now - data['nordpool']['TimeStamp'].iloc[0] < datetime.timedelta(hours=0)) :

	# 	nordpool  = getSpotPrice(now=now, prev_data=data['nordpool'], test=test)
	# 	plot_nordpool_data(nordpool)
		
	# 	last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
	# 	if nordpool.empty: #TODO Maybe also if nordpool == data['nordpool'] then no new download
	# 		new_download = False
	# 	else:
	# 		new_download = True
	# 	data['nordpool'] = nordpool
	# 	data['last_down_load'] = last_down_load
	# 	data['new_down_load'] = new_download
		
	# Current status from GARO	
	connected, available = get_Garo_status(test=test)
	# Respons from webserver
	response = cc.get_button_state()
	if test:
		# Get combinations
		response, available, nord_pool_data, schedule, connected = test_debug.get_next_combination()
		# Update state
		data = test_debug.update_state(data, now)


	if connected == None or connected == 'CHARGING_PAUSED':
		time.sleep(time_to_sleep)
		print()
		cc.save_log(data, now, connected, available, response)
		continue
	# Response options
	# connected: "NOT_CONNECTED", "CONNECTED", "DISABLED", 'CHARGING_PAUSED', 'CHARGING_FINISHED', 'CHARGING':
	# available: "ALWAYS_OFF", "ALWAYS_ON", "SCHEMA":

	if (connected != "NOT_CONNECTED") and (connected != "CHARGING_FINISHED"):

		
		# If no response
		if response == None:
			time.sleep(time_to_sleep)
			print()
			continue

		#########################################################
		# Emergancy! Problem with the last download!					  #
		#########################################################
		if data['nordpool'].empty or data['nordpool']['TimeStamp'].iloc[-1] < now:
			print("Emergency charge!", end=" ")
			charge = True
			data['charge'] = charge
	

		#########################################################
		# If everthing was like last time										 		#	
		#########################################################
		elif cc.if_status_quo(data, response, connected):
			print("No change!", end=" ")

		###   UPDATE SCHEDULE SOMETHING CHANGED #######################
		# The response from webserver have been changed           		#
		# or the car has been connected			                      		#
		###############################################################
		else:
			print("Update schedule!", end=" ")
			data = cc.update_charge_schedule(data, response, connected)

		####################     CHARGING      ##########################
		# Determine if the car should be charged or not	acording to		  #
		# the schedule and the time now.														    #	
		#################################################################
		if  not data['schedule'].empty:
			charge = cc.ifCharge(charge_schedule=data['schedule'], now=now)
		else:
			charge = False
		
		data['charge'] = charge

		####################     NEW DOWNLOAD      ######################
		# If  new data is downloaded from nordpool. And there is still 	#
		# remaining hours to charge or still schedule										#
		#################################################################

		if data['new_down_load']:
			print("New data!", end=" ")
			if not data['schedule'].empty and \
				response['charge_type'] == 'auto':
				print("Update schedule!", end=" ")
				data = cc.update_charge_schedule(data, response, connected)


		#################################################################
		# Turn status to auto as default																#
		#################################################################
		if response['charge_type'] == 'on' or 'fast_smart' \
				and data['schedule'].empty:
			
			print("Default auto!", end=" ")
			_  = cc.set_button_state({'charge_type':response['charge_type']})

		###############      LOW TEMP			###############################
		# If the temperature is low, charge the car!										#
		# Only if temp device is connected!	Oherwise it it it return	  #
		# false.																												#													  
		#################################################################
		if cc.lowTemp():
			print("Low temp!", end=" ")
			charge = True
			data['charge'] = charge


		###################  IF SCHEDULE IS OUT OF DATE  ###################
		# If the schedule is out of date, delete it												 #
		#####################################################################
		if not data['schedule'].empty:
			if datetime.timedelta(hours=1) + data['schedule']['TimeStamp'].iloc[-1] < now:
				schedule = pd.DataFrame()
				data['schedule'] = schedule


	################### WHEN CAR STOPPED CHARGING ###################
	#																															  #
	#################################################################
	elif connected == "CHARGING_FINISHED":
		print("Charging finished!", end=" ")
		charge = False
		schedule = pd.DataFrame()

		print("Default auto!", end=" ")
		data['charge_type'] = 'auto'

		# Update webstate
		_  = cc.set_button_state({'charge_type':response['charge_type']})

		data['schedule'] = schedule
		data['charge'] = charge

	###################   WHEN CAR IS DISSCONNECTED   ###################
	#										or charging finished by car											#
	##################################################################### 	
	elif connected == "NOT_CONNECTED"  and data['connected'] != "NOT_CONNECTED" :

		charge = False
		schedule = pd.DataFrame()

		print("Default auto!", end=" ")
		data['charge_type'] = 'auto'

		# Update webstate
		_  = cc.set_button_state({'charge_type':response['charge_type']})
	
		data['schedule'] = schedule
		data['charge'] = charge
	
	elif connected == "NOT_CONNECTED" and data['connected'] == "NOT_CONNECTED":
		if available == "ALWAYS_ON":
			charge = False
			schedule = pd.DataFrame()
			data['schedule'] = schedule
			data['charge'] = charge


	###################   UPDATE CHARGE STATUS   ########################
	#																																		#
	#####################################################################
	# Considering power constraints
	if data['charge']:
		#TODO How to handle if the status is auto, fast_smart or on and how it 
		# should be influence the charging status and charging current.

		data['charge'] = cc.power_constraints(response['charge_type'])
		pass		

	charging, connected, available = cc.changeChargeStatusGaro(charging=data['charging'], 
																												charge=data['charge'], 
																												connected=connected, 
																												available=available,
																												test=test,)
	data['charging'] = charging

	new_download = False   # After the first loop of new data it turns to old
	data['new_down_load'] = new_download
	data['connected'] = connected
	data['available'] = available
	if response != None:
		data['charge_type'] = response['charge_type']
		data['hours'] = response['hours']
		data['set_time'] = response['set_time']
		data['fas_value'] = response['fas_value']
		data['kwh_per_week'] = response['kwh_per_week']
	_ = cc.set_button_state({'status':connected})
	

	with open('data/saved_data.pkl', 'wb') as f:
			pickle.dump(data,f)
	cc.save_log(data, now, connected, available, response)	
	print()
	time.sleep(time_to_sleep)
