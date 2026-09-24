import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext_thailand.constants import ERP_CUSTOM_FIELDS, ERP_PROPERTY_SETTERS


def execute():
	frappe.db.delete(
		"Custom Field", {"fieldname": "client_id", "dt": "Currency Exchange Settings"}
	)
	custom_fields = {
		"Currency Exchange Settings": list(
			filter(
				lambda l: l["fieldname"] in ["client_id"],
				ERP_CUSTOM_FIELDS["Currency Exchange Settings"],
			)
		)
	}
	create_custom_fields(custom_fields, ignore_validate=True)
	make_property_setter(
		"Currency Exchange Settings",
		*ERP_PROPERTY_SETTERS.get("Currency Exchange Settings")[0]
	)
