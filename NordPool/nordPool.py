from nordpool import elspot, elbas
import datetime
from pprint import pprint
import pandas as pd
import pickle
from CONFIG.config import region

def getDataNordPool(utc_offset, now, prev_data):

	print(f"Downloaded data from Nordpool at: {now}", end=" ")
	"""
	"""
	# TODO remove redundant code and eliminate repeated code!
	try:
		if prev_data.empty:
			prices_bas = elbas.Prices()
			
			end_date = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
			prices = prices_bas.hourly(end_date=end_date, areas=[region])
			last = prices['areas'][region]['Last']
			pprint(last)
			timestamp = []
			price = []
			for element in last:
				timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
				price.append(element['value'])
			df = pd.DataFrame({'TimeStamp':timestamp, 'value':price}) 
			df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

			with open('data/log_nordpool.pkl', 'wb') as f:
				pickle.dump(df,f)
			
			return df


		else:
			prices_spot = elspot.Prices()

			prices = prices_spot.hourly(areas=[region])
			pprint(prices)
			timestamp = []
			price = []
			values = prices['areas'][region]['values']
			for element in values:
					timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
					price.append(element['value'])
			new_data = pd.DataFrame({'TimeStamp':timestamp, 'value':price})
		
			new_data['TimeStamp'] = pd.to_datetime(new_data['TimeStamp']).dt.tz_localize(None)

			first_time_stamp = new_data['TimeStamp'].iloc[0]
			value = new_data['value'].iloc[0]
	
			prev_data['TimeStamp'] = pd.to_datetime(prev_data['TimeStamp'])
			last_time_stamp = prev_data['TimeStamp'].iloc[-1]
			t = type(value)
			if value < 100000:		# Sometimes the returned values from Nordpool have inf values
				last_day = last_time_stamp.day
				one_day = datetime.timedelta(hours=24)
				first_day = first_time_stamp.day
				
				#if last_time_stamp.day + datetime.timedelta(hours=24) == first_time_stamp.day:
				if last_day + 1 == first_day:
					with open('data/log_nordpool.pkl', 'rb') as f:
						log_nordpool = pickle.load(f)
					concat_df = pd.concat([prev_data, new_data], axis=0, ignore_index=True)
					log_nordpool = pd.concat([log_nordpool, new_data], axis=0, ignore_index=True)

					concat_df = concat_df.reset_index(drop=True)
					log_nordpool = log_nordpool.reset_index(drop=True)
					concat_df = concat_df.iloc[-96:,]
	
					with open('data/log_nordpool.pkl', 'wb') as f:
						pickle.dump(log_nordpool,f)
					log_nordpool.to_csv('data/log_nordpool.csv')
					
					return concat_df
				else:
					# If not the new data is aligned with the old data
					# Try to compacted the code!
					prices_bas = elbas.Prices()
					
					end_date = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
					prices = prices_bas.hourly(end_date=end_date, areas=[region])
					last = prices['areas'][region]['Last']
					pprint(last)
					timestamp = []
					price = []
					for element in last:
						timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
						price.append(element['value'])
					df = pd.DataFrame({'TimeStamp':timestamp, 'value':price}) 
					df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

					with open('data/log_nordpool.pkl', 'wb') as f:
						pickle.dump(df,f)
					
					return df
					

			return prev_data
	except:
		print("Could not get data from Nordpool:")	
		return prev_data

