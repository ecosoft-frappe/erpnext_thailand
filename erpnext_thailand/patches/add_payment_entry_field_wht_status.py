import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext_thailand.constants import ERP_CUSTOM_FIELDS
from erpnext_thailand.thai_tax.doctype.withholding_tax_cert.withholding_tax_cert import (
	update_payment_entry_wht_status,
)


def execute():
	custom_fields = {
		"Payment Entry": list(
			filter(
				lambda l: l["fieldname"] == "wht_status",
				ERP_CUSTOM_FIELDS["Payment Entry"],
			)
		)
	}
	create_custom_fields(custom_fields, ignore_validate=True)

	# Set status for payments with existing certs
	vouchers = frappe.get_all(
		"Withholding Tax Cert",
		filters={"voucher_type": "Payment Entry", "voucher_no": ["is", "set"]},
		pluck="voucher_no",
		distinct=True,
	)
	for voucher_no in vouchers:
		update_payment_entry_wht_status("Payment Entry", voucher_no)

	# Payments without any cert
	frappe.db.set_value(
		"Payment Entry",
		{"wht_status": ["is", "not set"]},
		"wht_status",
		"Not Issued",
		update_modified=False,
	)
