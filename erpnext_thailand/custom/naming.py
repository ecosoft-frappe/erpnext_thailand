from frappe.model.naming import determine_consecutive_week_number
from frappe.utils import getdate


def parse_naming_series_variable(doc, variable):
	"""Use date to get part"""
	date = getdate()
	if doc:
		date = (
			doc.get("posting_date")
			or doc.get("transaction_date")
			or doc.get("date")
			or getdate()
		)
		if isinstance(date, str):
			date = getdate(date)
	if variable == "YYYY-DATE":
		return date.strftime("%Y")
	if variable == "YY-DATE":
		return date.strftime("%y")
	if variable == "MM-DATE":
		return date.strftime("%m")
	if variable == "DD-DATE":
		return date.strftime("%d")
	if variable == "WW-DATE":
		return determine_consecutive_week_number(date)
