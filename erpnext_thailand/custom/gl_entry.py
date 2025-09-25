import frappe
from frappe import _
from erpnext.accounts.doctype.gl_entry.gl_entry import GLEntry


class GLEntry(GLEntry):

	def after_insert(self):
		if self.petty_cash_holder and self.account:
			petty_cash_holder = frappe.get_value("Petty Cash Holder", {"name": self.petty_cash_holder, "petty_cash_account": self.account})
			if not petty_cash_holder:
				frappe.throw(_("Petty Cash Holder doesn't exist."))
			# Check petty cash holder enabled
			disabled = frappe.get_value("Petty Cash Holder", petty_cash_holder, "disabled")
			if disabled == 1:
				frappe.throw(_("The petty cash holder ({}: {}) is currently disabled. Please enable it before proceeding with this transaction.").format(self.petty_cash_holder, self.petty_cash_holder_name))
			# Check amount
			gl_entries = frappe.get_all(
				"GL Entry",
				filters={
					"petty_cash_holder": petty_cash_holder,
					"account": self.account,
				},
				group_by="petty_cash_holder",
				fields=["petty_cash_holder", "sum(debit) as debit", "sum(credit) as credit"]
			)
			petty_cash_balance = gl_entries[0].debit - gl_entries[0].credit
			petty_cash_float = frappe.get_value("Petty Cash Holder", petty_cash_holder, "petty_cash_float")
			if petty_cash_balance > petty_cash_float:
				frappe.throw(_("The petty cash balance ({:,.2f}) must not exceed the petty cash float ({:,.2f}).").format(petty_cash_balance, petty_cash_float))
			frappe.set_value("Petty Cash Holder", petty_cash_holder, "petty_cash_balance", petty_cash_balance)


def rename_gl_entry_in_tax_invoice(newname, oldname):
	for tax_invoice in ["Sales Tax Invoice", "Purchase Tax Invoice"]:
		frappe.db.sql(
			f"UPDATE `tab{tax_invoice}` SET gl_entry = %s where gl_entry = %s",
			(newname, oldname)
		)
