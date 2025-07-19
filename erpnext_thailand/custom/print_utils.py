import frappe


def add_comment_on_print_pdf(form_dict):
	""" On PDF printout, if the print format is set to add commit, do it"""
	if form_dict.format:
		add_comment = frappe.get_value(
			"Print Format", form_dict.format, "add_comment_info")
		if add_comment:
			if form_dict.doctype and form_dict.name:
				doc = frappe.get_doc(form_dict.doctype, form_dict.name)
				doc.add_comment(
					comment_type="Info",
					text="Printed: {}".format(form_dict.format),
				)
				frappe.db.commit()
