
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import ERP_CUSTOM_FIELDS

def execute():
    custom_fields = {
        "Purchase Invoice Item": ERP_CUSTOM_FIELDS["Purchase Invoice Item"]
    }
    create_custom_fields(custom_fields, ignore_validate=True)
