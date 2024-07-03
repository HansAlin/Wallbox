from nordpool import elspot, elbas
import datetime
from pprint import pprint
import pandas as pd
import pickle
from CONFIG.config import region

def getDataNordPool(utc_offset, now, prev_data):
	"""
	alternative url
	https://www.elprisetjustnu.se/api/v1/prices/[ÅR]/[MÅNAD]-[DAG]_[PRISKLASS].json
	"""
	print(f"Downloaded data from Nordpool at: {now}", end=" ")
	"""
	"""
	# TODO remove redundant code and eliminate repeated code!

	

	try:
		if prev_data.empty:
			new_data = get_price_from_date(now=now, utc_offset=utc_offset)
			save_data(new_data)
			return new_data
		
		else:
			# Last time stamp from previous data
			last_time_stamp_prev = prev_data['TimeStamp'].iloc[-1]

			# Before new data have arrived approx 14:00
			# or if last time stamp from norpool is more than now
			diff = (last_time_stamp_prev + datetime.timedelta(hours=1) - now)
			if now.hour < 14 or ( diff < datetime.timedelta(hours=0)):
				new_data = get_price_from_date(now=now, utc_offset=utc_offset)
			else:
				new_data = get_price_spot(utc_offset)
				# Sometimes the returned values from Nordpool have inf values
				if new_data['value'].iloc[0] > 10000:
					new_data = get_price_from_date(now=now, utc_offset=utc_offset)

			# Try to concatenate new data with old data		
			first_time_stamp_new = new_data['TimeStamp'].iloc[0]
			if last_time_stamp_prev.day + 1 == first_time_stamp_new.day:
				new_data = concat_data(prev_data=prev_data, new_data=new_data)

			save_data(new_data)

			return new_data
		
	except:
		print("Could not get data from Nordpool:", end=" ")	
		return prev_data

def get_price_from_date(now, utc_offset):
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

	return df

def get_price_spot(utc_offset):
	prices_spot = elspot.Prices()

	prices = prices_spot.hourly(areas=[region])
	pprint(prices)
	timestamp = []
	price = []
	values = prices['areas'][region]['values']
	for element in values:
			timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
			price.append(element['value'])
	df = pd.DataFrame({'TimeStamp':timestamp, 'value':price})
	df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

	return df
		

def save_data(df):
	with open('data/log_nordpool.pkl', 'wb') as f:
		pickle.dump(df,f)
	df.to_csv('data/log_nordpool.csv')

def concat_data(prev_data, new_data):	
	df = pd.concat([prev_data, new_data], axis=0, ignore_index=True)
	df = df.reset_index(drop=True)
	df = df.iloc[-96:,]
	return df