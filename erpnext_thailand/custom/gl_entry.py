import frappe


def rename_gl_entry_in_tax_invoice(newname, oldname):
	for tax_invoice in ["Sales Tax Invoice", "Purchase Tax Invoice"]:
		frappe.db.sql(
			f"UPDATE `tab{tax_invoice}` SET gl_entry = %s where gl_entry = %s",
			(newname, oldname)
		)
