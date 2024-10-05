import requests
from bs4 import BeautifulSoup

# url for aurora detector
AUROR_URL = 'http://192.168.1.200'

def get_aurora():
    try:
        response = requests.get(AUROR_URL, timeout=18)
        soup = BeautifulSoup(response.text, 'html.parser')
        data = soup.find_all('p')[2].text
        aurora_points = data.split(':')[1]
        aurora_points = float(aurora_points)
        print(data)
        return aurora_points

    except Exception as e:
        print(e)
        
points = get_aurora()        