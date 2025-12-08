from erpnext_thailand.constants import ERP_PROPERTY_SETTERS
from frappe.custom.doctype.property_setter.property_setter import \
    make_property_setter


def execute():
    make_property_setter("Currency Exchange Settings", *ERP_PROPERTY_SETTERS.get("Currency Exchange Settings")[0])
