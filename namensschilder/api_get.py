#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import json
import os
from pathlib import Path

# URL-endpoints
BASEURL = "https://pretix.eu/api/v1/organizers/fossgis/events/"
EVENT_ID = "2025"
# EVENT_ID = "demo-2020"
# https://docs.pretix.eu/en/latest/api/resources/orders.html#get--api-v1-organizers-(organizer)-events-(event)-orders-
ORDER_URL = BASEURL + EVENT_ID + "/orders/"
# https://docs.pretix.eu/en/latest/api/resources/invoices.html#get--api-v1-organizers-(organizer)-events-(event)-invoices-
INVOICE_URL = BASEURL + EVENT_ID + "/invoices/"
# ?????????????????
NREI_URL = BASEURL + EVENT_ID + "/orders?identifier=dekodi_nrei"
# https://docs.pretix.eu/en/latest/api/resources/items.html#get--api-v1-organizers-(organizer)-events-(event)-items-
ITEMS_URL = BASEURL + EVENT_ID + "/items/"

ITEM_CATEGORY_URL = BASEURL + EVENT_ID + "/categories/"

QUESTIONS = BASEURL + EVENT_ID + "/questions/"

if not 'PRETIX_API_TOKEN' in os.environ:
    raise Exception("PRETIX_API_TOKEN variable nicht definiert.")

# Auth*
headers = {
    "Authorization": f"Token {os.environ['PRETIX_API_TOKEN']}"
}

def getJsonData(url, filename):

    results = []

    while url:
        print(f'Read {url}')
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code}\n\t{response.text}\n\t{response.url}")

        data = response.json()

        results.extend(data.get("results", []))
        url = data['next']

    with open(filename, 'w') as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

# Call the functions to execute the code

root = Path(__file__).parent / "data" / EVENT_ID
os.makedirs(root, exist_ok=True)

getJsonData(QUESTIONS, root / "questions.json")
getJsonData(ITEM_CATEGORY_URL, root / "categories.json")
getJsonData(ORDER_URL, root / "orders.json")
getJsonData(INVOICE_URL, root / "invoices.json")
getJsonData(NREI_URL, root / "nrei.json")
getJsonData(ITEMS_URL, root / "items.json")
