from frappe.custom.doctype.custom_field.custom_field import \
    create_custom_fields

from erpnext_thailand.constants import DEPOSIT_CUSTOM_FIELDS


def execute():
    custom_fields = {
        "Sales Invoice": DEPOSIT_CUSTOM_FIELDS["Sales Invoice"],
        "Purchase Invoice": DEPOSIT_CUSTOM_FIELDS["Purchase Invoice"],
    }
    create_custom_fields(custom_fields, ignore_validate=True)
