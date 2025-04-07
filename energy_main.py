import sys
import time
import os
import ENERGY.energy_cal as ec

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

"""  WARNING: The script pygmentize is installed in '/home/hans/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location."""

while(True):

  try:
    _ = energy_cal.update(test=test)

    print()

  except Exception as e:
    print('Error: ', e)
    print('Failed to update channel')
    time.sleep(sleep_time)
    continue


  time.sleep(sleep_time)  



