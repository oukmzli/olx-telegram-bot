# olx_api.py

import requests
import datetime
from dateutil.parser import parse as parse_date
import logging

logger = logging.getLogger(__name__)

def fetch_listings(filters):
    url = "https://www.olx.pl/api/v1/offers/"
    params = {
        "offset": 0,
        "limit": 50,
        "category_id": 15,
        "region_id": 4,
        "city_id": 8959,
        "sort_by": "created_at:desc",
        "filter_refiners": "spell_checker"
    }

    if filters.get('min_price'):
        params['filter_float_price:from'] = filters['min_price']
    else:
        params.pop('filter_float_price:from', None)
    if filters.get('max_price'):
        params['filter_float_price:to'] = filters['max_price']
    else:
        params.pop('filter_float_price:to', None)

    if filters.get('district_ids'):
        params['district_id'] = filters['district_ids']
    else:
        params.pop('district_id', None)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error fetching listings: {e}")
        return []
    except Exception as e:
        logger.exception("Unexpected error occurred while fetching listings.")
        return []

    data = response.json()
    listings = data.get('data', [])

    parsed_listings = []
    for item in listings:
        listing = {
            'id': str(item.get('id')),
            'title': item.get('title'),
            'url': item.get('url'),
            'price': None,
            'rent_additional': None,
            'location': None,
            'region_id': None,
            'region_name': None,
            'region_normalized_name': None,
            'district_id': None,
            'district_name': None,
            'area': None,
            'rooms': None,
            'is_business': item.get('business', False),
            'description': item.get('description', '')
        }

        for param in item.get('params', []):
            if param.get('key') == 'price':
                listing['price'] = param.get('value', {}).get('label', 'N/A')
            if param.get('key') == 'rent':
                listing['rent_additional'] = param.get('value', {}).get('label', 'N/A')
            if param.get('key') == 'm':
                listing['area'] = param.get('value', {}).get('label', 'N/A')
            if param.get('key') == 'rooms':
                listing['rooms'] = param.get('value', {}).get('label', 'N/A')

        region_data = item.get('location', {}).get('region', {})
        if region_data:
            listing['region_id'] = region_data.get('id', 'N/A')
            listing['region_name'] = region_data.get('name', 'N/A')
            listing['region_normalized_name'] = region_data.get('normalized_name', 'N/A')

        district_data = item.get('location', {}).get('district', {})
        if district_data:
            listing['district_id'] = str(district_data.get('id', 'N/A'))
            listing['district_name'] = district_data.get('name', 'N/A')

        pushup_time_str = item.get('pushup_time')
        if pushup_time_str:
            try:
                listing_time = parse_date(pushup_time_str)
            except Exception as e:
                logger.error(f"Error parsing pushup_time: {e}")
                continue
        else:
            continue

        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - listing_time
        if age > datetime.timedelta(days=2):
            continue

        parsed_listings.append(listing)

    logger.debug(f"Fetched {len(parsed_listings)} valid listings from OLX")
    return parsed_listings

def fetch_districts():
    district_name_to_id = {
        'debniki': '261',
        'biezanow-prokocim': '281',
        'bienczyce': '285',
        'bronowice': '253',
        'czyzyny': '283',
        'grzegorzki': '279',
        'krowodrza': '255',
        'lagiewniki-borek falecki': '259',
        'mistrzejowice': '289',
        'nowa huta': '287',
        'podgorze': '263',
        'podgorze duchackie': '277',
        'pradnik bialy': '275',
        'pradnik czerwony': '267',
        'stare miasto': '273',
        'swoszowice': '269',
        'wzgorza krzeslawickie': '291',
        'zwierzyniec': '257'
    }

    return district_name_to_id
