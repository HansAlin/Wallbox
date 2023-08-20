from leafpy import Leaf
from pprint import pprint

def leaf_status():
	try:
		leaf = Leaf(username='hansalin@gmail.com', password='L@ngdrag00', region_code='NE')
		r = leaf.BatteryStatusRecordsRequest()
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
