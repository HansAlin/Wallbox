import sys
import os
import time
from nordpool import elspot, elbas
from pprint import pprint
import pandas as pd
import datetime

import pickle
from GARO.garo import get_Garo_status

from SpotPrice.spotprice import getSpotPrice
from CHARGE.charge import get_chargeSchedule, ifCharge, changeChargeStatusGaro, get_button_state, get_now, lowTemp, create_data_file, set_button_state, connected_to_lan, plot_nordpool_data, plot_data_schedule, get_charge_fraction, save_log
import random
import numpy as np
import DEBUG.debug as debug



"""

"""


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

if test:
	print("Test mode")
	test_debug = debug.TestDebug()
else:
	print("Normal mode")

try:
	with open('data/saved_data.pkl', 'rb') as f:
		file_content = f.read()
		data = pickle.loads(file_content)

except:
	data = create_data_file()

try:
	data['nordpool']['TimeStamp'] = pd.to_datetime(data['nordpool']['TimeStamp'])	
except:
	data['nordpool'] = pd.DataFrame()


plot_nordpool_data(data['nordpool'])
time_to_sleep = 54  # It is needed because asking GARO to often generates problems
print("Start or restart")
now, utc_offset = get_now()
print()

if 'set_time' not in data:
	data['set_time'] = 0
if 'fas_value' not in data:
	data['fas_value'] = 1
if 'kwh_per_week' not in data:
	data['kwh_per_week'] = 50

if test:
	time_to_sleep = 0.1

_ = set_button_state({'auto':data['auto'],
											'full':data['full'],
											'fast_smart':data['fast_smart'],
											'on':data['on'],
											'hours':data['hours'],
											'set_time':data['set_time'],
											'fas_value':data['fas_value'],
											'kwh_per_week':data['kwh_per_week']

})

while True:
	now, utc_offset = get_now()
	
	if not connected_to_lan(test=test):
		time.sleep(time_to_sleep)
		continue

	# If it is more than 24 h since last download, download!
	 
	if ( data['nordpool'].empty or \
		now - data['last_down_load'] > datetime.timedelta(hours=24)) or \
		(data['nordpool']['TimeStamp'].iloc[-1] - now < datetime.timedelta(hours=9)) or \
			(now - data['nordpool']['TimeStamp'].iloc[0] < datetime.timedelta(hours=0)) :

		nordpool = getSpotPrice(now=now, prev_data=data['nordpool'], test=test)
		plot_nordpool_data(nordpool)
		
		last_down_load = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
		if nordpool.empty:
			new_download = False
		else:
			new_download = True
		data['nordpool'] = nordpool
		data['last_down_load'] = last_down_load
		data['new_down_load'] = new_download
		
	# Current status from GARO	
	connected, available = get_Garo_status(test=test)
	# Respons from webserver
	response = get_button_state()
	if test:
		# Get combinations
		response, available, nord_pool_data, schedule, connected = test_debug.get_next_combination()
		# Update state
		data = test_debug.update_state(data, now)


	if connected == None or connected == 'CHARGING_PAUSED':
		time.sleep(time_to_sleep)
		print()
		save_log(data, now, connected, available, response)
		continue
	# Response options
	# connected: "NOT_CONNECTED", "CONNECTED", "DISABLED", 'CHARGING_PAUSED', 'CHARGING_FINISHED', 'CHARGING':
	# available: "ALWAYS_OFF", "ALWAYS_ON", "SCHEMA":

	if (connected != "NOT_CONNECTED") and (connected != "CHARGING_FINISHED"):

		
		# If no response
		if response == None:
			time.sleep(time_to_sleep)
			print()
			save_log(data, now, connected, available, response)
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
		elif response['auto'] == data['auto'] and \
				response['full'] == data['full'] and \
				response['fast_smart'] == data['fast_smart'] and \
				response['on'] == data['on'] and \
				response['hours'] == data['hours'] and \
				response['set_time'] == data['set_time'] and \
				response['fas_value'] == data['fas_value'] and \
				response['kwh_per_week'] == data['kwh_per_week'] and \
				 not (connected != "NOT_CONNECTED" and data['connected'] == "NOT_CONNECTED"):
				
			
			
			print("No change!", end=" ")

		######################   AUTO         #########################	
		# The response from webserver have been changed to auto,  		#
		# or the car has been connected			                      		#
		###############################################################
		elif response['auto'] == 1:

			schedule= get_chargeSchedule(hour_to_charged=12, 
																	nordpool_data=data['nordpool'], 
																	now=now, 
																	pattern='auto',
																	charge_fraction=get_charge_fraction( response['fas_value'], response['kwh_per_week']))
			data['schedule'] = schedule
			
		######################   FAST_SMART   ###########################
		# or the car has been connected and is in fast_smart mode     	#		
		# and was not cached in previous statement										  #
		#################################################################
		elif response['fast_smart']:

			hours = response['hours']
			schedule = get_chargeSchedule(hour_to_charged=hours, 
																		nordpool_data=data['nordpool'], 
																		now=now, 
																		set_time=response['set_time'],
																		pattern='fast_smart')
			data['schedule'] = schedule

		#####################      ON          ##########################
		# The response from webserver have been changed to on,					#
		# or the car has been connected and is in on mode 'on'					#
		# and was not cached in previous statement											#
		#################################################################
		elif response['on']== 1:

			schedule = get_chargeSchedule(hour_to_charged=16, 
																		nordpool_data=data['nordpool'], 
																		now=now, 
																		pattern='on' )
			data['schedule'] = schedule

		#################################################################
		# The response is off																						#
		#################################################################	
		elif response['auto'] == 0 and response['fast_smart'] == 0 and response['on']== 0:
			schedule = pd.DataFrame()
			charge = False
			data['schedule'] = schedule
			data['charge'] = charge

		####################     CHARGING      ##########################
		# Update the values from GARO to align with data in the program	#
		#################################################################
		elif connected == "CHARGING":
			data['charging'] = True


		####################     CHARGING      ##########################
		# Determine if the car should be charged or not	acording to		  #
		# the schedule and the time now.														    #	
		#################################################################
		if  not data['schedule'].empty:
			charge = ifCharge(charge_schedule=data['schedule'], now=now)
		else:
			charge = False
		
		data['charge'] = charge

		####################     NEW DOWNLOAD      ######################
		# If  new data is downloaded from nordpool. And there is still 	#
		# remaining hours to charge or still schedule										#
		#################################################################
		if data['new_down_load']:
			print("New data!", end=" ")
			if not data['schedule'].empty:
				schedule = data['schedule']
				sub_schedule = schedule[schedule['TimeStamp'] > now]
				if response['auto'] == 1:
					pattern = 'auto'
					hours_to_charged = 12
				elif response['fast_smart'] == 1:
					pattern = 'fast_smart'
					hours_to_charged = len(sub_schedule)
				elif response['on'] == 1:
					pattern = 'on'
					charged_hours = len(schedule[schedule['TimeStamp'] < now])
					hours_to_charged = 16 - charged_hours
				elif response['full'] == 1:
					pattern = 'full'
					hours_to_charged = len(sub_schedule)
			else:
				pattern = 'auto'
				hours_to_charged = 12

			schedule = get_chargeSchedule(hour_to_charged=hours_to_charged, 
																								nordpool_data=data['nordpool'], 
																								now=now, 
																								pattern=pattern,
																								set_time=response['set_time'],
																								charge_fraction=get_charge_fraction( response['fas_value'], response['kwh_per_week']))
			data['schedule'] = schedule

		#################################################################
		# Turn status to auto as default																#
		#################################################################
		if (response['on'] == 1 or \
				response['full'] == 1 or \
				response['fast_smart'] == 1) and \
					data['schedule'].empty:
			
			print("Default auto!", end=" ")
			_  = set_button_state({'auto':1,'fast_smart':0,'on':0, 'full':0})

		###############      LOW TEMP			###############################
		# If the temperature is low, charge the car!										#
		# Only if temp device is connected!	Oherwise it it it return	  #
		# false.																												#													  
		#################################################################
		if lowTemp():
			print("Low temp!", end=" ")

			if response['full'] == 1:
					if data['schedule'].empty: # We are after last charge time and car has not disconnected
						print(" and charging full!", end=" ")
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
		data['auto'] = 1
		data['fast_smart'] = 0
		data['on'] = 0
		data['full'] = 0

		# Update webstate
		_  = set_button_state({'auto':data['auto'],
												'fast_smart':data['fast_smart'],
												'on':data['on'], 
												'full':data['full']})

		data['schedule'] = schedule
		data['charge'] = charge

	###################   WHEN CAR IS DISSCONNECTED   ###################
	#										or charging finished by car											#
	##################################################################### 	
	elif connected == "NOT_CONNECTED"  and data['connected'] != "NOT_CONNECTED" :

		charge = False
		schedule = pd.DataFrame()

		print("Default auto!", end=" ")
		data['auto'] = 1
		data['fast_smart'] = 0
		data['on'] = 0
		data['full'] = 0

		_  = set_button_state({'auto':data['auto'],
												'fast_smart':data['fast_smart'],
												'on':data['on'], 
												'full':data['full']})
	
		data['schedule'] = schedule
		data['charge'] = charge
	
	elif connected == "NOT_CONNECTED" and data['connected'] == "NOT_CONNECTED":
		if available == "ALWAYS_ON":
			charge = False
			schedule = pd.DataFrame()
			data['schedule'] = schedule
			data['charge'] = charge
		else:
			print("Not connected!", end=" ")
			time.sleep(time_to_sleep)
			print()
			continue

	###################   UPDATE CHARGE STATUS   ########################
	#																																		#
	#####################################################################

	charging, connected, available = changeChargeStatusGaro(charging=data['charging'], 
																												charge=data['charge'], 
																												connected=connected, 
																												available=available,
																												test=test,)
	data['charging'] = charging

	new_download = False   # After the first loop of new data it turns to old
	data['new_down_load'] = new_download
	data['connected'] = connected
	data['available'] = available
	data['auto'] = response['auto']
	data['full'] = response['full']
	data['fast_smart'] = response['fast_smart']
	data['on'] = response['on']
	data['hours'] = response['hours']
	data['set_time'] = response['set_time']
	data['fas_value'] = response['fas_value']
	data['kwh_per_week'] = response['kwh_per_week']
	
	plot_nordpool_data(data['nordpool'])
	plot_data_schedule(data['schedule'], data['nordpool'],now)

	with open('data/saved_data.pkl', 'wb') as f:
			pickle.dump(data,f)
	save_log(data, now, connected, available, response)	
	print()
	time.sleep(time_to_sleep)
