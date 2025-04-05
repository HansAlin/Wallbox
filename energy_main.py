import sys
import time
import datetime
import thingspeak
import os

from GARO.garo import get_current_consumtion, get_Garo_status
from SpotPrice.spotprice import load_data, getSpotPrice, save_data, get_nordpool_data, get_current_price
from CHARGE.charge import get_now
from CONFIG.config import channel_id, api_key
import energy_cal as ec

test=False
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


print('Starting energy calculation')
energy_cal = ec.Energy()
sleep_time = energy_cal.sleep_time



while(True):

  #try:
  _ = energy_cal.update(test=test)

  print()

  # except Exception as e:
  #   print('Error: ', e)
  #   print('Failed to update channel')
  #   time.sleep(sleep_time)
  #   continue


  time.sleep(sleep_time)  



