import frappe
import urllib3
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import flt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_thai_tax_settings(company):
    settings = frappe.get_single("Thai Tax Settings")
    accounts = list(filter(lambda x: x.company == company, settings.company_accounts))
    if not accounts:
        frappe.throw(_("Please set up {0} for company {1}").format(
			frappe.utils.get_link_to_form("Thai Tax Settings", "Thai Tax Settings"),
   			company,
		))
    return accounts[0]


def create_tax_invoice_on_gl_tax(doc, method):
	if doc.flags.from_repost:
		return
	# Auto create Tax Invoice only when account equal to tax account.
	setting = get_thai_tax_settings(doc.company)
	doctype = False
	tax_amount = 0.0
	voucher = frappe.get_doc(doc.voucher_type, doc.voucher_no)
	
	# Check if the voucher is a tax invoice related doctypes
	if voucher.doctype not in [
     	"Sales Invoice",
      	"Purchase Invoice",
       	"Payment Entry",
        "Expense Claim",
        "Journal Entry",
    ]:
		return
 
	is_return = False
	if doc.voucher_type in ["Sales Invoice", "Purchase Invoice"]:
		is_return = voucher.is_return  # Case Debit/Credit Note
	if doc.voucher_type == "Journal Entry":
		is_return = voucher.reversal_of and True or False
	sign = is_return and -1 or 1
	# Tax amount, use Dr/Cr to ensure it support every case
	if doc.account in [setting.sales_tax_account, setting.purchase_tax_account]:
		tax_amount = doc.credit - doc.debit
		if (tax_amount > 0 and not is_return) or (tax_amount < 0 and is_return):
			doctype = "Sales Tax Invoice"
		if (tax_amount < 0 and not is_return) or (tax_amount > 0 and is_return):
			doctype = "Purchase Tax Invoice"
		tax_amount = abs(tax_amount) * sign
	if doctype:
		if voucher.docstatus == 2:
			tax_amount = 0
		if tax_amount != 0:
			# Base amount, use base amount from origin document
			if voucher.doctype == "Expense Claim":
				if voucher.split_tax_invoice:
					base_amount = sum([x.tax_base_amount for x in voucher.splitted_tax_invoices])
				else:
					base_amount = voucher.base_amount_overwrite or voucher.total_sanctioned_amount
			elif voucher.doctype == "Sales Invoice":
				base_amount = voucher.base_net_total
			elif voucher.doctype == "Purchase Invoice":
				if voucher.split_tax_invoice:
					base_amount = sum([x.tax_base_amount for x in voucher.splitted_tax_invoices])
				else:
					base_amount = voucher.base_net_total
			elif voucher.doctype == "Payment Entry":
				base_amount = voucher.tax_base_amount
			elif voucher.doctype == "Journal Entry":
				# If clear_undue_tax is not checked, return
				if not voucher.create_tax_invoice:
					return
				# For Journal Entry, use Tax Invoice Detail table as voucher
				voucher = frappe.get_doc("Journal Entry Tax Invoice Detail", doc.voucher_detail_no)
				base_amount = voucher.tax_base_amount
			base_amount = abs(base_amount) * sign
			# Validate base amount
			tax_rate = frappe.get_cached_value("Account", doc.account, "tax_rate")
			if abs((base_amount * tax_rate / 100) - tax_amount) > 0.1:
				frappe.throw(
					_(
         				"Tax should be {}% of the base amount<br/>"
					  	"<b>Note:</b> To correct base amount, fill in Tax Base Amount.".format(tax_rate)
					)
				)
			if voucher.get("split_tax_invoice", False):
				# Use Split Tax Invoice Table
				tinvs = create_tax_invoice(doc, doctype, base_amount, tax_amount, voucher, True)
				validate_splitted_tax_invoices(voucher, setting.purchase_tax_account)
				for tinv in tinvs:
					tinv = update_voucher_tinv(doctype, voucher, tinv, True)
					tinv.submit()
			else:
				[tinv] = create_tax_invoice(doc, doctype, base_amount, tax_amount, voucher)
				tinv = update_voucher_tinv(doctype, voucher, tinv)
				tinv.submit()


def validate_splitted_tax_invoices(voucher, tax_account):
	tax_amount = 0
	for tax in voucher.taxes:
		if tax.account_head == tax_account:
			tax_amount += tax.get("base_tax_amount") or tax.tax_amount
	splitted_tax_amount = 0
	for tax in voucher.splitted_tax_invoices:
		splitted_tax_amount += tax.tax_amount
	# Check if tax amount in 2 tables are equal
	if abs(tax_amount - splitted_tax_amount) > 0.1:
		frappe.throw(
			_(
				"Document Tax amount and Splitted Tax Invoice are not equal<br/>"
				"- Tax amount in Tax Invoice: {0}<br/>"
				"- Tax amount in Splitted Tax Invoice: {1}"
			).format(tax_amount, splitted_tax_amount)
		)


def create_tax_invoice(doc, doctype, base_amount, tax_amount, voucher, split_tax_invoice=False):
	tinv_dict = {}
	# For sales invoice / purchase invoice / payment and journal entry, we can get the party from GL
	gl = frappe.db.get_all(
		"GL Entry",
		filters={
			"voucher_type": doc.voucher_type,
			"voucher_no": doc.voucher_no,
			"party": ["!=", ""],
		},
		fields=["party", "party_type"],
	)
	party = gl and gl[0].get("party")
	if doc.voucher_type == "Journal Entry":
		if doctype == "Sales Tax Invoice":
			party = voucher.customer or party
			if not party:
				frappe.throw(
					_(
						"<b>Customer is required for Sales Tax Invoice!</b><br/>"
						"Please edit accounting entry with Tax account and choose <b>Customer</b> under Overwrite Tax invoice section."
					)
				)
		if doctype == "Purchase Tax Invoice":
			party = voucher.supplier or party
			if not party:
				frappe.throw(
					_(
						"<b>Supplier is required for Purchase Tax Invoice!</b><br/>"
						"Please edit accounting entry with Tax account and choose <b>Supplier</b> under Overwrite Tax invoice section."
					)
				)
		je = frappe.get_doc(doc.voucher_type, doc.voucher_no)
		if je.for_payment:
			tinv_dict.update(
				{
					"against_voucher_type": "Payment Entry",
					"against_voucher": je.for_payment,
				}
			)
	# Case Payment Entry, party must be of type customer/supplier only
	if doc.voucher_type == "Payment Entry" and doc.party_type == "Employee":
		party = voucher.supplier
	# Case expense claim, partner should be supplier, not employee
	if doc.voucher_type == "Expense Claim" and not voucher.split_tax_invoice:
		party = voucher.supplier
	if not party:
		frappe.throw(_("Please fill in Supplier for Purchase Tax Invoice"))
	# Create Tax Invoice
	tinv_dict.update(
		{
			"doctype": doctype,
			"company": doc.company,
			"gl_entry": doc.name,
			"tax_amount": tax_amount,
			"tax_base": base_amount,
			"party": party,
		}
	)
	if not split_tax_invoice:
		tinv = frappe.get_doc(tinv_dict)
		tinv.insert(ignore_permissions=True)
		return [tinv]
	else:
		tinvs = []
		for tax in voucher.splitted_tax_invoices:
			if tax.tax_amount > 0:
				tinv_dict.update(
					{
						"party": tax.supplier,
						"tax_amount": tax.tax_amount,
						"tax_base": tax.tax_base_amount,
						"number": tax.tax_invoice_number,
						"date": tax.tax_invoice_date,
						"report_date": tax.tax_invoice_date,
						"splitted_tax_invoice": tax.name
					}
				)
				tinvs.append(frappe.get_doc(tinv_dict).insert(ignore_permissions=True))
		return tinvs


def update_voucher_tinv(doctype, voucher, tinv, split_tax_invoice=False):
	# Set company tax address
	def update_company_tax_address(voucher, tinv):
		# From Sales Invoice and Purchase Invoice, use voucher address
		if tinv.voucher_type == "Sales Invoice":
			tinv.company_tax_address = voucher.company_address
		elif tinv.voucher_type == "Purchase Invoice":
			tinv.company_tax_address = voucher.billing_address
		else:  # From Payment Entry, Expense Claim and Journal Entry
			tinv.company_tax_address = voucher.company_tax_address
		if not tinv.company_tax_address:
			frappe.throw(_("No Company Billing/Tax Address"))

	update_company_tax_address(voucher, tinv)
 
	# Use data in tax detail table
	if split_tax_invoice:
		return tinv

	# Sales Invoice - use Sales Tax Invoice as Tax Invoice
	# Purchase Invoice - use Bill No as Tax Invoice
	if doctype == "Sales Tax Invoice":
		voucher.tax_invoice_number = tinv.name
		voucher.tax_invoice_date = tinv.date
		tinv.report_date = tinv.date
	if doctype == "Purchase Tax Invoice":
		if not (voucher.tax_invoice_number and voucher.tax_invoice_date):
			frappe.throw(_("Please enter Tax Invoice Number / Tax Invoice Date"))
		voucher.save()
		tinv.number = voucher.tax_invoice_number
		tinv.report_date = tinv.date = voucher.tax_invoice_date
	voucher.save()
	tinv.save()
	return tinv


def validate_company_address(doc, method):
	if not doc.company_tax_address:
		addresses = frappe.db.get_all(
			"Address",
			filters={"is_your_company_address": 1, "address_type": "Billing"},
			fields=["name", "address_type"],
		)
		if len(addresses) == 1:
			doc.company_tax_address = addresses[0]["name"]


def validate_tax_invoice(doc, method):
	# If taxes contain tax account, tax invoice is required.
	setting = get_thai_tax_settings(doc.company)
	tax_account = setting.purchase_tax_account
	voucher = frappe.get_doc(doc.doctype, doc.name)
	has_vat = False
	for tax in voucher.taxes:
		if tax.account_head == tax_account:
			has_vat = True
			break
	if not doc.split_tax_invoice:
		if has_vat and not doc.tax_invoice_number:
			frappe.throw(_("This document require Tax Invoice Number"))
		if not has_vat and doc.tax_invoice_number:
			frappe.throw(_("This document has no due VAT, please remove Tax Invoice Number"))
	else:
		if has_vat and not doc.splitted_tax_invoices:
			frappe.throw(_("This document require Tax Invoice Number(s)"))
		if not has_vat and doc.splitted_tax_invoices:
			frappe.throw(_("This document has no due VAT, please remove Tax Invoice Number(s)"))


@frappe.whitelist()
def to_clear_undue_tax(dt, dn):
	if is_tax_invoice_exists(dt, dn):
		return False
	if not make_clear_vat_journal_entry(dt, dn):
		return False
	return True


def is_tax_invoice_exists(dt, dn):
	doc = frappe.get_doc(dt, dn)
	ptax = frappe.get_all(
		"Purchase Tax Invoice",
		or_filters={"voucher_no": doc.name, "against_voucher": doc.name},
		pluck="name",
	)
	return True if ptax else False


@frappe.whitelist()
def make_clear_vat_journal_entry(dt, dn):
	doc = frappe.get_doc(dt, dn)
	tax = get_thai_tax_settings(doc.company)
	je = frappe.new_doc("Journal Entry")
	je.entry_type = "Journal Entry"
	je.create_tax_invoice = 1
	je.supplier = doc.party_type == "Supplier" and doc.party or False
	je.company_tax_address = doc.company_tax_address
	je.for_payment = doc.name
	je.user_remark = _("Clear Undue Tax on %s" % doc.name)
	# Loop through all paid doc, pick only ones with Undue Tax
	base_total = 0
	tax_total = 0
	references = filter(
		lambda x: x.reference_doctype in ("Purchase Invoice", "Expense Claim"), doc.references
	)
	for ref in references:
		if not ref.allocated_amount or not ref.total_amount:
			continue
		# Find gl entry of ref doc that has undue amount
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={
				"voucher_type": ref.reference_doctype,
				"voucher_no": ref.reference_name,
			},
			fields=["*"],
		)
		for gl in gl_entries:
			(undue_tax, base_amount, account_undue, account) = get_undue_tax(doc, ref, gl, tax)
			if ref.reference_doctype in ("Purchase Invoice", "Expense Claim"):
				undue_tax = -undue_tax
				base_amount = -base_amount
			base_total += base_amount
			if undue_tax:
				je.append(
					"accounts",
					{
						"account": account_undue,
						"credit_in_account_currency": undue_tax > 0 and undue_tax,
						"debit_in_account_currency": undue_tax < 0 and abs(undue_tax),
						"tax_base_amount": base_total,
					},
				)
				tax_total += undue_tax
	if not tax_total:
		return False
	# To due tax
	je.append(
		"accounts",
		{
			"account": account,
			"credit_in_account_currency": tax_total < 0 and abs(tax_total),
			"debit_in_account_currency": tax_total > 0 and tax_total,
		},
	)
	return je


def clear_invoice_undue_tax(doc, method):
	old_doc = doc.get_doc_before_save()
	if (
		old_doc
		and old_doc.total_allocated_amount == doc.total_allocated_amount
		and old_doc.has_purchase_tax_invoice == doc.has_purchase_tax_invoice
	):
		return
	doc.taxes = []
	tax = get_thai_tax_settings(doc.company)
	base_total = 0
	tax_total = 0
	references = filter(
		lambda x: x.reference_doctype
		in ("Sales Invoice", "Purchase Invoice", "Expense Claim"),
		doc.references,
	)
	for ref in references:
		if (
			ref.reference_doctype in ("Purchase Invoice", "Expense Claim")
			and not doc.has_purchase_tax_invoice
		):
			return
		if not ref.allocated_amount or not ref.total_amount:
			continue
		# Find gl entry of ref doc that has undue amount
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={
				"voucher_type": ref.reference_doctype,
				"voucher_no": ref.reference_name,
			},
			fields=["*"],
		)
		for gl in gl_entries:
			(undue_tax, base_amount, account_undue, account) = get_undue_tax(doc, ref, gl, tax)
			if ref.reference_doctype in ("Purchase Invoice", "Expense Claim"):
				undue_tax = -undue_tax
				base_amount = -base_amount
			base_total += base_amount
			if undue_tax:
				doc.append(
					"taxes",
					{
						# 'add_deduct_tax': undue_tax > 0 and 'Deduct' or 'Add',
						"add_deduct_tax": "Add",
						"description": "Clear Undue Tax",
						"charge_type": "Actual",
						"account_head": account_undue,
						"tax_amount": -undue_tax,
					},
				)
				tax_total += undue_tax
	if not tax_total:
		if doc.has_purchase_tax_invoice:
			frappe.throw(
				_("No undue tax amount to clear. Please uncheck 'Has Purchase Tax Invoice'")
			)
		return
	# To due tax
	doc.append(
		"taxes",
		{
			# 'add_deduct_tax': tax_total > 0 and 'Add' or 'Deduct',
			"add_deduct_tax": "Add",
			"description": "Clear Undue Tax",
			"charge_type": "Actual",
			"account_head": account,
			"tax_amount": tax_total,
		},
	)
	doc.tax_base_amount = base_total
	doc.calculate_taxes()
	doc.save()


def get_undue_tax(doc, ref, gl, tax):
	# Prepration
	undue_tax = 0
	base_amount = 0
	tax_account_undue = tax.sales_tax_account_undue
	tax_account = tax.sales_tax_account
	if ref.reference_doctype in ("Purchase Invoice", "Expense Claim"):
		tax_account_undue = tax.purchase_tax_account_undue
		tax_account = tax.purchase_tax_account
	credit = gl["credit"]
	debit = gl["debit"]
	alloc_percent = ref.allocated_amount / ref.total_amount
	# Find Base
	report_type = frappe.get_cached_value("Account", gl["account"], "report_type")
	if report_type == "Profit and Loss":
		base_amount = alloc_percent * (credit - debit)
	# Find Tax
	if gl["account"] == tax_account_undue:
		undue_tax = alloc_percent * (credit - debit)
		# kittiu: For now, as residual from bs_reconcile is not stable, do not use.
		# undue_remain = get_uncleared_tax_amount(gl, doc.payment_type)
		# if not undue_remain:
		# 	undue_tax = 0
		# else:
		# 	undue_tax = undue_tax if undue_tax < undue_remain else undue_remain
		# --
	return (undue_tax, base_amount, tax_account_undue, tax_account)

# kittiu: For now, as residual from bs_reconcile is not stable, do not use.
# def get_uncleared_tax_amount(gl, payment_type):
# 	# If module bs_reconcile is installed, uncleared_tax = residual amount
# 	# else uncleared_tax is the debit - credit amount
# 	uncleared_tax = gl.debit - gl.credit
# 	if gl.get("is_reconcile"):
# 		uncleared_tax = gl.get("residual")
# 	if payment_type == "Receive":
# 		uncleared_tax = -uncleared_tax
# 	return uncleared_tax
# --

def is_tax_reset(doc, tax_accounts):
	# For new doc, or has tax changes, do the reset
	if doc.docstatus != 0:
		return False
	old_doc = doc.get_doc_before_save()
	if old_doc:
		old_tax_lines = list(filter(lambda l: l.account in tax_accounts, old_doc.accounts))
		new_tax_lines = list(filter(lambda l: l.account in tax_accounts, doc.accounts))
		if len(old_tax_lines) != len(new_tax_lines):
			return True
		else:
			for tax_line in list(zip(old_tax_lines, new_tax_lines)):
				old_line = tax_line[0]
				new_line = tax_line[1]
				if (
					old_line.tax_base_amount != new_line.tax_base_amount
					or old_line.debit != new_line.debit
					or old_line.credit != new_line.credit
					or old_line.supplier != new_line.supplier
					or old_line.customer != new_line.customer
					or old_line.tax_invoice_number != new_line.tax_invoice_number
					or str(old_line.tax_invoice_date) != str(new_line.tax_invoice_date)
				):
					return True
	else:
		return True
	return False


def prepare_journal_entry_tax_invoice_detail(doc, method):
	setting = get_thai_tax_settings(doc.company)
	tax_accounts = [setting.sales_tax_account, setting.purchase_tax_account]
	precision = get_field_precision(
		frappe.get_meta("Journal Entry Tax Invoice Detail").get_field("tax_base_amount")
	)
	# Reset Tax Invoice Table
	reset_tax = is_tax_reset(doc, tax_accounts)
	if reset_tax:
		for d in doc.tax_invoice_details:
			d.delete()
		tinv_idx = 1
		for tax_line in filter(lambda l: l.account in tax_accounts, doc.accounts):
			tax_rate = frappe.get_cached_value("Account", tax_line.account, "tax_rate")
			tax_amount = abs(tax_line.debit - tax_line.credit)
			tax_base_amount = tax_line.tax_base_amount or (
				tax_rate > 0 and tax_amount * 100 / tax_rate or 0
			)
			company_tax_address = doc.company_tax_address
			if not company_tax_address:
				addrs = frappe.get_all("Address", {"is_your_company_address": 1}, pluck="name")
				company_tax_address = len(addrs) == 1 and addrs[0] or ""
			party_name = ""
			if tax_line.customer:
				party_name = frappe.get_doc("Customer", tax_line.customer).customer_name
			if tax_line.supplier:
				party_name = frappe.get_doc("Supplier", tax_line.supplier).supplier_name
			tinv_detail = frappe.get_doc(
				{
					"doctype": "Journal Entry Tax Invoice Detail",
					"parenttype": "Journal Entry",
					"parentfield": "tax_invoice_details",
					"parent": doc.name,
					"idx": tinv_idx,
					"company_tax_address": company_tax_address,
					"supplier": tax_line.supplier,
					"customer": tax_line.customer,
					"party_name": party_name,
					"tax_invoice_number": tax_line.tax_invoice_number,
					"tax_invoice_date": tax_line.tax_invoice_date,
					"tax_base_amount": flt(tax_base_amount, precision),
					"tax_amount": flt(tax_amount, precision),
				}
			)
			tax_line.reference_detail_no = tinv_detail.insert().name
			tax_line.save()
			tinv_idx += 1
		doc.reload()


# Zero Tax Invoice for Sales Ivoice
def create_sales_tax_invoice_on_zero_tax(doc, method):
    """ This method is used for Sales Invoice only """
    if doc.flags.from_repost:
        return
    if doc.doctype != "Sales Invoice":
        return
    setting = get_thai_tax_settings(doc.company)
    if not setting.create_sales_taxinv_on_zero_tax:
        return
    doctype = "Sales Tax Invoice"
    zero_taxes = list(filter(lambda t: (
    t.account_head == setting.sales_tax_account
    and t.tax_amount == 0
	), doc.taxes))
    base_amount = sum(tax.base_total for tax in zero_taxes)
    if base_amount:
        tinv = create_sales_tax_invoice_zero_tax(doc, doctype, base_amount, zero_taxes[0].account_head)
        tinv = update_voucher_tinv(doctype, doc, tinv)
        tinv.submit()


def create_sales_tax_invoice_zero_tax(doc, doctype, base_amount, account):
    tinv_dict = {
        "date": doc.posting_date,
        "doctype": doctype,
        "tax_amount": 0,
        "tax_base": base_amount,
        "party": doc.customer,
        "voucher_type": doc.doctype,
        "voucher_no": doc.name,
        "account": account,
    }
    tinv = frappe.get_doc(tinv_dict)
    tinv.insert(ignore_permissions=True)
    return tinv


def cancel_related_tax_invoice(doc, method):
	doctypes = ["Sales Tax Invoice", "Purchase Tax Invoice"]
	for doctype in doctypes:
		tinv = frappe.get_all(doctype, filters={
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
			"docstatus": ("!=", 2),
		}, pluck="name")
		if tinv:
			tinv = frappe.get_doc(doctype, tinv[0])
			tinv.cancel()
