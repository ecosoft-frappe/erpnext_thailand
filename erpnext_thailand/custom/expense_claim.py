import frappe
from frappe import _
from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim

class ExpenseClaim(ExpenseClaim):

    def before_submit(self):
        super().before_submit()
        if self.is_petty_cash:
            petty_cash_limit = frappe.get_value(
                "Petty Cash Holder",
                self.petty_cash_holder,
                "petty_cash_limit",
            )
            if petty_cash_limit and self.grand_total > petty_cash_limit:
                frappe.throw(_("This transaction exceeds the allowed petty cash limit."))

    def validate(self):
        super().validate()
        if not self.is_petty_cash and (self.petty_cash_holder or self.petty_cash_holder_name):
            self.update({
                "petty_cash_holder": "",
                "petty_cash_holder_name": "",
            })
