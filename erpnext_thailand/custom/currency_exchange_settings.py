import frappe
import requests
from frappe import _
from erpnext.accounts.doctype.currency_exchange_settings.currency_exchange_settings import CurrencyExchangeSettings
from frappe.utils import nowdate


class CurrencyExchangeSettings(CurrencyExchangeSettings):

	def validate_parameters(self):
		if self.service_provider == "Bank of Thailand":
			params = {}
			for row in self.req_params:
				params[row.key] = row.value.format(
					transaction_date=nowdate(), to_currency="THB", from_currency="USD"
				)
			params["client_id"] = self.client_id
			api_url = self.api_endpoint.format(
				transaction_date=nowdate(), to_currency="THB", from_currency="USD")
			try:
				response = requests.get(api_url, params=params)
			except requests.exceptions.RequestException as e:
				frappe.throw("Error: " + str(e))
			response.raise_for_status()
			value = response.json()
			return response, value
		else:
			return super().validate_parameters()

	def validate_result(self, response, value):
		if self.service_provider == "Bank of Thailand":
			try:
				for key in self.result_key:
					value = value[
						str(key.key).format(transaction_date=nowdate(), to_currency="THB", from_currency="USD")
					]
			except Exception:
				frappe.throw(_("Invalid result key. Response:") + " " + response.text)
			if not isinstance(value, int | float):
				frappe.throw(_("Returned exchange rate is neither integer not float."))
			self.url = response.url
		else:
			super().validate_result(response, value)
