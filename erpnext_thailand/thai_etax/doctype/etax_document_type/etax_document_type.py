# Copyright (c) 2026, Ecosoft and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class eTaxDocumentType(Document):
	def validate(self):
		if self.template_source == "ERPNext":
			self.server_print_format = None
		else:
			self.print_format = None
