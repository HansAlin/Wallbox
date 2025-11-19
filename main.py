import sys
import os
import time
import numpy as np
import pandas as pd
import  numpy as np
import json
import datetime
import pickle
import GARO.garo as garo
import CONFIG.config as conf
import traceback
import time

import CHARGE.charge as cc
# Test 1

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
# Set timestamp to datetime
data['last_down_load'] = pd.to_datetime(data['last_down_load'])

temp = cc.Temp(time_laps=240) # Sets how often temperature should be checked


try:
	if 'nordpool' in data and not data['nordpool'].empty:
		data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'], errors='coerce')
		diff = data['nordpool']['TimeStamp'].diff().mean()
		schedule_time_delta = int(diff.total_seconds() / 60)

except:
	data['nordpool'] = pd.DataFrame()
	schedule_time_delta = 15

now, utc_offset = cc.get_now()
garo_time = now
time_to_sleep = conf.sleep_time  # It is needed because asking GARO to often generates problems
print("Start or restart")

print()

if 'set_time' not in data:
	data['set_time'] = 0
if 'fas_value' not in data:
	data['fas_value'] = 1
if 'kwh_per_week' not in data:
	data['kwh_per_week'] = 50

if test:
	time_to_sleep = 1

_ = cc.set_button_state({'charge_type':data['charge_type'],
											'hours':data['hours'],
											'set_time':data['set_time'],
											'fas_value':data['fas_value'],
											'kwh_per_week':data['kwh_per_week']

})

while True:
	try:
		now, utc_offset = cc.get_now()	

		if (now - garo_time).total_seconds() > 60:
			print('Garo updated, ', end='')
			garo.update_Garo_state()
			garo_time = now


		# if not cc.connected_to_lan(test=test):
		# 	time.sleep(time_to_sleep)
		# 	continue

		# Download data if neccecary
		data = cc.if_download_nordpool_data(data, now, test=test)
		# Set Timestamp to datetime
		data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'])


		# Current status from GARO
		connected, available = garo.get_Garo_status(test=test)
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
				print("Status quo!", end=" ")

			###   UPDATE SCHEDULE SOMETHING CHANGED #######################
			# The response from webserver have been changed           		#
			# or the car has been connected			                      		#
			###############################################################
			else:
				data = cc.update_charge_schedule(data, response, now)

			####################     CHARGING      ##########################
			# Determine if the car should be charged or not	acording to		  #
			# the schedule and the time now.														    #
			#################################################################
			if  not data['schedule'].empty:
				charge = cc.ifCharge(charge_schedule=data['schedule'], now=now, time_delta=schedule_time_delta)
				print("Got schedule", end=" ")
				if charge:
					print("and is charging, ", end=" ")
				else:
					print("and is not charging", end=" ")
			else:
				charge = False
				print("No schedule and not charging", end=" ")

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
					data = cc.update_charge_schedule(data, response, now)


			#################################################################
			# Turn status to auto as default																#
			#################################################################
			if response['charge_type'] in ('manual', 'fast_smart') and data['schedule'].empty:

				print("manual or fast_smart and schedule empty. Default auto!", end=" ")

				_  = cc.set_button_state({'charge_type': 'auto'})

			###############      LOW TEMP			###############################
			# If the temperature is low, charge the car!										#
			# Only if temp device is connected!	Oherwise it it it return	  #
			# false.																												#
			#################################################################
			if temp.lowTemp():
				print("Low temp!", end=" ")
				charge = True
				data['charge'] = charge

		################### WHEN CAR STOPPED CHARGING ###################
		#	TODO remove this after test if possible																														  #
		#################################################################
		elif connected == "CHARGING_FINISHED":
			print("Charging finished!", end=" ")
			charge = False
			schedule = pd.DataFrame()

			print("Default auto!", end=" ")
			data['charge_type'] = 'auto'

			# Update webstate
			_  = cc.set_button_state({'charge_type':'auto'})

			data['schedule'] = schedule
			data['charge'] = charge


		###################   WHEN CAR IS DISSCONNECTED   ###################
		#										or charging finished by car
		#####################################################################
		elif connected == "NOT_CONNECTED"  and data['connected'] != "NOT_CONNECTED" :

			charge = False
			schedule = pd.DataFrame()

			print("Car dissconnected. Default auto!", end=" ")
			data['charge_type'] = 'auto'

			# Update webstate
			_  = cc.set_button_state({'charge_type': 'auto'})

			data['schedule'] = schedule
			data['charge'] = charge

		elif connected == "NOT_CONNECTED" and data['connected'] == "NOT_CONNECTED":
			if available == "ALWAYS_ON":
				charge = False
				schedule = pd.DataFrame()
				data['schedule'] = schedule
				data['charge'] = charge
				# Update webstate
				_  = cc.set_button_state({'charge_type': 'auto'})

		###################   UPDATE CHARGE STATUS   ########################
		#																																		#
		#####################################################################
		# Considering power constraints
		if data['charge']:
			do_charge = cc.power_constraints(response, garo_status=connected)
		else:
			do_charge = data['charge']

		charging, connected, available = cc.changeChargeStatusGaro(charging=data['charging'],
																													charge=do_charge,
																													connected=connected,
																													available=available,
																													test=test,)
		data['charging'] = charging

		###################  IF SCHEDULE IS OUT OF DATE  ###################
		# If the schedule is out of date, delete it												 #
		#####################################################################
		if not data['schedule'].empty:
			if datetime.timedelta(minutes=15) + data['schedule']['TimeStamp'].iloc[-1] < now:
				schedule = pd.DataFrame()
				data['schedule'] = schedule
				# Set to auto
				data['charge_type'] = 'auto'
				data['charge'] = False
				# Update webstate
				_  = cc.set_button_state({'charge_type': 'auto'})
		else:
			schedule = pd.DataFrame()
			data['schedule'] = schedule
			# Save to auto
			data['charge_type'] = 'auto'
			data['charge'] = False
			# Update webstate
			_  = cc.set_button_state({'charge_type': 'auto'})

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

		#TODO make charge status go back to auto
		tmp_path = 'data/saved_data_tmp.pkl'
		path = 'data/saved_data.pkl'

		with open(tmp_path, 'wb') as f:
				pickle.dump(data, f)

		os.replace(tmp_path, path)

		data_to_save = data.copy()

		# Convert DataFrames to list-of-dicts
		for key in ['schedule', 'nordpool']:
				if key in data_to_save and isinstance(data_to_save[key], pd.DataFrame):
						df = data_to_save[key].copy()
						for col in df.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']):
								df[col] = df[col].astype(str)  # convert Timestamp to string
						data_to_save[key] = df.to_dict(orient='records')

		# Convert standalone Timestamps in data dict
		for k, v in data_to_save.items():
				if isinstance(v, pd.Timestamp):
						data_to_save[k] = str(v)

		tmp_path = 'data/saved_data_tmp.json'
		path = 'data/saved_data.json'

		with open(tmp_path, 'w') as f:
				json.dump(data_to_save, f, indent=4, default=str)

		os.replace(tmp_path, path)

		cc.save_log(data, now, connected, available, response)
		print(";")
		time.sleep(time_to_sleep)

	except Exception as e:
			print("Error:", e)
			cc.save_log({"error": str(e), "trace": traceback.format_exc()}, datetime.datetime.now(), None, None, None)
			time.sleep(10)
			continue
