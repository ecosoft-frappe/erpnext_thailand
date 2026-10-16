from frappe import _


def add_etax_logs(data, doctype):
	"""e-Tax requests and responses kept in Integration Request"""
	data.setdefault("non_standard_fieldnames", {})[
		"Integration Request"
	] = "reference_docname"
	data.setdefault("dynamic_links", {})["reference_docname"] = [
		doctype,
		"reference_doctype",
	]
	data["transactions"].append({"label": _("e-Tax"), "items": ["Integration Request"]})


def get_dashboard_data_for_purchase_invoice(data):
	data["non_standard_fieldnames"].update({"Purchase Tax Invoice": "voucher_no"})
	data["transactions"].append(
		{"label": _("Tax Invoice"), "items": ["Purchase Tax Invoice"]}
	)
	for transaction in data["transactions"]:
		if transaction["label"] == _("Reference"):
			transaction["items"].append("Purchase Billing")
	return data


def get_dashboard_data_for_sales_invoice(data):
	data["non_standard_fieldnames"].update({"Sales Tax Invoice": "voucher_no"})
	data["transactions"].append(
		{"label": _("Tax Invoice"), "items": ["Sales Tax Invoice"]},
	)
	for transaction in data["transactions"]:
		if transaction["label"] == _("Reference"):
			transaction["items"].append("Sales Billing")
	add_etax_logs(data, "Sales Invoice")
	return data


def get_dashboard_data_for_expense_claim(data):
	data["non_standard_fieldnames"].update({"Purchase Tax Invoice": "voucher_no"})
	data["transactions"].append(
		{"label": _("Tax Invoice"), "items": ["Purchase Tax Invoice"]}
	)
	return data


def get_dashboard_data_for_payment_entry(data):
	data["transactions"].append({"items": ["Payment Receipt"]})
	add_etax_logs(data, "Payment Entry")
	return data
