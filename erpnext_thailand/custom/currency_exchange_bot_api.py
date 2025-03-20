import frappe # type: ignore
from frappe import _ # type: ignore
import http.client
from datetime import datetime, timedelta
import json


@frappe.whitelist(allow_guest=True)
def get_api_currency_exchange(from_currency, to_currency, transaction_date):

    # Convert the transaction_date string to a datetime object
    trans_start_date = datetime.strptime(transaction_date, "%Y-%m-%d")
    trans_start_date = trans_start_date - timedelta(days=5)

    trans_start_date = trans_start_date.strftime("%Y-%m-%d")

    trans_end_date = datetime.strptime(transaction_date, "%Y-%m-%d")
    trans_end_date = trans_end_date.strftime("%Y-%m-%d")

    # Params to BOT API
    start_date = trans_start_date
    end_date = trans_end_date
    currency = from_currency

    site_config = frappe.get_site_config()
    client_id = site_config.get("bot_client_id")
    conn = http.client.HTTPSConnection("apigw1.bot.or.th")
    headers = {
        'X-IBM-Client-Id': client_id,
        'accept': "application/json"
    }

    # Properly formatted URL with dynamic date parameters
    url_path = f"/bot/public/Stat-ExchangeRate/v2/DAILY_AVG_EXG_RATE/?start_period={start_date}&end_period={end_date}&currency={currency}"
    conn.request("GET", url_path, headers=headers)

    # Respose
    res = conn.getresponse()
    data = res.read()
    result = data.decode("utf-8")

    # To Json
    parsed_result = json.loads(result)

    rates = 0
    # Check if 'data_detail' exists and has items
    if 'data_detail' in parsed_result['result']['data'] and parsed_result['result']['data']['data_detail']:
        data_detail = parsed_result['result']['data']['data_detail']

        # Sort data by the 'period' field if not empty
        if data_detail:
            sorted_data = sorted(data_detail, key=lambda x: datetime.strptime(x['period'], '%Y-%m-%d'))

            # Get the latest period's data (the last element in the sorted list)
            latest_period_data = sorted_data[-1]
            rates = latest_period_data['selling']
            rates = float(rates)
        else:
            rates = 0
    else:
        rates = 0

    # Creating the response dictionary
    response_data = {
        'amount': 1.0,
        'from_currency': from_currency,
        'date': transaction_date,
        'rates': {to_currency: rates}  # Assume rate is static for example
    }
    print('response_data', response_data)
    # Setting the response directly to avoid Frappe's automatic "data" wrapping
    frappe.local.response.http_status_code = 200  # Setting HTTP status code
    frappe.local.response.message = response_data 