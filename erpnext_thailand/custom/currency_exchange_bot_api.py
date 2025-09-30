import frappe
import json
import http.client
from datetime import datetime, timedelta


@frappe.whitelist(allow_guest=True)
def get_api_currency_exchange(
	from_currency, to_currency, transaction_date, token=None):
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

	if not token:
		currency_exchange_settings = frappe.get_single("Currency Exchange Settings")
		token = currency_exchange_settings.get_password("token")

	conn = http.client.HTTPSConnection("gateway.api.bot.or.th")
	headers = {
		"Authorization": token,
		"accept": "application/json",
        "Content-Type": "application/json",
	}

	# Properly formatted URL with dynamic date parameters
	url_path = f"/Stat-ExchangeRate/v2/DAILY_AVG_EXG_RATE/?start_period={start_date}&end_period={end_date}&currency={currency}"
	conn.request("GET", url_path, headers=headers)

	# Respose
	res = conn.getresponse()
	data = res.read()
	result = data.decode("utf-8")

	# To Json
	parsed_result = json.loads(result)

	rates = 0
	# Check if "data_detail" exists and has items
	if "data_detail" in parsed_result["result"]["data"] and parsed_result["result"]["data"]["data_detail"]:
		data_detail = parsed_result["result"]["data"]["data_detail"]

		# Sort data by the "period" field if not empty
		if data_detail:
			sorted_data = sorted(data_detail, key=lambda x: datetime.strptime(x["period"], "%Y-%m-%d"))

			# Get the latest period's data (the last element in the sorted list)
			latest_period_data = sorted_data[-1]
			rates = float(latest_period_data["selling"])

	# Creating the response dictionary
	response_data = {
		"amount": 1.0,
		"from_currency": from_currency,
		"date": transaction_date,
		"rates": {to_currency: rates}  # Assume rate is static for example
	}
	print("response_data", response_data)
	# Setting the response directly to avoid Frappe's automatic "data" wrapping
	frappe.local.response.http_status_code = 200  # Setting HTTP status code
	frappe.local.response.message = response_data
