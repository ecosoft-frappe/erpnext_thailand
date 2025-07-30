import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry
from .payment_entry import reconcile_undue_tax_gls


class JournalEntry(JournalEntry):

	def get_gl_dict(self, args, account_currency=None, item=None):
		gl_dict = super().get_gl_dict(args, account_currency=account_currency, item=item)
		if item and item.doctype == "Journal Entry Account":
			gl_dict.update({
				"petty_cash_holder": item.petty_cash_holder,
				"petty_cash_holder_name": item.petty_cash_holder_name,
			})
		return gl_dict


def reconcile_undue_tax(jv, method):
	""" If bs_reconcile is installed, reconcile undue tax gls """
	if jv.for_payment:
		pay = frappe.get_doc("Payment Entry", jv.for_payment)
		vouchers = [jv.name, pay.name] + [r.reference_name for r in pay.references]
		reconcile_undue_tax_gls(vouchers, pay.company)
