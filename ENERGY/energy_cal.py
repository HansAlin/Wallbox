from GARO.garo import get_current_consumtion
from SpotPrice.spotprice import get_current_price
from CONFIG.config import low_price, energy_price, power_price
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
    self.energy_hour_list = PowerList()
    self.energy_acc_hour = 0
    self.energy_month_list = PowerList()
    self.cost_month_list = PowerList()
    self.cost_hour_list = PowerList()
    self.start_time = time.time()
    
    # Load energy status from file to dictionary
    try:
        self.status = self.load_status_dict_from_file()

        self.voltage = self.status.get('voltage', 230)
        self.sleep_time = self.status.get('sleep_time', 15)

        # Power
        self.power_current_hour_list.update(self.status.get('power_current_list', []))
        self.power_current_hour_mean = self.status.get('power_current_mean', 0)
        self.power_month_list.update(self.status.get('power_month_list', []))
        self.third_highest_power = self.status.get('third_highest_power', 3000)

        # Energy
        self.energy_acc_hour = self.status.get('energy_acc_hour', 0)
        self.energy_hour_list.update(self.status.get('energy_hour_list', []))
        self.energy_month_list = PowerList()
        self.energy_month_list.update(self.status.get('energy_month_list', []))

        # Date and time
        self.current_hour = self.status.get('current_hour', 0)
        self.current_month = self.status.get('current_month', 0)

        # Cost
        self.cost_month_list.update(self.status.get('cost_month_list', []))
        self.total_cost = self.status.get('total_cost', 0)
        self.cost_hour_list.update(self.status.get('cost_hour_list', []))

    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        # Default values if loading fails
        self.voltage = 230
        self.sleep_time = 15
        self.power_current_hour_mean = 0
        self.third_highest_power = 3000
        self.energy_acc_hour = 0
        self.energy_month_list = PowerList()
        self.current_hour = 0
        self.current_month = 0
        self.cost_month_list = PowerList()
        self.total_cost = 0
        self.cost_hour_list = PowerList()


  def calculate_cost(self, elapsed_time, current_energy):

    # Turn energy from Wh to kWs
    current_energy = current_energy / 3600000

    # Number of total seconds this month
    now = datetime.datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = now.replace(month=now.month+1, day=1, hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(seconds=1)
    total_seconds_this_month = (end_of_month - start_of_month).total_seconds()
    # Accumulated seconds this month
    acc_seconds_this_month = (now - start_of_month).total_seconds()

    # Calculate consumtion costs
    variable_costs = energy_price['add_cost_per_kWh'] * current_energy
    fixed_costs = energy_price['fixed_cost_per_month'] * elapsed_time / total_seconds_this_month
    total_variable_costs = (variable_costs + fixed_costs) * (1 + energy_price['moms'])

    # Calculate power costs
    fast_avgift = power_price['fast_avgift'] * elapsed_time / total_seconds_this_month
    overforingsavgift = power_price['överföringsavgift'] * current_energy
    energiskatt = power_price['energiskatt'] * current_energy
    skatteavdrag = power_price['skatteavdrag'] * current_energy

    # Get the threerd highest power
    third_highest_powers = self.power_month_list.values[:3]
    # Add current mean power to the list
    third_highest_powers.append(self.power_current_hour_mean)
    # Sort the list and get the third highest power
    third_highest_powers.sort(reverse=True)
    third_highest_powers = third_highest_powers[:3]
    mean_power = np.mean(third_highest_powers)
    mean_power_cost = power_price['effektavgift'] * mean_power /1000 * elapsed_time / total_seconds_this_month
    # Calculate the total power cost 
    total_power_cost = fast_avgift + overforingsavgift + energiskatt + skatteavdrag + mean_power_cost
    # Calculate the total cost
    total_cost = total_variable_costs + total_power_cost
    # Scale cost to one hour of use
    total_cost = total_cost * (3600 / elapsed_time)
    return total_cost


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
      self.energy_month_list.add([str(one_hour_ago), self.energy_acc_hour])
      self.energy_hour_list.reset()

      # Update cost
      self.cost_month_list.add([str(one_hour_ago), self.total_cost])
      self.cost_hour_list.reset()

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
      self.energy_month_list.reset()
      self.cost_month_list.reset()



    # Energy
    self.energy_acc_hour += energy
    self.energy_hour_list.add([str(now), energy])

    # Power
    self.power_current_hour_list.add([str(now), (power['1']+ power['2']+ power['3'])])
    self.power_current_hour_mean = self.power_current_hour_list.mean
    self.third_highest_power = self.power_month_list.third_highest

    # Cost
    self.cost_hour_list.add([str(now), self.total_cost])


    # Update thingspeak
    if not test:
      self.ch.update({1: power['1'], 2: power['2'], 3: power['3'], 4: self.power_current_hour_mean , 5: self.third_highest_power})


    # Print status
    print(f"Power: {power['1']+ power['2']+ power['3']:>7.1f} W, Mean power: {self.power_current_hour_mean:>7.1f} W, Third highest power: {self.third_highest_power:>7.1f} W, Current cost/h{self.total_cost:7.1f}", end=" ")
    # Save status to file
    self.save_status_dict_to_file()
      
  def save_status_dict_to_file(self, test=False):
      status = {
          'voltage': self.voltage,
          'sleep_time': self.sleep_time,
          'power_current_list': self.power_current_hour_list.get(),
          'power_current_mean': self.power_current_hour_mean,
          'power_month_list': self.power_month_list.get(),
          'third_highest_power': self.third_highest_power,
          'energy_acc_hour': self.energy_acc_hour,
          'energy_hour_list': self.energy_hour_list.get(),  # Corrected reference
          'energy_month_list': self.energy_month_list.get(),
          'current_hour': self.current_hour,
          'current_month': self.current_month,
          'cost_month_list': self.cost_month_list.get(),
          'cost_hour_list': self.cost_hour_list.get(),
          'total_cost': self.total_cost,
          'start_time': self.start_time,  # Included start_time if needed
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

  def  get_power(self, current):
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
    self.total_cost = self.calculate_cost(elapsed_time, current_energy)
    print(f"E: {current_energy:>5.1f} Wh", end=" ")

    return current_energy

if __name__ == "__main__":
  energy = Energy()

  energy.current_hour
  for i in range(1, 10):
    print(f"Test {i}")
    time.sleep(10)

    energy.update(test=True)    
    print(f"Current cost: {energy.total_cost:>5.1f} SEK", end=" ")