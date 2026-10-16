from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext_thailand.constants import ETAX_CUSTOM_FIELDS


def execute():
	create_custom_fields(ETAX_CUSTOM_FIELDS, ignore_validate=True)
