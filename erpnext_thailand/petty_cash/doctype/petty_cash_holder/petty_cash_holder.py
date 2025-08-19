# Copyright (c) 2025, Ecosoft and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PettyCashHolder(Document):

	def validate(self):
		petty_cash_float = self.petty_cash_float or 0
		petty_cash_balance = self.petty_cash_balance or 0
		if petty_cash_float < petty_cash_balance:
			frappe.throw(_("The petty cash balance ({:,.2f}) must not exceed the petty cash float ({:,.2f}).").format(self.petty_cash_balance, self.petty_cash_float))


@frappe.whitelist()
def create_journal_entry(posting_date, petty_cash_holder, from_account, to_account, amount:float, type):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.update(
		{
			"voucher_type": "Cash Entry",
			"posting_date": posting_date,
		}
	)

	debit_entry = {
		"account": to_account,
		"debit_in_account_currency": amount,
		"credit_in_account_currency": 0,
	}

	credit_entry = {
		"account": from_account,
		"debit_in_account_currency": 0,
		"credit_in_account_currency": amount,
	}

	if type == "topup":
		debit_entry["petty_cash_holder"] = petty_cash_holder
	elif type == "withdraw":
		credit_entry["petty_cash_holder"] = petty_cash_holder

	journal_entry.append("accounts", debit_entry)
	journal_entry.append("accounts", credit_entry)
	journal_entry.save()
	journal_entry.submit()
	return journal_entry
