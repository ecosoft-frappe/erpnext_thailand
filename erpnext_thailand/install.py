import json

import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext_thailand.constants import (
	BILLING_CUSTOM_FIELDS,
	DEPOSIT_CUSTOM_FIELDS,
	ERP_CUSTOM_FIELDS,
	ERP_PROPERTY_SETTERS,
	HRMS_CUSTOM_FIELDS,
)
from erpnext_thailand.utils import import_thai_zip_code_data


def after_install():
	try:
		print("Setting up ERPNext Thailand...")
		make_custom_fields()
		make_property_setters()
		print("Importing Thailand Zip Codes...")
		import_thai_zip_code_data()
		add_thai_tax_to_accounts_sidebar()
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


THAI_TAX_SIDEBAR_LINKS = (
	("DocType", "Sales Tax Invoice"),
	("DocType", "Purchase Tax Invoice"),
	("DocType", "Sales Billing"),
	("DocType", "Purchase Billing"),
	("DocType", "Payment Receipt"),
	("Report", "Sales Tax Report"),
	("Report", "Purchase Tax Report"),
	("Report", "PND3"),
	("Report", "PND53"),
	("DocType", "Thai Tax Settings"),
	("DocType", "Withholding Tax Type"),
)


def add_thai_tax_to_accounts_sidebar():
	"""Add a Thai Tax section below Journal Entry in the Accounts sidebar (site layer)."""
	from frappe.desk.doctype.custom_sidebar import custom_sidebar

	if not frappe.db.exists("DocType", "Custom Sidebar"):
		return

	items = custom_sidebar.layer_arrangement("Accounts", None)
	if any(item.get("type") == "Section Break" and item.get("label") == "Thai Tax" for item in items):
		return

	print("Adding Thai Tax to Accounts sidebar...")
	section = [
		{
			"type": "Section Break",
			"label": "Thai Tax",
			"icon": "receipt-text",
			"indent": 1,
			"collapsible": 1,
			"keep_closed": 1,
			"child": 0,
			"added": 1,
		}
	]
	section += [
		{
			"type": "Link",
			"label": link_to,
			"link_type": link_type,
			"link_to": link_to,
			"child": 1,
			"collapsible": 1,
			"added": 1,
		}
		for link_type, link_to in THAI_TAX_SIDEBAR_LINKS
	]

	position = next(
		(i + 1 for i, item in enumerate(items) if item.get("link_to") == "Journal Entry"),
		len(items),
	)
	items[position:position] = section
	custom_sidebar._save_customization("Accounts", items, user=None)


def after_app_install(app_name):
	if app_name == "hrms":
		create_custom_fields(HRMS_CUSTOM_FIELDS, ignore_validate=True)
		# Change order erpnext_thailand after hrms
		installed_apps = frappe.get_installed_apps()
		installed_apps.remove("erpnext_thailand")
		installed_apps.append("erpnext_thailand")
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
