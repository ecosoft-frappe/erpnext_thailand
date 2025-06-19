from frappe import _


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
	return data


def get_dashboard_data_for_expense_claim(data):
	data["non_standard_fieldnames"].update({"Purchase Tax Invoice": "voucher_no"})
	data["transactions"].append(
		{"label": _("Tax Invoice"), "items": ["Purchase Tax Invoice"]}
	)
	return data


def get_dashboard_data_for_payment_entry(data):
	data["non_standard_fieldnames"].update({"Withholding Tax Cert": "voucher_no"})
	data["transactions"].extend(
		[
			{"items": ["Payment Receipt"]},
			{"items": ["Withholding Tax Cert"]}
		]
	)
	return data
