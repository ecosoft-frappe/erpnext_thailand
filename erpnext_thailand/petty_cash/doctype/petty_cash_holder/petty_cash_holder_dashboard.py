from frappe import _

def get_data():
	return {
		"fieldname": "petty_cash_holder",
		"transactions": [
			{"label": _("Journal Entry"), "items": ["Journal Entry"]},
		],
	}
