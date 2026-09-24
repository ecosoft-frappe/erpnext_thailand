from frappe import _


def get_data():
	return {
		"fieldname": "payment_receipt",
		"internal_and_external_links": {
			"Sales Billing": "sales_billing",
			"Payment Entry": ["payment_references", "payment_entry"],
			"Sales Invoice": ["billing_references", "reference_name"],
		},
		"transactions": [{"items": ["Payment Entry", "Sales Billing", "Sales Invoice"]}],
	}
