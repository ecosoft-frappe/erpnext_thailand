from .payment_entry import reconcile_undue_tax_gls


def unreconcile_undue_tax(doc, method):
	"""If bs_reconcile is installed, unreconcile undue tax gls"""
	vouchers = [doc.voucher_no] + [r.reference_name for r in doc.allocations]
	reconcile_undue_tax_gls(vouchers, doc.company, unreconcile=True)
