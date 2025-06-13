import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from GARO.garo import get_current_consumtion
from SpotPrice.spotprice import get_current_price, get_nordpool_data
from CONFIG.config import low_price, energy_price, power_price
import time
import pandas as pd
import numpy as np
import datetime
import thingspeak
from CONFIG.config import channel_id, api_key
from CHARGE.charge import get_now
import json

import portalocker

class PowerList:
    def __init__(self, mode=None):
        self._data = []
        self._old_3rd_highest = None
        self._mode = mode  # 'hour' or 'month'


    # def append(self, datetime_str, power_value):
    #     self._data.append((datetime_str, power_value))

    def add(self, data):
        """Add new data point [timestamp_string, value] and filter by mode"""
        self._data.append(data)
        self._filter_old()

    def _filter_old(self):
        if not self._mode or not self._data:
            return

        now = datetime.datetime.now()
        filtered_data = []

        for entry in self._data:
            try:
                timestamp = datetime.datetime.fromisoformat(entry[0])
            except ValueError:
                timestamp = datetime.datetime.strptime(entry[0], '%Y-%m-%dT%H:%M:%S')

            if self._mode == 'hour':
                if timestamp.year == now.year and timestamp.month == now.month and timestamp.day == now.day and timestamp.hour == now.hour:
                    filtered_data.append(entry)

            elif self._mode == 'month':
                if timestamp.year == now.year and timestamp.month == now.month:
                    filtered_data.append(entry)

        self._data = filtered_data

    def update(self, data):
        self._data = data    

    def update_values(self, values, timestamps):
      """
      This function updates the values in the list
      """
      data = []
      for i, (value, timestamp) in enumerate(zip(values, timestamps)):
         data.append([str(timestamp), float(value)])
      self._data = data

    def get(self, index=None):
        if index is None:
            return self._data
        return self._data[index]  

    def update_by_index(self, index, data):
        if index < len(self._data):
            self._data[index][1] = data
        else:
            raise IndexError("Index out of range")

    def get_mean_3rd_highest(self):
        sorted_values = np.sort(self.values)
        if len(sorted_values) < 3:
            return np.mean(sorted_values)
        else:
            return np.mean(sorted_values[-3:])    

    @property  
    def len(self):
        return len(self._data)     

    @property
    def datetime(self):
        # Turne the datetime strings into datetime objects
        if not self._data:
            return []
        # Convert datetime strings to datetime objects
        try:
            return [datetime.datetime.fromisoformat(entry[0]) for entry in self._data]
        except ValueError:
            # If the format is not ISO8601, try parsing it
            return [datetime.datetime.strptime(entry[0], '%Y-%m-%dT%H:%M:%S') for entry in self._data]


    @property
    def values(self):
        return [entry[1] for entry in self._data]

    @property
    def mean(self):
        return np.mean(self.values)
    
    @property
    def mean_3rd_highest(self):
        sorted_values = np.sort(self.values)
        if len(sorted_values) < 3:
            return np.mean(sorted_values)
        else:
            return np.mean(sorted_values[-3:])

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

    @property
    def sorted(self):
        """
        This function returns the sorted values in the list
        """
        return np.sort(self.values)

    def get_value_and_time(self, index):
        """
        This function returns the value and time at a specific index
        """
        if index < len(self._data):
            return self._data[index]
        else:
            raise IndexError("Index out of range")

    def get_third_highest_index(self):
      """
      This function returns the index of the third highest value in the list
      """
      # Where the third highest value is in the list
      index = np.where(np.array(self.values) == self.third_highest)[0][0]
      # If value are the default value or index is not in the list
      if self.third_highest == 3000 or index not in range(len(self._data)):
        index = -1
      return index   

    def get_index_by_order(self, order):
      # Sort from highest to lowest
      try:
        sorted_values = np.sort(self.values)[::-1]
        order_value = sorted_values[order]
        index = np.where(np.array(self.values) == order_value)[0][0]
      except IndexError:
        # If the order is out of range, return -1
        index = -1

      return index

    def reset(self):
        self._data = []   

    def set_old_3rd_highest(self, value):
        self._old_3rd_highest = value  
    

class Energy:

  def __init__(self, distribution_type='3rd_highest', test=False):
    """ 
    Available distribution types:
    - '3rd_highest': Distributes the power costs over the three highest power values in the month.
    - 'mean': Distributes the power costs evenly over the month.
    - 'weighted': Distributes the power costs based on the power values in the month.
    """
    
    self.ch = thingspeak.Channel(id=channel_id, api_key=api_key)
    self.power_current_hour_list = PowerList(mode='hour')
    self.power_month_list = PowerList(mode='month')
    self.energy_hour_list = PowerList(mode='hour')
    self.energy_acc_hour = 0
    self.energy_month_list = PowerList(mode='month')
    self.cost_month_list = PowerList(mode='month')
    self.cost_hour_list = PowerList(mode='hour')
    self.start_time = time.time()
    self.each_hour_time, _ = get_now()
    self.distribution_type = distribution_type
    self.numpy_encoder = NumpyEncoder()
    self.test = test
    
    # Load energy status from file to dictionary
    try:
        self.status = self.load_status_dict_from_file()

        self.voltage = self.status.get('voltage', 230)
        self.sleep_time = self.status.get('sleep_time', 15)

        # Power
        self.power_current_hour_list.update(self.status.get('power_current_list', []))
        self.power_current_hour_mean = self.status.get('power_current_mean', 0)
        self.power_month_list.update(self.status.get('power_month_list', []))

        # Energy
        self.energy_acc_hour = self.status.get('energy_acc_hour', 0)
        self.energy_hour_list.update(self.status.get('energy_hour_list', []))
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


  def seconds_this_month(self, now):
    """
    This function calculates the seconds in the current month
    """
    if isinstance(now, list):
      now = pd.to_datetime(now[-1])
    next_month = now.replace(month=now.month % 12 + 1, day=1, hour=0, minute=0, second=0)
    seconds_this_month = (next_month - now.replace(day=1, hour=0, minute=0, second=0)).total_seconds()
    return seconds_this_month
  
  def acc_seconds_this_month(self, now):
    """
    This function calculates the accumulated seconds in the current month
    """
    if isinstance(now, list):
      now = pd.to_datetime(now[-1])
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0)
    seconds_this_month = (now - first_day_of_month).total_seconds()
    return seconds_this_month

  def calculate_cost(self, energy_list, power_list, now, time_delta, distribution_type='3rd_highest'):

    # Energy 
    # All costs are calculated per hour
    if np.isscalar(energy_list):
      seconds_this_month = self.seconds_this_month(pd.to_datetime(now))
      energy_values = np.array(energy_list) * 3600 # Unit Wh -> Ws
      datetime_series = now
      power_values = np.array(power_list)
      spot_price = get_current_price(now)['value']* energy_values / (1000 * 3600) * 3600 / time_delta  
      # Spot price is in öre/kWh
    else:
      seconds_this_month = self.seconds_this_month(pd.to_datetime(now[-1]))
      energy_values = np.array(energy_list.values) / 3600
      datetime_series = energy_list.datetime
      power_values = np.array(power_list.values)
      spot_price = get_current_price(energy_list.datetime)['value'].values * energy_values / (1000 * 3600) * time_delta
    #spot_price = get_historical_price() #TODO yet to be implemented
    additional_spot_price = energy_price['add_cost_per_kWh'] * energy_values / (1000 * 3600) * 3600 / time_delta  # Convert from öre/kWh to öre/Ws
    fixed_energy_month_price = energy_price['fixed_cost_per_month'] * np.ones_like(energy_values) * 3600 / seconds_this_month
    moms = energy_price['moms'] * (additional_spot_price + fixed_energy_month_price + spot_price)  # Calculate the VAT on the total cost
    # Power
    fixed_power_month_price = power_price['fast_avgift'] * np.ones_like(power_values) * time_delta / seconds_this_month
    transfer_fee = power_price['överföringsavgift'] * energy_values / (1000 * 3600) * time_delta 
    taxes = (power_price['energiskatt'] + power_price['skatteavdrag'] ) * energy_values / (1000 * 3600) * time_delta
    # If energy_values are not a scaler
    if not np.isscalar(energy_values):
      effektavgift = self.distribute_power_costs(now, distribution_type=distribution_type) # Distribute the power costs
    else:
       effektavgift = np.ones_like(power_values) * self.current_power_cost(now, distribution_type=distribution_type, time_delta=time_delta) # Calculate the current power cost
    cost = additional_spot_price + fixed_energy_month_price + moms + fixed_power_month_price + transfer_fee + taxes + effektavgift

    return cost, datetime_series

  def current_power_cost(self, now, distribution_type, time_delta):

    if self.power_month_list.len < 3:
      # If there are less than 3 entries, return zero cost
      return 0

    if self.power_current_hour_mean > self.third_highest_power:
      # Calculate the cost based on the current power mean
      if distribution_type == '3rd_highest':
        # Get the current three highest power values
        power_3rd_highest_list = self.power_month_list.sorted[-3:]
        # Change last entry
        power_3rd_highest_list[-1] = self.power_current_hour_mean 

        power_fee = power_price['effektavgift'] / 1000 * np.mean(power_3rd_highest_list)  # Convert from öre/kW to öre/Ws
      elif distribution_type == 'mean':
        # Calculate the mean of the power values
        power_fee = power_price['effektavgift'] / 1000 * self.power_month_list.mean_3rd_highest  # Convert from öre/kW to öre/Ws
        # Hours this month
        hours = self.seconds_this_month(now) / 3600
        power_fee = power_fee / hours  # Convert to cost per hour
      elif distribution_type == 'weighted':
        # Calculate the weighted average of the power values
        total_power = sum(self.power_month_list.values)
        power_fee = power_price['effektavgift'] / 1000 * (self.power_current_hour_mean / total_power) 
        # And weighted by the ratio of the acc_seconds_this_month to seconds_this_month
        ratio = self.acc_seconds_this_month(now) / self.seconds_this_month(now)
        power_fee *= ratio  # Scale by the ratio of accumulated seconds to total seconds in the month
      else:
        raise ValueError("Invalid distribution type. Use '3rd_highest', 'mean', or 'weighted'.")
      
    else:
      # If the current power mean is not greater than the third highest power, set the cost to zero
      power_fee = 0

    return power_fee  


  def distribute_power_costs(self, now, distribution_type='3rd_highest'):
    power_fee = self.power_month_list.mean_3rd_highest * power_price['effektavgift'] / 1000
    power_fee_list = np.zeros_like(self.power_month_list.values)

    seconds_this_month = self.seconds_this_month(now)
    acc_seconds_this_month = self.acc_seconds_this_month(now)

    if distribution_type == '3rd_highest':
       indeces_3rd_highest = [self.power_month_list.get_index_by_order(i) for i in range(0, 3)]
       for index in indeces_3rd_highest:
          power_fee_list[index] = power_fee / len(indeces_3rd_highest)
    elif distribution_type == 'mean':
      # Distribute the mean power cost evenly across all entries
      # and scale it by the ratio of the acc_seconds_this_month to seconds_this_month
      ratio = acc_seconds_this_month / seconds_this_month
      power_fee_list += power_fee * ratio / len(self.power_month_list.values)
    elif distribution_type == 'weighted':
       # Distribute the power cost based on the power values
       # and scale it by the ratio of the acc_seconds_this_month to seconds_this_month
       ratio = acc_seconds_this_month / seconds_this_month
       total_power = sum(self.power_month_list.values)
       for index, value in enumerate(self.power_month_list.values):
          scaled_value = value * ratio / total_power
          power_fee_list[index] = scaled_value * power_fee        
    else:
      raise ValueError("Invalid distribution type. Use '3rd_highest', 'mean', or 'weighted'.")

    return power_fee_list   


  def mean_3rd_highest_power(self):
     
    power_fee_list = np.zeros_like(self.power_month_list.values) 
    _3rd_highest_power = self.power_month_list.sorted[-3:]
    _3rd_highest_power_index = []
    for i in range(len(_3rd_highest_power)):
      _3rd_highest_power_index.append(self.power_month_list.get_index_by_order(i))
    sum_3rd_highest_power = sum(_3rd_highest_power)
    mean_3rd_highest_power = sum_3rd_highest_power / len(_3rd_highest_power)
    for index in _3rd_highest_power_index:
      time, value = self.power_month_list.get_value_and_time(index)
      scaled_value = value * mean_3rd_highest_power / sum_3rd_highest_power
      power_fee_list[index] = scaled_value * power_price['effektavgift'] / 1000

    return power_fee_list

  def update(self):

    elapsed_time = time.time() - self.start_time
    self.start_time = time.time()
    if self.test: 
       print("Test mode") 
    now, utc_off = get_now()
    current = get_current_consumtion(self.test)
    if current == None:
      return None
    power = self.get_power(current)
    energy = self.get_energy_consumtion(power, elapsed_time)

    # New hour
    if self.current_hour != now.hour:
      # Seconds since last hour
      seconds_since_last_hour = (now - self.each_hour_time).total_seconds()
      self.each_hour_time = now

      # Update current hour
      self.current_hour = now.hour
      one_hour = datetime.timedelta(hours=1)

      # Update power with timestamp
      one_hour_ago = now - one_hour
      one_hour_ago = one_hour_ago.replace(minute=0, second=0, microsecond=0)
      old_3rd_highest_power_mean = self.power_month_list.mean_3rd_highest
      self.power_month_list.add([str(one_hour_ago), self.power_current_hour_mean])


      # Update energy
      self.energy_month_list.add([str(one_hour_ago), self.energy_acc_hour])

      
 
      # Update cost
      nows = self.energy_month_list.datetime
      cost_month_list, timestamp = self.calculate_cost(self.energy_month_list, self.power_month_list, nows, seconds_since_last_hour, distribution_type=self.distribution_type)
      self.cost_month_list.update_values(cost_month_list, timestamp)
      self.cost_hour_list.reset()

      # Update thingspeak
      if not self.test:
        self.ch.update({6: self.energy_acc_hour, 7: get_current_price(now), 8:self.power_current_hour_mean})

      self.energy_acc_hour = 0
      self.power_current_hour_list.reset()
      self.power_current_hour_mean = 0
      self.energy_hour_list.reset()

    # New month
    if self.current_month != now.month:

      self.power_month_list.set_old_3rd_highest(self.power_month_list.third_highest)
      self.power_month_list.reset()
      self.current_month = now.month
      self.energy_month_list.reset()
      self.cost_month_list.reset()



    # Energy
    self.energy_acc_hour += energy
    self.energy_hour_list.add([str(now), self.energy_acc_hour])

    # Power
    self.power_current_hour_list.add([str(now), (power['1']+ power['2']+ power['3'])])
    self.power_current_hour_mean = self.power_current_hour_list.mean
    self.third_highest_power = self.power_month_list.third_highest

    # Cost
    cost, timestamp = self.calculate_cost(energy, power['1']+ power['2']+ power['3'], now, time_delta=3600, distribution_type=self.distribution_type)
    self.cost_hour_list.add([str(now), cost])

    # Update thingspeak
    if not self.test:
      self.ch.update({1: power['1'], 2: power['2'], 3: power['3'], 4: self.power_current_hour_mean , 5: self.third_highest_power})

    # Print status
    print(f"Power: {float(power['1']+ power['2']+ power['3']):>7.1f} W, Mean power: {self.power_current_hour_mean.item():>7.1f} W, Third highest power: {self.third_highest_power:>7.1f} W, Current {cost.item():>7.3f} öre/h", end=" ")
    # Save status to file
    self.save_status_dict_to_file()
      
  def inspect_nested(self,obj, prefix=''):
      if isinstance(obj, dict):
          for k, v in obj.items():
              self.inspect_nested(v, prefix + f"{k}.")
      elif isinstance(obj, list):
          for i, item in enumerate(obj):
              self.inspect_nested(item, prefix + f"[{i}].")
      else:
          print(f"{prefix[:-1]}: {type(obj)}")


  def save_status_dict_to_file(self):
      status = {
          'voltage': float(self.voltage) if isinstance(self.voltage, np.ndarray) else self.voltage,
          'sleep_time': self.sleep_time,
          'power_current_list': self.power_current_hour_list.get(),
          'power_current_mean': float(self.power_current_hour_mean),
          'power_month_list': self.power_month_list.get(),
          'third_highest_power': float(self.power_month_list.third_highest),
          'energy_acc_hour': float(self.energy_acc_hour),
          'energy_hour_list': self.energy_hour_list.get(),
          'energy_month_list': self.energy_month_list.get(),
          'current_hour': self.current_hour,
          'current_month': self.current_month,
          'cost_month_list': self.cost_month_list.get(),
          'cost_hour_list': self.cost_hour_list.get(),
          'total_cost': float(self.total_cost),
          'start_time': self.start_time,
      }
      # print(f"Saving dict!", end='')
      # self.numpy_encoder.test_type(status=status)
      self.numpy_encoder.encode_json(status)

      path = 'data/energy_status_test.json' if self.test else 'data/energy_status.json'
      temp_path = path + ".tmp"

      with open(temp_path, 'w') as f:
          portalocker.lock(f, portalocker.LOCK_EX)
          json.dump(status, f, cls=NumpyEncoder)
          f.flush()
          os.fsync(f.fileno())
          portalocker.unlock(f)

      os.replace(temp_path, path)  # Atomic rename


  def get_power_mean(self):
    return self.power_current_hour_mean

  def load_status_dict_from_file(self):
      path = 'data/energy_status_test.json' if self.test else 'data/energy_status.json'
      with open(path, 'r') as f:
          portalocker.lock(f, portalocker.LOCK_SH)
          status = json.load(f)
          portalocker.unlock(f)
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
      
  def get_energy_consumtion(self, power, elapsed_time=None):


    print(f"Time: {elapsed_time:>5.0f} s", end=" ")
    
    current_energy = (power['1'] + power['2'] + power['3']) * elapsed_time / 3600

    print(f"E: {current_energy:>5.1f} Wh", end=" ")

    return current_energy

  def plot_cost(self):
    """
    This function plots the cost per hour
    """
    import matplotlib.pyplot as plt

    # Convert datetime strings to pandas datetime
    datetime_series = pd.to_datetime(self.cost_hour_list.datetime, format='ISO8601')

    # Plotting the cost per hour
    plt.figure(figsize=(10, 5))
    plt.plot(datetime_series, self.cost_hour_list.values, marker='o', linestyle='-', color='b')
    plt.title('Cost per Hour')
    plt.xlabel('Time')
    plt.ylabel('Cost (SEK)')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

class NumpyEncoder(json.JSONEncoder):

  def default(self, obj):
      if isinstance(obj, np.ndarray):
          # Return as a list
          return obj.tolist()
      elif isinstance(obj, (np.generic,)):
          # Covers np.integer, np.floating, np.bool_, etc.
          return obj.item()
      return super().default(obj)

      
  def encode_json(self, status):
      for key, value in status.items():
          if isinstance(status[key], list):
              temp_list = []
              for item in status[key]:
                  if isinstance(item, list):
                      item[0] = str(item[0])  # Ensure timestamp is string
                      val = item[1]

                      # Handle numpy arrays
                      if isinstance(val, np.ndarray):
                          if val.ndim == 0 or val.size == 1:
                              val = val.item()
                          else:
                              raise ValueError(f"Expected scalar or single-element array, got shape {val.shape}")
                      
                      # Handle pandas Series
                      elif isinstance(val, pd.Series):
                          if len(val) == 1:
                              val = float(val.iloc[0])
                          else:
                              raise ValueError(f"Expected single-element Series, got length {len(val)}")
                      
                      # Handle numpy generic types
                      elif isinstance(val, np.generic):
                          val = val.item()
                      
                      # Convert to float
                      item[1] = float(val)
                  temp_list.append(item)
              status[key] = temp_list

  def test_type(self, status):

     for key, value in status.items():
        print(f'Key: {key} type: {type(value)}')  
         
      


if __name__ == "__main__":
  
  
  energy = Energy(test=True)

  distribution_types = ['mean', '3rd_highest', 'weighted']*3
  time_delta = 3600
  now, utc_off = get_now()
  energy.save_status_dict_to_file()

  if_first_time = True  
  index = 0

  for distribution_type in distribution_types:
    
    for i in range(3):
     for j in range(5):
         if j == i:
            energy.current_hour = now.hour - 1
         energy.update()
         time.sleep(1)  
