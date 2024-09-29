# olx_api.py

import requests
import datetime
from dateutil.parser import parse as parse_date
import logging

logger = logging.getLogger(__name__)

def fetch_listings(filters):
    """
    fetch listings from OLX based on the provided filters
    :param filters: dictionary with keys 'min_price', 'max_price', 'district_ids'
    :return: list of parsed listings
    """
    url = "https://www.olx.pl/api/v1/offers/"
    params = {
        "offset": 0,
        "limit": 50,
        "category_id": 15,  # Flats for rent
        "region_id": 4,     # Malopolskie region
        "city_id": 8959,    # Krakow
        "sort_by": "created_at:desc",
        "filter_refiners": "spell_checker"
    }

    # Add price filters
    if filters.get('min_price'):
        params['filter_float_price:from'] = filters['min_price']
    if filters.get('max_price'):
        params['filter_float_price:to'] = filters['max_price']

    # Add district filters
    if filters.get('district_ids'):
        params['district_id'] = filters['district_ids']

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error fetching listings: {e}")
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
            listing['district_id'] = district_data.get('id', 'N/A')
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

        # check if the listing is within the last 2 days
        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - listing_time
        if age > datetime.timedelta(days=2):
            continue

        parsed_listings.append(listing)

    logger.debug(f"Fetched {len(parsed_listings)} valid listings from OLX")
    return parsed_listings


def fetch_districts():
    district_name_to_id = {
        'krowodrza': '255',
        'nowa huta': '287',
        'podgórze': '263',
        'zwierzyniec': '257',
        'dębniki': '261',
        'stare miasto': '273'
    }

    return district_name_to_id
