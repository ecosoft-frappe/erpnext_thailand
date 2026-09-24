# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr


class WithholdingTaxType(Document):
	def get_account(self, company):
		account = list(filter(lambda x: x.company == company, self.accounts))
		return account and account[0].account or None
