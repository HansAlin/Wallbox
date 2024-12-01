import datetime
import pandas as pd
from itertools import product

class TestDebug:

    def __init__(self):
        self.debug = True
        self.count = 1201

        self.responses = {
            'available': ["ALWAYS_OFF", "ALWAYS_ON", "SCHEMA"],
            'connection': ["CONNECTED", "DISABLED", 'CHARGING_PAUSED', 'CHARGING_FINISHED', 'CHARGING'],
            'auto': [1, 0, 0, 0],
            'full': [0, 1, 0 ,0],
            'fast_smart': [0, 0, 1, 0],
            'on': [0, 0, 0, 1],
            'hours': [0, 5, 15],
            'set_time': [0, 12],# 24],
            'fas_value': [1],
            'kwh_per_week': [10,40],# 480],
            'nord_pool_data': ['OLD_DATA', 'DATA', 'EMPTY_DATA'],
            'schedule': ['NO_SCHEDULE', 'SCHEDULE'],
        }

        self.combinations = self.generate_combinations()
        self.schedule = None
        self.nord_pool_data = None

    def generate_combinations(self):
        # Extract the keys that should have only one '1' value
        single_value_keys = ['auto', 'full', 'fast_smart', 'on']
        other_keys = [k for k in self.responses.keys() if k not in single_value_keys]

        # Generate all combinations for single value keys

        valid_single_value_combinations = [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)]
        # Generate all combinations for other keys
        other_combinations = list(product(*[self.responses[k] for k in other_keys]))

        # Combine both sets of combinations
        valid_combinations = []
        for single_comb in valid_single_value_combinations:
            for other_comb in other_combinations:
                combination = dict(zip(single_value_keys, single_comb))
                combination.update(dict(zip(other_keys, other_comb)))
                valid_combinations.append(combination)
    
        print(f"Generated {len(valid_combinations)} combinations", end=" ")
        
        return valid_combinations


    def get_next_combination(self):
        if self.count >= len(self.combinations):
            self.count = 0
        combination = self.combinations[self.count]
        self.count += 1

        # Save the combination to a file
        with open("DEBUG/combination.txt", "w") as f:
            f.write(str(combination))

        response = 		response  = {
			    'auto': combination['auto'],
          'full': combination['full'],
          'fast_smart': combination['fast_smart'],
          'on': combination['on'],
          'hours': combination['hours'],
          'set_time': combination['set_time'],
          'fas_value': combination['fas_value'],
          'kwh_per_week': combination['kwh_per_week']
        }

        connected = combination['connection']
        available = combination['available']

        nord_pool_data = combination['nord_pool_data']
        schedule = combination['schedule']
        print(f"Combination: {self.count-1}/{len(self.combinations)}")
        return response, available, nord_pool_data, schedule, connected
    
    def update_state(self, df, now):

        if self.schedule == 'NO_SCHEDULE':
            df['schedule'] = pd.DataFrame()	
        if self.nord_pool_data == 'OLD_DATA':
            df['nordpool'] = df['nordpool'][df['nordpool']['TimeStamp'] < now - datetime.timedelta(hours=5)]	
        elif self.nord_pool_data == 'EMPTY_DATA':
            df['nordpool'] = pd.DataFrame()	
            df['new_down_load'] = False  
        return df          

# Example usage
if __name__ == "__main__":
    test_debug = TestDebug()
    for i in range(100):
        print(test_debug.get_next_combination())