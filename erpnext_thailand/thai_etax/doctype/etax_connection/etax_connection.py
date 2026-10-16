# Copyright (c) 2026, Ecosoft and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class eTaxConnection(Document):
	def validate(self):
		self.server_url = (self.server_url or "").strip().rstrip("/")
		if not self.server_url.startswith(("http://", "https://")):
			frappe.throw(_("Server URL must be a valid HTTP or HTTPS URL."))
		if not 0 <= (self.replacement_lock_day or 0) <= 31:
			frappe.throw(_("Replacement Lock Day must be between 0 and 31."))
