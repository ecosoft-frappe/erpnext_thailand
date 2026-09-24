from frappe import _


def get_data():
	return {
		"fieldname": "sales_billing",
		"non_standard_fieldnames": {
			"Sales Billing": "sales_invoice",
			"Payment Entry": "sales_billing",
			"Payment Receipt": "sales_billing",
		},
		"internal_and_external_links": {
			"Sales Invoice": ["sales_billing_line", "sales_invoice"],
			"Payment Entry": ["sales_billing_line", "sales_billing"],
		},
		"transactions": [
			{"label": _("Reference"), "items": ["Sales Invoice"]},
			{"label": _("Payment"), "items": ["Payment Entry", "Payment Receipt"]},
		],
	}
