from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from ..constants import ERP_PROPERTY_SETTERS


def execute():
	property_setters = ERP_PROPERTY_SETTERS.get("Document Naming Settings", [])
	for property_setter in property_setters:
		for_doctype = not property_setter[0]
		make_property_setter("Document Naming Settings", *property_setter, for_doctype)
