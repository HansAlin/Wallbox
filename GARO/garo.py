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
	## TODO remove
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

		print(f"From Garo: {data['connector']} and {data['mode']}", end=" ")
		return data['connector'], data['mode']
	except:
		print("Not able to contact wallbox!", end=" ")
		return None, None
  