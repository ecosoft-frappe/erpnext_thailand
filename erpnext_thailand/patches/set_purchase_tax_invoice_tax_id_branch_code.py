import frappe

from erpnext_thailand.thai_tax.doctype.purchase_tax_invoice.purchase_tax_invoice import (
	get_supplier_tax_id_branch_code,
)


def execute():
	"""Tax ID and Branch Code were virtual fields read from the supplier, store them"""
	tax_invoices = frappe.get_all(
		"Purchase Tax Invoice",
		or_filters={"tax_id": ["is", "not set"], "branch_code": ["is", "not set"]},
		fields=["name", "party", "voucher_type", "voucher_no"],
	)
	for tinv in tax_invoices:
		tax_id, branch_code = get_supplier_tax_id_branch_code(
			tinv.party, tinv.voucher_type, tinv.voucher_no
		)
		frappe.db.set_value(
			"Purchase Tax Invoice",
			tinv.name,
			{"tax_id": tax_id, "branch_code": branch_code},
			update_modified=False,
		)
