from leafpy import Leaf
from pprint import pprint

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
