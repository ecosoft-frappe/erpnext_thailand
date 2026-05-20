# Copyright (c) 2024, FLO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from collections import defaultdict

class PaymentReceipt(Document):

    def validate(self):
        self.update_payment_references()
        self.update_billing_references()
        self.update_total_paid_amount()

    def on_submit(self):
        self.check_payment_references()

    def check_payment_references(self):
        if not self.payment_references:
            frappe.throw(_("No Payment References found!"))
        unsubmitted_references = []
        for pr in self.payment_references:
            payment = frappe.get_doc("Payment Entry", pr.payment_entry)
            if payment.docstatus != 1:unsubmitted_references.append(payment.name)
        if unsubmitted_references:
            frappe.throw(_("Unsubmitted Payment References: {0}").format(", ".join(unsubmitted_references)))

    def update_payment_references(self):
        pe_names = get_payment_entries_for_billing(self.sales_billing) if self.sales_billing else []
        self.payment_references = []
        for name in pe_names:
            self.append("payment_references", {"payment_entry": name})

    def update_billing_references(self):
        self.billing_references = []
        allocated = self.get_sum_allocated_by_invoice()
        sales_billing = frappe.get_doc("Sales Billing", self.sales_billing)
        for ref in sales_billing.sales_billing_line:
            self.append("billing_references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": ref.sales_invoice,
                "due_date": ref.due_date,
                "grand_total": ref.grand_total,
                "outstanding_amount": ref.outstanding_amount,
                "allocated_amount": allocated[ref.sales_invoice]["allocated"],
            })
    
    def get_sum_allocated_by_invoice(self):
        group = defaultdict(lambda: {"allocated": 0.0})
        for pr in self.payment_references:
            pe = frappe.get_doc("Payment Entry", pr.payment_entry)
            for pe_ref in pe.references:
                if pe_ref.reference_doctype == "Sales Invoice":
                    key = pe_ref.reference_name
                    group[key]["allocated"] += pe_ref.allocated_amount
        return group

    def update_total_paid_amount(self):
        self.total_paid_amount = sum([r.paid_amount for r in self.payment_references])
        self.total_invoice_amount = sum([r.grand_total for r in self.billing_references])

    def get_payment_entries_for_billing(sales_billing):
        result = frappe.get_all("Payment Entry", {"sales_billing": sales_billing, "docstatus": 1}, pluck="name")
        if result:
            return result

        invoices = frappe.get_all("Sales Billing Line", {"parent": sales_billing}, pluck="sales_invoice")
        if not invoices:
            return []

        pe_names = list(set(frappe.get_all("Payment Entry Reference", {
            "reference_doctype": "Sales Invoice", "reference_name": ["in", invoices],
        }, pluck="parent")))

        return frappe.get_all("Payment Entry", {"name": ["in", pe_names], "docstatus": 1}, pluck="name") if pe_names else []