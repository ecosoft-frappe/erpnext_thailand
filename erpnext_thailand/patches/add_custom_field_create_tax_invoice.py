from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext_thailand.constants import ERP_CUSTOM_FIELDS


def execute():
	custom_fields = {
		"Journal Entry": list(
			filter(
				lambda l: l["fieldname"] in ["create_tax_invoice", "tax_invoice"],
				ERP_CUSTOM_FIELDS["Journal Entry"],
			)
		)
	}
	create_custom_fields(custom_fields, ignore_validate=True)
