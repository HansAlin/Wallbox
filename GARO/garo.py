from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
import time
import requests
from CONFIG.config import url_garo

def on_off_Garo(value):
	"""
	This function takes the argument value and sets 
	the Garo Charger to: "1" = on, "0" = off, "2" = Schedule
	"""	
	# Uncomment this for running
	# TODO fix this
	############################################################

	# # For raspberry pi 
	# # r'/usr/bin/chromedriver'

	# options =  webdriver.ChromeOptions()
	# options.add_argument('--headless')
	# options.add_argument('--log-level=OFF')
	# options.add_argument('--disable-infobars')
	# options.add_argument('--disable-gpu')
	# options.add_experimental_option('excludeSwitches', ['disable-logging'])

	# try:
	# 	# For raspberry pi /usr/bin/chromedriver
	# 	#driver = webdriver.Chrome(r'/usr/bin/chromedriver', options=options)

		
	# 	driver = webdriver.Chrome(options=options)
	# 	url = url_garo + "/serialweb/"
	# 	driver.get(url)
	# 	time.sleep(30)

	# 	x = driver.find_element(by=By.ID, value="controlmode")
	# 	drop = Select(x)
	# 	drop.select_by_value(value)
	# 	driver.close()
	# 	driver.quit()
	# 	print('Status updated in GARO!:', end=" ")
	# 	return True
	# except:
	# 	print('Not able to update status in GARO!:', end=" ")
	# 	return False
	############################################################
	return True

def get_Garo_status():
	"""
	This function check if car is connected to GARO
	Return: 
	connection : connection type
	available : if available


	"""
	try:
		url = url_garo + '/servlet/rest/chargebox/status?_=1'
		response = requests.get(url=url, timeout=30)
		data = response.json()

		

		if data['mode'] == "ALWAYS_OFF":
			available = 0
		elif data['mode'] == "ALWAYS_ON":
			available = 1
		elif data['mode'] == "SCHEMA":
			available = 2
		else:
			print("Error reading values from GARO wallbox!", end=" ")
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
			print("Error reading values from GARO wallbox!", end=" ")
			connection = None

		print(f"From Garo: {data['connector']} and {data['mode']}", end=" ")
		return connection, available

	except:
		print("Not able to contact wallbox!", end=" ")
		return None, None
  