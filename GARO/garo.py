
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
	options.add_argument('--disk-cache-size=0')

	try:
		# For raspberry pi /usr/bin/chromedriver
		driver = webdriver.Chrome(options=options)

		url = url_garo + "/serialweb/"
		driver.get(url)

		# Click the div to reveal the select options
		controlmode_button = WebDriverWait(driver, 30).until(
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
	except Exception as e:
		print(f'Not able to update status in GARO!: {e}', end=" ")
		return False


def get_Garo_status(test=False):
	"""
	This function check if car is connected to GARO
	Return: 
	connection : connection type
	available : if available


	"""
	if test:
		return 'CONNECTED', 'ALWAYS_OFF'

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
	options.add_argument('--disk-cache-size=0')

	try:
		# For raspberry pi /usr/bin/chromedriver
		#driver = webdriver.Chrome(r'/usr/bin/chromedriver', options=options)
		
		
		driver = webdriver.Chrome(options=options)
		url = url_garo + "/serialweb/"
		driver.get(url)

		# Wait for the element to be clickable
		wait = WebDriverWait(driver, 20)
		div = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "ui-collapsible-heading-toggle")))
		
		# Scroll the element into view
		driver.execute_script("arguments[0].scrollIntoView(true);", div)
		div.click()

		x1 = driver.find_element(By.ID, "localphase1").text
		x2 = driver.find_element(By.ID, "localphase2").text
		x3 = driver.find_element(By.ID, "localphase3").text
		driver.close()
		driver.quit()

		x1 = x1.split(': ')[1].split('A/')[0]
		x2 = x2.split(': ')[1].split('A/')[0]
		x3 = x3.split(': ')[1].split('A/')[0]
 

		x1 = float(x1)
		x2 = float(x2)
		x3 = float(x3)

		print(f'1: {x1:>5.1f} A, 2: {x2:>5.1f} A, 3: {x3:>5.1f} A', end=" ")

		return {'fas1':x1, 'fas2':x2, 'fas3':x3}
	except Exception as e:
		print(f'Not able to update status in GARO!: {e}', end=" ")
		return False
	
if __name__ == '__main__':
	# Test the functions
	on_off_Garo('1')
	on_off_Garo('0')

	get_Garo_status()
	get_current_consumtion()


  