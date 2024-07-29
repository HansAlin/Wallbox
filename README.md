# Wallbox
Wallbox is for anyone who has a GARO Wallbox (GLB Fixed cable Wifi) for charging their EV and that has prices on electric power from Nordpool.

The code is currently running on a UBUNTU machine. However, the goal is to implement the code on a Raspberry Pi. 

## Notes
1. In the code, there is a function that reads the temperature from a device on my roof. The reason for that is the power should be available when it is low temperature. If you don't implement temperature reader the function just returns False, it is not low temperature.
 

## Config file
In order to make the program work you have to create a config.py file and store it in the same folder as main.py. The code in config.py should look like this:

## Homepage Charger Control

# Auto

The first option is to set the Wallbox to "Auto." This option will take the lowest value of future data and compare it to the lowest value in each time window of the same size as the number of future hours. It will then take the average value of these lowest values. If the lowest value from the future data is lower than the average value of the previous lowest hours, that time is added to the schedule.

In other words, it checks whether the future lowest value is lower than the historical lowest value (with a history spanning a maximum of 4 days). The number of hours being checked is based on how many hours the car is needed per week. The hours needed per week determine a fraction that is used to decide how many hours the Wallbox should aim for each day.

Under "KWH per Week," you determine the number of kWh needed during a 5-day cycle. 

In the "Current" option, you choose the number of phases the car can take: either 1 or 3. If values are changed, you must press the "Submit" button.

# Fast Smart Charge

If turned on, the Wallbox will try to find "Hours needed" within "Charged within" hours. If values are changed, you must press the "Submit" button. When Fast Smart Charge ends, the system turns to Auto.

# Now

This option turns on charging for 16 hours and then switches to "Auto" afterward.


```

# GARO url
url_garo = "http://192.168.1.81:8080" 


# NordPool
region = 'SE3'

# url for the temperture device if any
low_temp_url = 'http://192.168.1.200'

# url for the server. Start the server.py and then find the IP address:
server_url = 'http://192.168.1.141:5000'

# url for the router if any
router_url = "http://router.asus.com/Main_Login.asp"

tz_region = 'Europe/Stockholm'
```
Change it according to your preferences.