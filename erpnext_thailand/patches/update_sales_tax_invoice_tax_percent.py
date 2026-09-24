import frappe


def execute():
	"""Update Sales Tax Invoice tax percent"""
	for doc in frappe.get_all("Sales Tax Invoice"):
		script_doc = frappe.get_doc("Sales Tax Invoice", doc.name)
		script_doc.compute_tax_percent()
		frappe.db.commit()
