import frappe


def add_comment_on_print_pdf(doctype, name, print_format):
	""" On PDF printout, if the print format is set to add commit, do it """
	if print_format:
		add_comment = frappe.get_value(
			"Print Format", print_format, "add_comment_info")
		if add_comment:
			if doctype and name:
				doc = frappe.get_doc(doctype, name)
				doc.add_comment(
					comment_type="Info",
					text="Printed: {}".format(print_format),
				)
				frappe.db.commit()
