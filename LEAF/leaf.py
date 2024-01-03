from leafpy import Leaf
from pprint import pprint
import time
from CONFIG.config import username, password, region_code
from CHARGE.charge import set_button_state, get_temp
import datetime
import os
import pandas as pd

def leaf_status(now, utc):
	count = 0
	up_to_date = False
	r = {}
	try:
		while(count < 5 and not up_to_date):
			leaf = Leaf(username=username, password=password, region_code=region_code)
			time.sleep(2)
			r = leaf.BatteryStatusRecordsRequest()
			
			# Check if data is up to date
			targetdate = r['BatteryStatusRecords']['TargetDate']
			targetdate = datetime.datetime.strptime(targetdate, '%Y/%m/%d %H:%M') + datetime.timedelta(hours=utc)
			if (now - targetdate ) < datetime.timedelta(seconds=900):
				up_to_date = True
			else:
				time.sleep(60)	
			count += 1 
		pprint(r)
		save_data(r)	
	except:
		return -1, -1
	
	try:
		soc = int(r['BatteryStatusRecords']['BatteryStatus']['SOC']['Value'])
		
		if soc == 100:
			return 0, soc
	except:
		print("Not poosible to read SOC status")
		soc = 0	
		charging_hours = 15
	# TODO fix this
	try:
		charging_hours = int(r['BatteryStatusRecords']['TimeRequiredToFull200']['HourRequiredToFull'])
	except:
		charging_hours = int((100 - soc)/100*15)
	if charging_hours != 0:
		charging_hours = charging_hours + 1
	
	# TODO This might be needed to uncomment
	# leaf.BatteryRemoteChargingRequest()
	print(f"Charging hours: {charging_hours}", end=" ")
	return charging_hours, soc

def start_climat_control(test=False):
	count = 0
	
	try:
		
		while (count < 5 ):
			if not test:
				leaf = Leaf(username=username, password=password, region_code=region_code)
				response = leaf.ACRemoteRequest()
			else:
				response = {'status':200}	
			
			if response['status'] == 200:
				print("Climat control started ", end="")
				_ = set_button_state({'auto':0,'fast_smart':0,'on':1, 'full':0})
				return 1
			else:
				time.sleep(60)
			count += 1	
		print("Not possible to start climat control ", end="")	
		return -1
	except:
		print("Not possible to start climat control ", end="")
		return -1	

def stop_climat_control(test=False):
	count = 0
	try:
		while (count < 5 ):
			if not test:
				leaf = Leaf(username=username, password=password, region_code=region_code)
				response = leaf.ACRemoteOffRequest()
			else:
				response = {'status':200}	

			if response['status'] == 200:
				print("Climat control stopped ", end="")
				_ = set_button_state({'auto':1,'fast_smart':0,'on':0, 'full':0, 'ac':0})
				return 1
			else:
				time.sleep(60)
		
		print("Not possible to stop climat control ", end="")

		return -1
		
	except:
		print("Not possible to stop climat control ", end="")
		return -1	


def save_data(data):
	path = 'data/leaf_data.csv'
	dir_path = os.path.dirname(path)
	isExist = os.path.exists(path)
	data_frame = {}
	data_frame['SOC'] = data['BatteryStatusRecords']['BatteryStatus']['SOC']['Value']
	data_frame['kwh'] = data['BatteryStatusRecords']['BatteryStatus']['BatteryRemainingAmountWH']
	data_frame['amount'] = data['BatteryStatusRecords']['BatteryStatus']['BatteryRemainingAmount']
	data_frame['capacity'] = data['BatteryStatusRecords']['BatteryStatus']['BatteryCapacity']
	data_frame['range_ac_on'] = data['BatteryStatusRecords']['CruisingRangeAcOn']
	data_frame['range_ac_off'] = data['BatteryStatusRecords']['CruisingRangeAcOff']
	data_frame['timestamp'] = data['BatteryStatusRecords']['TargetDate']
	data_frame['temp'] = get_temp()
	
	df = pd.DataFrame([data_frame])  # Convert dictionary to DataFrame


	if not isExist:
		os.makedirs(dir_path, exist_ok=True)  # Create directory if it doesn't exist
		print("The new directory is created!")
		df.to_csv(path, index=False)

		
	else:
		old_data_frame = pd.read_csv(path)
		new_data_frame = pd.concat([old_data_frame, df], axis=0, ignore_index=True)
		new_data_frame.to_csv(path, index=False)
	
	