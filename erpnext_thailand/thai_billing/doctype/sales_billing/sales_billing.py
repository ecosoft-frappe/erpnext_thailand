# Copyright (c) 2023, FLO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import cint


class SalesBilling(Document):

    def validate(self):
        invoices = [i.sales_invoice for i in self.sales_billing_line]
        if len(invoices) > len(list(set(invoices))):
            frappe.throw(_("Please do not select same sales invoice more than once!"))
        total_outstanding_amount = sum([i.outstanding_amount for i in self.sales_billing_line])
        total_billing_amount = sum([i.grand_total for i in self.sales_billing_line])
        self.total_outstanding_amount = total_outstanding_amount
        self.total_billing_amount = total_billing_amount


@frappe.whitelist()
def get_due_billing(customer=None, currency=None, tax_type=None, threshold_type=None, threshold_date=None, include_draft_invoices=None):
    if not (customer, currency, tax_type, threshold_date):
        return {}
    docstatus = [1]
    if cint(include_draft_invoices):
        docstatus = [0, 1]
    filters = {
        "customer": customer,
        "currency": currency,
        "docstatus": ["in", docstatus],
        "outstanding_amount": ["!=", 0]
    }
    if tax_type:
        filters["taxes_and_charges"] = tax_type
    if threshold_type == "Due Date":
        filters["due_date"] = ["<=", threshold_date]
    if threshold_type == "Invoice Date":
        filters["posting_date"] = ["<=", threshold_date]
    invoices = frappe.get_list(
        "Sales Invoice",
        filters=filters,
        fields=["name", "posting_date", "due_date", "po_no", "grand_total", "outstanding_amount", "payment_terms_template"]
    )
    # Exclude invoices which are in other submitted sales billing
    # use frappe query builder to joinb Sales Billing and Sales Billing Line
    SalesBilling = DocType("Sales Billing")
    SalesBillingLine = DocType("Sales Billing Line")

    excluded_invoices = (
        frappe.qb.from_(SalesBilling)
        .join(SalesBillingLine)
        .on(SalesBilling.name == SalesBillingLine.parent)
        .where(SalesBilling.docstatus == 1)
		.where(SalesBilling.closed == 0)
        .select(SalesBillingLine.sales_invoice)
    ).run()

    excluded_invoices = [d[0] for d in excluded_invoices]
    invoices = [inv for inv in invoices if inv["name"] not in excluded_invoices]
    return invoices


@frappe.whitelist()
def create_multi_payment_entries(payment_details, sales_billing_name, posting_date, allocate_amount=0):
    import json
    try:
        payment_details = json.loads(payment_details)
    except Exception:
        frappe.throw(_("Failed to parse payment details. Please check your input."))

    sales_billing = frappe.get_doc("Sales Billing", sales_billing_name)
    customer, company = sales_billing.customer, sales_billing.company
    company_currency = frappe.get_value("Company", company, "default_currency")

    payment_entries = []
    for detail in payment_details:
        detail = frappe._dict(detail)
        mode_of_payment = detail.mode_of_payment
        paid_to = frappe.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account")
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": customer,
            "posting_date": posting_date,
            "mode_of_payment": mode_of_payment,
            "bank_account": detail.company_bank_account,
            "party_bank_account": detail.party_bank_account,
            "paid_amount": detail.paid_amount,
            "received_amount": detail.paid_amount,
            "company": company,
            "sales_billing": sales_billing_name,
            "target_exchange_rate": 1,
            "paid_to": paid_to,
            "account_currency": company_currency,
            "reference_no": detail.chequereference_no,
            "reference_date": detail.chequereference_date,
        })
        for line in sales_billing.sales_billing_line:
            if not line.outstanding_amount:
                continue
            if line.sales_invoice:
                payment_entry.append("references", {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": line.sales_invoice,
                    "allocated_amount": 1  # Need an amount to avoid this ref line being removed
                })
        payment_entry.validate()  # Validate to get the total outstanding
        if int(allocate_amount):
            payment_entry.allocate_amount_to_references(payment_entry.paid_amount, False, True)
        payment_entry.insert()
        payment_entries.append(payment_entry.name)
        # If allocated, auto submit is required because potentially there are > 1 payment entries
        if int(allocate_amount):
            payment_entry.submit()
    
    res = {
        "payment_entries": payment_entries,
        "payment_receipt_name": None
    }

    # Create Payment Receipt based on configuration
    create_receipt = frappe.db.get_single_value("Thai Billing Settings", "create_payment_receipt_from_sales_billing")
    if create_receipt:
        payment_receipt = frappe.get_doc({
            "doctype": "Payment Receipt",
            "sales_billing": sales_billing_name,
            "company": company,
            "customer": customer,
            "date": posting_date,
        })
        for pe in payment_entries:
            payment_receipt.append("payment_references", {
                "payment_entry": pe,
            })
        payment_receipt.insert()
        # If allocated, auto submit it
        if int(allocate_amount):
            payment_receipt.submit()
        res["payment_receipt_name"] = payment_receipt.name

    return res