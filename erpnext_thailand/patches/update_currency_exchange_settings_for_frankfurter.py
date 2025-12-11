import frappe
from erpnext_thailand.constants import ERP_PROPERTY_SETTERS
from frappe.custom.doctype.property_setter.property_setter import \
    make_property_setter


def execute():
    # Update options for the service_provider field
    make_property_setter("Currency Exchange Settings", *ERP_PROPERTY_SETTERS.get("Currency Exchange Settings")[0])

    # Update service provider from frankfurter.app to frankfurter.dev
    settings_meta = frappe.get_meta("Currency Exchange Settings")
    settings = frappe.get_doc("Currency Exchange Settings")

    if (
        "frankfurter.dev" not in settings_meta.get_options("service_provider").split("\n")
        or settings.service_provider != "frankfurter.app"
    ):
        return

    settings.service_provider = "frankfurter.dev"
    settings.set_parameters_and_result()
    settings.flags.ignore_validate = True
    settings.save()
