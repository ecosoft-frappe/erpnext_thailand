from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import ERP_CUSTOM_FIELDS


def execute():
    create_custom_fields({"Currency": ERP_CUSTOM_FIELDS["Currency"]}, ignore_validate=True)
