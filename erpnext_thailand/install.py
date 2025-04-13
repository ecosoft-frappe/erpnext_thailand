import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import \
    create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import \
    make_property_setter

from erpnext_thailand.constants import (
    ERP_CUSTOM_FIELDS, ERP_PROPERTY_SETTERS,
    HRMS_CUSTOM_FIELDS, BILLING_CUSTOM_FIELDS,
	DEPOSIT_CUSTOM_FIELDS
)


def after_install():
	try:
		print("Setting up ERPNext Thailand...")
		make_custom_fields()
		make_property_setters()
		click.secho("Thank you for installing ERPNext Thailand!", fg="green")
	except Exception as e:
		BUG_REPORT_URL = "https://github.com/ecosoft-frappe/erpnext_thailand/issues/new"
		click.secho(
			"Installation for ERPNext Thailand app failed due to an error."
			" Please try re-installing the app or"
			f" report the issue on {BUG_REPORT_URL} if not resolved.",
			fg="bright_red",
		)
		raise e


def make_custom_fields():
	print("Setup custom fields for erpnext...")
	create_custom_fields(ERP_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(BILLING_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(DEPOSIT_CUSTOM_FIELDS, ignore_validate=True)
	if "hrms" in frappe.get_installed_apps():
		print("Setup custom fields for hrms...")
		create_custom_fields(HRMS_CUSTOM_FIELDS, ignore_validate=True)


def make_property_setters():
	print("Setup property setters for erpnext...")
	for doctypes, property_setters in ERP_PROPERTY_SETTERS.items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)
		for doctype in doctypes:
			for property_setter in property_setters:
				for_doctype = not property_setter[0]
				make_property_setter(doctype, *property_setter, for_doctype)


def after_app_install(app_name):
	if app_name == "hrms":
		create_custom_fields(HRMS_CUSTOM_FIELDS, ignore_validate=True)
