from leafpy import Leaf
from pprint import pprint
import time
from CONFIG.config import username, password, region_code
import datetime

def leaf_status(now, utc):
	count = 0
	up_to_date = False
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
