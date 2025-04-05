import unittest
import pickle
import pandas as pd
import CHARGE.charge as ch

class TestCharge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('data/saved_data.pkl', 'rb') as f:
            file_content = f.read()
            cls.data = pickle.loads(file_content)
        cls.now, _ = ch.get_now()
        cls.test = True

    def test_empty_data(self):
        data = self.data.copy()
        data['nordpool'] = pd.DataFrame()
        ch.if_download_nordpool_data(data, self.now, test=self.test)
        nordpool = data['nordpool']
        last_down_load = data['last_down_load']
        new_down_load = data['new_down_load']
        last_entry = data['nordpool'].iloc[-1]['TimeStamp']
        
        self.assertTrue(last_entry > self.now + pd.Timedelta(hours=8), 'Failed to download nordpool data')
        self.assertTrue(last_down_load.hour == 14, 'Failed to update last_down_load')
        self.assertTrue(new_down_load == True, 'Failed to update new_down_load')

    def test_last_download_more_than_24_hours_ago(self):
        data = self.data.copy()
        data['nordpool'] = data['nordpool'][data['nordpool']['TimeStamp'] < self.now - pd.Timedelta(hours=24)]
        ch.if_download_nordpool_data(data, self.now, test=self.test)
        last_down_load = data['last_down_load']
        new_down_load = data['new_down_load']
        last_entry = data['nordpool'].iloc[-1]['TimeStamp']
        
        self.assertTrue(last_entry > self.now + pd.Timedelta(hours=8), 'Failed to download nordpool data')
        self.assertTrue(last_down_load.hour == 14, 'Failed to update last_down_load')
        self.assertTrue(new_down_load == True, 'Failed to update new_down_load')

    def test_last_entry_less_than_9_hours_ahead(self):
        data = self.data.copy()
        data['nordpool'] = data['nordpool'][data['nordpool']['TimeStamp'] <= pd.Timestamp(self.now.date()) + pd.Timedelta(hours=23)]
        test_now = self.now.replace(hour=14)
        
        ch.if_download_nordpool_data(data, test_now, test=self.test)
        last_down_load = data['last_down_load']
        new_down_load = data['new_down_load']
        last_entry = data['nordpool'].iloc[-1]['TimeStamp']
        
        self.assertTrue(last_entry > self.now + pd.Timedelta(hours=8), 'Failed to download nordpool data')
        self.assertTrue(last_down_load.hour == 14, 'Failed to update last_down_load')
        self.assertTrue(new_down_load == True, 'Failed to update new_down_load')

    def test_first_entry_less_than_0_hours_ago(self):
        data = self.data.copy()
        data['nordpool'] = data['nordpool'][data['nordpool']['TimeStamp'] < self.now]
        ch.if_download_nordpool_data(data, self.now, test=self.test)
        last_down_load = data['last_down_load']
        new_down_load = data['new_down_load']
        last_entry = data['nordpool'].iloc[-1]['TimeStamp']
        
        self.assertTrue(last_entry > self.now + pd.Timedelta(hours=8), 'Failed to download nordpool data')
        self.assertTrue(last_down_load.hour == 14, 'Failed to update last_down_load')
        self.assertTrue(new_down_load == True, 'Failed to update new_down_load')

    def test_response(self):
        data = ch.get_button_state()
        self.assertIsNotNone(data, 'Failed to get button state')
        self.assertIsInstance(data, dict, 'Failed to get button state')
        self.assertIn('hours', data, 'Failed to get button state')
        self.assertIn('set_time', data, 'Failed to get button state')
        self.assertIn('fas_value', data, 'Failed to get button state')
        self.assertIn('kwh_per_week', data, 'Failed to get button state')
        self.assertIn('status', data, 'Failed to get button state')
        self.assertIn('charge_type', data, 'Failed to get button state')
        self.assertTrue(data['charge_type'] in ['auto', 'fast_smart', 'on', 'off'], 'Failed to get button state')

    def test_if_status_quo(self):
        data = self.data.copy()

        response = ch.get_button_state()

        response['charge_type'] = data['charge_type']
        response['hours'] = data['hours']
        response['set_time'] = data['set_time']
        response['fas_value'] = data['fas_value']
        response['kwh_per_week'] = data['kwh_per_week']
        data['connected'] = 'CONNECTED'
        connected = 'NOT_CONNECTED'

        self.assertTrue(ch.if_status_quo(data, response, connected), 'Failed to check if status quo')

        # Check if the status quo is not met
        response['charge_type'] = 'auto'
        data['charge_type'] = 'fast_smart'
        response['hours'] = data['hours']
        response['set_time'] = data['set_time']
        response['fas_value'] = data['fas_value']
        response['kwh_per_week'] = data['kwh_per_week']
        data['connected'] = 'CONNECTED'
        connected = 'NOT_CONNECTED'

        self.assertFalse(ch.if_status_quo(data, response, connected), 'Failed to check if status quo')
            

if __name__ == '__main__':
    #unittest.main()
    #unittest.main(defaultTest='TestCharge.test_first_entry_less_than_0_hours_ago')
    #unittest.main(defaultTest='TestCharge.test_response')
    unittest.main(defaultTest='TestCharge.test_if_status_quo')