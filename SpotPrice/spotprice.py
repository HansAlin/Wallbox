from CONFIG.config import region, currency, days_of_histroical_data
import requests
import datetime
import pickle
import json
import pandas as pd
import time
import os


def fetch_elprisetjustnu_data(now, region, verbose=False):

	year = now.year
	month = now.month
	day = now.day

	# Make month two digits
	month = str(month).zfill(2)

	# Make day two digits
	day = str(day).zfill(2)

	# Construct the URL
	# Data from https://www.elprisetjustnu.se/
	get_url = f"https://www.elprisetjustnu.se/api/v1/prices/{year}/{month}-{day}_{region}.json"
	if verbose:
		print(f"URL: {get_url}")

	try:
		# Send a GET request to the URL
		response = requests.get(get_url)

		# Raise an error if the status code isn't 200
		response.raise_for_status()

		# Parse the JSON response
		json_data = response.json()

		return json_data
	except requests.exceptions.RequestException as e:
		print(f"An error occurred: {e}")
		return None

def turn_json_to_df(json_data):
	# Turn the JSON data into a pandas DataFrame
	df = pd.DataFrame(json_data)

	new_df = df[['time_start', currency]]
	# Rename the columns
	new_df.columns = ['TimeStamp', 'value']
	if currency == "SEK_per_kWh":
		new_df.loc[:, 'value']  = new_df['value'] * 100
	elif currency == "EUR_per_kWh":
		new_df.loc[:, 'value'] = new_df['value'] * 100

	# Turn TimeStamp to datetime object
	new_df.loc[:, 'TimeStamp'] = pd.to_datetime(new_df['TimeStamp'], errors='coerce')
	new_df.loc[:, 'TimeStamp'] = new_df['TimeStamp'].apply(lambda x: x.replace(tzinfo=None))

	return new_df    
    

def getValues(now, verbose=False, test=False):
    
	if test:
		# Download saved data for testing
		df = get_simulated_new_data(now)
		return df
	else:
		# Download new data
		json_data = fetch_elprisetjustnu_data(now, region, verbose=verbose)

	if json_data is None:
		return None 
	else:
		# Turn the JSON data into a pandas DataFrame
		df = turn_json_to_df(json_data)
		if verbose:		
			print(f"Headers: {df.columns}")

	return df


def getSpotPrice(now, prev_data, verbose=False, test=False):
	"""
		Thsi function uses the API from elprisetjustnu.se to get the spot price for the current day.
		https://www.elprisetjustnu.se/api/v1/prices/[ÅR]/[MÅNAD]-[DAG]_[PRISKLASS].json

		Args:	
			now: datetime.datetime The current time
			prev_data: pd.DataFrame The previous data
			verbose: bool	print information
			test: bool, uses test data

		Returns:
			pd.DataFrame: The new data
	"""
	print(f"Downloaded data from Nordpool at: {now}", end=" ")

	days = days_of_histroical_data + 1
	
	try:
		if prev_data.empty or prev_data['TimeStamp'].iloc[-1] < now - datetime.timedelta(days=days):
			# Get one week of data
			days = days
			data = getValues(now - datetime.timedelta(days=days + 1), test=test)
			time.sleep(1)
			for i in range(0, days + 1):
				new_data = getValues(now - datetime.timedelta(days=(days-i)), test=test)
				# Concat
				data = concat_data(prev_data=data, new_data=new_data)
				time.sleep(1)
			# Sort data by time
			if now.hour >= 14:
				# Add one day
				new_data = getValues(now + datetime.timedelta(days=1), test=test)
				data = concat_data(prev_data=data, new_data=new_data)
			prev_data = data.sort_values(by='TimeStamp')	

		else:
			completed = False
			counter = 0
			while not completed or counter < 10:

				# Get the last timestamp from the previous data	
				last_prev = prev_data['TimeStamp'].iloc[-1]

				# Get the diff in days between now and the last timestamp
				now_day = datetime.datetime(year=now.year, month=now.month, day=now.day)
				last_prev_day = datetime.datetime(year=last_prev.year, month=last_prev.month, day=last_prev.day)

				diff = (now_day - last_prev_day).days

				if diff < 0:
					# Last time stamp from previous data is ahead of now
					# No more data to fetch
					completed = True
					break
				elif diff == 0:
					if now.hour < 14:
						# Before new data have arrived approx 14:00
						completed = True
						break
					else:
						# Get the spot price
						new_data = getValues(now + datetime.timedelta(days=1), verbose=verbose, test=test)
						prev_data = concat_data(prev_data=prev_data, new_data=new_data)
						completed = True
						break
				elif diff > 0:
					# Get the spot price
					then = now_day - datetime.timedelta(days=diff - 1)
					new_data = getValues(then, verbose=verbose, test=test)
					prev_data = concat_data(prev_data=prev_data, new_data=new_data)

				counter += 1
				time.sleep(1)	


		# Only save the last days of data
		new_data = prev_data[prev_data['TimeStamp'] >= prev_data['TimeStamp'].iloc[-1] - datetime.timedelta(days=days - 1)]	

		# Sort data by time
		new_data = new_data.sort_values(by='TimeStamp')	

		save_data(new_data)

		return new_data
		
	except Exception as e:
		print(f"Could not get data: {e}", end=" ")	
		return prev_data

# def get_price_from_date(now, utc_offset):
# 	prices_bas = elbas.Prices()
			
# 	end_date = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=14)
# 	prices = prices_bas.hourly(end_date=end_date, areas=[region])
# 	last = prices['areas'][region]['Last']
# 	pprint(last)
# 	timestamp = []
# 	price = []
# 	for element in last:
# 		timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
# 		price.append(element['value'])
# 	df = pd.DataFrame({'TimeStamp':timestamp, 'value':price}) 
# 	df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

# 	return df

# def get_price_spot(utc_offset):
# 	prices_spot = elspot.Prices()

# 	prices = prices_spot.hourly(areas=[region])
# 	pprint(prices)
# 	timestamp = []
# 	price = []
# 	values = prices['areas'][region]['values']
# 	for element in values:
# 			timestamp.append(element['start'] + datetime.timedelta(hours=utc_offset))
# 			price.append(element['value'])
# 	df = pd.DataFrame({'TimeStamp':timestamp, 'value':price})
# 	df['TimeStamp'] = pd.to_datetime(df['TimeStamp']).dt.tz_localize(None)

# 	return df
		

def save_data(df):
	
	# Load the previous data
	try:
		with open('data/log_nordpool.pkl', 'rb') as f:
			prev_data_pkl = pickle.load(f)
		last_prev_pkl = prev_data_pkl['TimeStamp'].iloc[-1]	
		# Concatenate the previous data with the new data
		df_new = df[df['TimeStamp'] > last_prev_pkl]
		df_pkl = pd.concat([prev_data_pkl, df_new], axis=0, ignore_index=True)
		df_pkl = df_pkl.reset_index(drop=True)

		# Only keep 365 days of data
		df_pkl = df_pkl[df_pkl['TimeStamp'] > df_pkl['TimeStamp'].iloc[0] - datetime.timedelta(days=365)]

		# Save the data
		with open('data/log_nordpool.pkl', 'wb') as f:
			pickle.dump(df_pkl,f)
	except:

		with open('data/log_nordpool.pkl', 'wb') as f:
			pickle.dump(df,f)

	# csv
	# Load the previous data
	try:
		with open('data/log_nordpool.csv', 'r') as f:
			prev_data_csv = pd.read_csv(f)
		prev_data_csv['TimeStamp'] = pd.to_datetime(prev_data_csv['TimeStamp'])

		last_prev_csv = prev_data_csv['TimeStamp'].iloc[-1]
		# Concatenate the previous data with the new data
		df_new = df[df['TimeStamp'] > last_prev_csv]
		df_csv = pd.concat([prev_data_csv, df_new], axis=0, ignore_index=True)
		df_csv = df_csv.reset_index(drop=True)

		# Only keep 365 days of data
		df_csv = df_csv[df_csv['TimeStamp'] > df_csv['TimeStamp'].iloc[0] - datetime.timedelta(days=365)]

		# If 'Unnamed: 0' is in the columns, remove it
		if 'Unnamed: 0' in df_csv.columns:
			df_csv = df_csv.drop(columns='Unnamed: 0')

		# Save the data
		df_csv.to_csv('data/log_nordpool.csv')

	except:

		df.to_csv('data/log_nordpool.csv')



def load_data():
	try:
		with open('data/log_nordpool.pkl', 'rb') as f:
			df = pickle.load(f)
	except:
		df = pd.DataFrame()
	return df	

def get_nordpool_data(now, test=False):
	"""
	This function loads data from the file log_nordpool.pkl and 
	check weather the data is up to date. If not, it gets the new data.

	Returns:
		pd.DataFrame: The data
	"""

	log_nord_pool_data = load_data()
	if log_nord_pool_data.empty:
		log_nord_pool_data = getSpotPrice(now=now, prev_data=log_nord_pool_data, test=test)
		save_data(log_nord_pool_data)

	# If data is missing, download new data
	last_time_stamp = log_nord_pool_data['TimeStamp'].iloc[-1]
	if last_time_stamp < now:
		log_nord_pool_data = getSpotPrice(now=now, prev_data=log_nord_pool_data, test=test)
		save_data(log_nord_pool_data)

	return log_nord_pool_data

def get_current_price(now):
	"""
	This function gets the current price from the data.

	Returns:
		float: The current price
	"""





	# Nordpool dataenergy
	if isinstance(now, str) or isinstance(now, datetime.datetime):
		# Make sure that now is a pandas datetime object
		if isinstance(now, str):
			now = pd.to_datetime(now)
		log_nord_pool_data = get_nordpool_data(now)
		# Get the current price  
		mask = (log_nord_pool_data['TimeStamp'] > (now - datetime.timedelta(hours=1))) & (log_nord_pool_data['TimeStamp'] < now)
		value = log_nord_pool_data[mask]

	if isinstance(now, list):
			# Convert all entries in now to datetime
			now_list = [pd.to_datetime(t) for t in now]
			now = now_list[0]

			# Get data from Nord Pool
			log_nord_pool_data = get_nordpool_data(now)

			# Set TimeStamp as index for reindexing
			log_nord_pool_data = log_nord_pool_data.set_index('TimeStamp')

			# Reindex to ensure all times in now_list are included
			value = log_nord_pool_data.reindex(now_list).fillna(0).reset_index()



	return value

def concat_data(prev_data, new_data):	
	if new_data.empty:
		return prev_data
	df = pd.concat([prev_data, new_data], axis=0, ignore_index=True)
	df = df.reset_index(drop=True)
	return df

def create_simulated_data(now):

	# Create test Data
	with open('data/test_data.pkl', 'rb') as f:
		df = pickle.load(f)
	# To datetime without utz
	# Convert 'TimeStamp' to datetime
	df['TimeStamp'] = pd.to_datetime(df['TimeStamp'], errors='coerce')

	# Check if the conversion was successful
	if df['TimeStamp'].isnull().any():
			raise ValueError("Some 'TimeStamp' values could not be converted to datetime.")

	# Remove timezone information
	df['TimeStamp'] = df['TimeStamp'].apply(lambda x: x.replace(tzinfo=None))

	diff = (now - df['TimeStamp'].iloc[-1]).days
	# Shift data
	if now.hour >= 14:
		add = 2
	else:
		add = 1 
	df['TimeStamp'] = df['TimeStamp'] + datetime.timedelta(days=diff + add)	

	# Create another week of data from First entry and backwards
	copy_df = df.copy()
	last = copy_df['TimeStamp'].iloc[0]
	first = copy_df['TimeStamp'].iloc[-1]
	diff = (first - last).days
	copy_df['TimeStamp'] = copy_df['TimeStamp'] - datetime.timedelta(days=diff + 1)
	df = pd.concat([copy_df, df], axis=0, ignore_index=True)

	sheck_for_gaps_in_data(df)

	with open('data/simulated_test_data.pkl', 'wb') as f:
		pickle.dump(df,f)

def get_simulated_prev_data(last_date):
	with open('data/simulated_test_data.pkl', 'rb') as f:
		df = pickle.load(f)

	# Convert 'TimeStamp' to datetime
	df['TimeStamp'] = pd.to_datetime(df['TimeStamp'], errors='coerce')

	# Check if the conversion was successful
	if df['TimeStamp'].isnull().any():
			raise ValueError("Some 'TimeStamp' values could not be converted to datetime.")

	# Remove timezone information
	df['TimeStamp'] = df['TimeStamp'].apply(lambda x: x.replace(tzinfo=None))

	last_year = last_date.year
	last_month = last_date.month
	last_day = last_date.day
	# Make the 
	last_day = datetime.datetime(year=last_year, month=last_month, day=last_day)

	df = df[df['TimeStamp'] < last_day]
	return df

def get_simulated_new_data(now):
	with open('data/simulated_test_data.pkl', 'rb') as f:
		df = pickle.load(f)
	# To datetime
	df['TimeStamp'] = pd.to_datetime(df['TimeStamp'])
	diff = (now - df['TimeStamp'].iloc[-1]).days + 1 
	#shift all the data
	df['TimeStamp'] = df['TimeStamp'] + datetime.timedelta(days=diff)
	df = df[df['TimeStamp'].dt.day == now.day]
	return df

def sheck_for_gaps_in_data(df):
	nr_rows = df.shape[0]
	for i in range(1, nr_rows):
		diff = df['TimeStamp'].iloc[i] - df['TimeStamp'].iloc[i-1]
		if diff > datetime.timedelta(days=1):
			#print(f"Gap between larger than 1 day: {diff} between {df['TimeStamp'].iloc[i-1]} and {df['TimeStamp'].iloc[i]}")
			print("There are gaps in the data.")

	print("There are no gaps in the data.")



if __name__ == "__main__":
	# Load NordPool data
	now = datetime.datetime.now()
	value = get_current_price(datetime.datetime.now())
	print(value)
	# nordpool_data = get_nordpool_data(now, test=True)
	# print(nordpool_data)