
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
import time
import requests
from CONFIG.config import url_garo
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import logging


def on_off_Garo(value):
	"""
	This function takes the argument value and sets 
	the Garo Charger to: "1" = on, "0" = off, "2" = Schedule
	"""	
	# TODO remove
	# For raspberry pi 
	# r'/usr/bin/chromedriver'

	options =  webdriver.ChromeOptions()
	options.add_argument('--headless')
	options.add_argument('--log-level=OFF')
	options.add_argument('--disable-infobars')
	options.add_argument('--disable-gpu')
	options.add_experimental_option('excludeSwitches', ['disable-logging'])
	driver = webdriver.Chrome(options=options)

	try:
		# For raspberry pi /usr/bin/chromedriver
		#driver = webdriver.Chrome(r'/usr/bin/chromedriver', options=options)

		
		url = url_garo + "/serialweb/"
		driver.get(url)
		time.sleep(30)

		# Click the div to reveal the select options
		controlmode_button = WebDriverWait(driver, 10).until(
			EC.element_to_be_clickable((By.ID, "controlmode-button"))
		)
		controlmode_button.click()

		# Wait for the select element to be present
		x = WebDriverWait(driver, 10).until(
		EC.presence_of_element_located((By.ID, "controlmode"))
    	)

		drop = Select(x)
		drop.select_by_value(value)

		# Verify the selected value
		selected_option = drop.first_selected_option.get_attribute("value")
		if selected_option == value:
			status_updated = True
		else:
			status_updated = False

		driver.close()
		driver.quit()
		print('Status updated in GARO!:', end=" ")
		return status_updated
	except:
		print('Not able to update status in GARO!:', end=" ")
		return False


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
		if data['connector'] == 'CHARGING_PAUSED':
			data['connector'] = "CONNECTED"
		return data['connector'], data['mode']
	except:
		print("Not able to contact wallbox!", end=" ")
		return None, None
	
def get_current_consumtion():
	"""
	This function check the power consumtion
	Return: 
	power : power consumtion in kW
	"""
	# TODO remove
	# For raspberry pi 
	# r'/usr/bin/chromedriver'

	options =  webdriver.ChromeOptions()
	options.add_argument('--headless')
	options.add_argument('--log-level=OFF')
	options.add_argument('--disable-infobars')
	options.add_argument('--disable-gpu')
	options.add_experimental_option('excludeSwitches', ['disable-logging'])

	try:
		# For raspberry pi /usr/bin/chromedriver
		#driver = webdriver.Chrome(r'/usr/bin/chromedriver', options=options)

		
		driver = webdriver.Chrome(options=options)
		url = url_garo + "/serialweb/"
		driver.get(url)
		time.sleep(20)

		div = driver.find_element(By.CLASS_NAME, "ui-collapsible-heading-toggle")
		ActionChains(driver).click(div).perform()

		x1 = driver.find_element(By.ID, "localphase1").text
		x2 = driver.find_element(By.ID, "localphase2").text
		x3 = driver.find_element(By.ID, "localphase3").text
		driver.close()
		driver.quit()

		x1 = x1.split(': ')[1]
		x2 = x2.split(': ')[1]
		x3 = x3.split(': ')[1]

		x1 = x1.split('A/')[0] 
		x2 = x2.split('A/')[0]
		x3 = x3.split('A/')[0]

		x1 = float(x1)
		x2 = float(x2)
		x3 = float(x3)

		print(f'Ström fas 1: {x1}, Ström fas 2: {x2}, Ström fas 3: {x3}', end=" ")

		return {'fas1':x1, 'fas2':x2, 'fas3':x3}
	except:
		print('Not able to update status in GARO!:', end=" ")
		return False
	


  