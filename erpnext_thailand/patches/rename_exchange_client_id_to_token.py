import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import ERP_CUSTOM_FIELDS


def execute():
    frappe.db.delete("Custom Field", {"fieldname": "client_id", "dt": "Currency Exchange Settings"})
    custom_fields = {
        "Currency Exchange Settings": list(filter(lambda l: l["fieldname"] in ["token"], ERP_CUSTOM_FIELDS["Currency Exchange Settings"]))
    }
    create_custom_fields(custom_fields, ignore_validate=True)