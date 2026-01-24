# Copyright (c) 2024, Ecosoft and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType


class PurchaseBilling(Document):
	def validate(self):
		invoices = [i.purchase_invoice for i in self.purchase_billing_line]
		if len(invoices) > len(list(set(invoices))):
			frappe.throw(_("Please do not select same Purchase Invoice more than once!"))
		total_outstanding_amount = sum([i.outstanding_amount for i in self.purchase_billing_line])
		total_billing_amount = sum([i.grand_total for i in self.purchase_billing_line])
		self.total_outstanding_amount = total_outstanding_amount
		self.total_billing_amount = total_billing_amount


@frappe.whitelist()
def get_due_billing(supplier=None, currency=None, tax_type=None, threshold_type=None, threshold_date=None):
	if not (supplier, currency, tax_type, threshold_date):
		return {}
	filters = {
		"supplier": supplier,
		"currency": currency,
		"docstatus": 1,
		"outstanding_amount": ["!=", 0]
	}
	# ปิดเงื่อนไข outstanding_amount

	if tax_type:
		filters["taxes_and_charges"] = tax_type
	if threshold_type == "Due Date":
		filters["due_date"] = ["<=", threshold_date]
	if threshold_type == "Invoice Date":
		filters["posting_date"] = ["<=", threshold_date]
	invoices = frappe.get_list(
		"Purchase Invoice",
		filters=filters,
		fields=["name", "posting_date", "due_date", "po_no", "grand_total", "outstanding_amount", "payment_terms_template"]
	)

	PurchaseBilling = DocType("Purchase Billing")
	PurchaseBillingLine = DocType("Purchase Billing Line")

	excluded_invoices = (
		frappe.qb.from_(PurchaseBilling)
		.join(PurchaseBillingLine)
		.on(PurchaseBilling.name == PurchaseBillingLine.parent)
		.where(PurchaseBilling.docstatus == 1)
		.select(PurchaseBillingLine.purchase_invoice)
	).run()

	excluded_invoices = [d[0] for d in excluded_invoices]
	invoices = [inv for inv in invoices if inv["name"] not in excluded_invoices]
	return invoices


def update_sales_billing_outstanding_amount(doc, method):
    # Document: Payment Entry
    total_outstanding_amount = 0
    if not doc.purchase_billing:
        return
    bill = frappe.get_doc("Purchase Billing", doc.purchase_billing)
    for bill_line in bill.purchase_billing_line:
        invoice = frappe.get_doc("Purchase Invoice", bill_line.purchase_invoice)
        bill_line.outstanding_amount = invoice.outstanding_amount
        total_outstanding_amount += invoice.outstanding_amount
    bill.total_outstanding_amount = total_outstanding_amount
    print("bill.total_outstanding_amount", bill.total_outstanding_amount)
    bill.save()