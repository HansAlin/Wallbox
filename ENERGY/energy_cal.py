from GARO.garo import get_current_consumtion
from SpotPrice.spotprice import get_current_price
from CONFIG.config import low_price
import time
import pandas as pd
import numpy as np
import datetime
import thingspeak
from CONFIG.config import channel_id, api_key
from CHARGE.charge import get_now
import json


class PowerList:
    def __init__(self):
        self._data = []
        self._old_3rd_highest = None

    # def append(self, datetime_str, power_value):
    #     self._data.append((datetime_str, power_value))

    def add(self, data):
        self._data.append(data)

    def update(self, data):
        self._data = data    

    def get(self, index=None):
        if index is None:
            return self._data
        return self._data[index]  

    @property  
    def len(self):
        return len(self._data)     

    @property
    def datetime(self):
        return [entry[0] for entry in self._data]

    @property
    def values(self):
        return [entry[1] for entry in self._data]

    @property
    def mean(self):
        return np.mean(self.values)
    
    @property
    def min(self):
        return np.min(self.values)

    @property
    def third_highest(self):
        if self.len <= 3:
            if self.len == 0 or self.min == 0:
                if self._old_3rd_highest:
                    return self._old_3rd_highest
                else:
                  return 3000
            else:
                return  self.min

        else:  
            # Convert datetime to pandas datetime series
            datetime_series = pd.to_datetime(self.datetime, format='ISO8601')

            # Create the mask based on low_price start and stop hours
            mask = (datetime_series.hour >= low_price['start']) | (datetime_series.hour < low_price['stop'])

            # Create a copy of the values array for calculation
            values_copy = np.array(self.values.copy())

            # Update the power to half in masked hours
            values_copy[mask]= values_copy[mask] / 2

            # Sort the values and return the third highest value
            sorted_values = np.sort(values_copy)
            return sorted_values[-3]

    def reset(self):
        self._data = []   

    def set_old_3rd_highest(self, value):
        self._old_3rd_highest = value  
    

class Energy:

  def __init__(self):
    
    self.ch = thingspeak.Channel(id=channel_id, api_key=api_key)
    self.power_current_hour_list = PowerList()
    self.power_month_list = PowerList()
    self.start_time = time.time()
    # Load energy stauts from file to dictionary
    try:
      self.status = self.load_status_dict_from_file()
      
      self.voltage = self.status['voltage']
      self.sleep_time = self.status['sleep_time']

      # Power
      self.power_current_hour_list.update(self.status['power_current_list'])
      self.power_current_hour_mean = self.status['power_current_mean']
      self.power_month_list.update(self.status['power_month_list'])
      self.third_highest_power = self.status['third_highest_power']
      # Energy
      self.energy_acc_hour = self.status['energy_acc_hour']
      self.energy_month_list = self.status['energy_month_list']

      self.current_hour = self.status['current_hour']
      self.current_month = self.status['current_month']

      

    except:
      self.voltage = 230  
      self.sleep_time = 15
      # Power
      #self.power_current_hour_list.add([])
      self.power_current_hour_mean = 0
      #self.power_month_list.add([])
      self.third_highest_power = 3000
      # Energy
      self.energy_acc_hour = 0
      self.energy_month_list = []

      self.current_hour = 0
      self.current_month = 0




  def update(self, test):
    if test:
       print("Test mode") 
    now, utc_off = get_now()
    current = get_current_consumtion(test)
    if current == None:
      return None
    power = self.get_power(current)
    energy = self.get_energy_consumtion(power)



    # New hour
    if self.current_hour != now.hour:
      # Update current hour
      self.current_hour = now.hour
      one_hour = datetime.timedelta(hours=1)
      # Update power with timestamp
      one_hour_ago = now - one_hour
      one_hour_ago = one_hour_ago.replace(minute=0, second=0, microsecond=0)
      self.power_month_list.add([str(one_hour_ago), self.power_current_hour_mean])

      # Update energy
      self.energy_month_list.append((str(one_hour_ago), self.energy_acc_hour))

      # Update thingspeak
      self.ch.update({6: self.energy_acc_hour, 7: get_current_price(now).iloc[0], 8:self.power_current_hour_mean})
      self.energy_acc_hour = 0
      self.power_current_hour_list.reset()
      self.power_current_hour_mean = 0

    # New month

    if self.current_month != now.month:

      self.power_month_list.set_old_3rd_highest(self.power_month_list.third_highest)
      self.power_month_list.reset()
      self.current_month = now.month



    # Energy
    self.energy_acc_hour += energy

    # Power
    self.power_current_hour_list.add([str(now), (power['1']+ power['2']+ power['3'])])
    self.power_current_hour_mean = self.power_current_hour_list.mean
    self.third_highest_power = self.power_month_list.third_highest

    # Update thingspeak
    self.ch.update({1: power['1'], 2: power['2'], 3: power['3'], 4: self.power_current_hour_mean , 5: self.third_highest_power})


    # Print status
    print(f"Power: {power['1']+ power['2']+ power['3']:>7.1f} W, Mean power: {self.power_current_hour_mean:>7.1f} W, Third highest power: {self.third_highest_power:>7.1f} W", end=" ")
    # Save status to file
    self.save_status_dict_to_file()
      
  def save_status_dict_to_file(self, test=False):
    # Convert the datetame tom string

    status = {
      'voltage': self.voltage,
      'sleep_time': self.sleep_time,
      'power_current_list': self.power_current_hour_list.get(),
      'power_current_mean': self.power_current_hour_mean,
      'power_month_list': self.power_month_list.get(),
      'third_highest_power': self.third_highest_power,
      'energy_acc_hour': self.energy_acc_hour,
      'energy_month_list': self.energy_month_list,
      'current_hour': self.current_hour,
      'current_month': self.current_month
    }
    path = 'data/energy_status.json'
    with open(path, 'w') as f:
      json.dump(status, f)

  def get_power_mean(self):
    return self.power_current_hour_mean

  def load_status_dict_from_file(self, test=False):
    if test:
      path = 'data/energy_status_test.json'
    else:
      path = 'data/energy_status.json'
    with open(path, 'r') as f:
      status = json.load(f)

    return status

  def get_power(self, current):
    """
    This function calculates the power consumption in W

    """

    voltage = 230

    if type(current) != bool:
      power_1 = current['fas1'] * voltage
      power_2 = current['fas2'] * voltage
      power_3 = current['fas3'] * voltage

      return {'1': power_1, '2': power_2, '3': power_3}
    else:
      return None
      
  def get_energy_consumtion(self, power):

    elapsed_time = time.time() - self.start_time   
    self.start_time = time.time()  
    print(f"Time: {elapsed_time:>5.0f} s", end=" ")
    
    current_energy = (power['1'] + power['2'] + power['3']) * elapsed_time / 3600

    print(f"E: {current_energy:>5.1f} Wh", end=" ")

    return current_energy

if __name__ == "__main__":
  energy = Energy()

  energy.current_hour
  energy.update(time.time(), test=True)    