import frappe


def before_tests():
	"""Add a Thai Tax Settings row for each ERPNext test company.

	This app's document hooks require a Thai Tax Settings row for the company.
	ERPNext creates its test records (e.g. Sales Invoices of "_Test Company")
	while this app's tests run, so give each test company a row without tax accounts.
	"""
	settings = frappe.get_single("Thai Tax Settings")
	existing = {row.company for row in settings.company_accounts}
	for company in frappe.get_test_records("Company"):
		if company["company_name"] not in existing:
			settings.append("company_accounts", {"company": company["company_name"]})
	# Test companies are created later, together with the test records
	settings.flags.ignore_links = True
	settings.save(ignore_permissions=True)
	frappe.db.commit()
