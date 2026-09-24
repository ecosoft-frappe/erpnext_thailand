from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from ..constants import ERP_PROPERTY_SETTERS


def execute():
	make_property_setter("Sales Invoice", *ERP_PROPERTY_SETTERS.get("Sales Invoice")[0])
	make_property_setter(
		"Purchase Invoice", *ERP_PROPERTY_SETTERS.get("Purchase Invoice")[0]
	)
