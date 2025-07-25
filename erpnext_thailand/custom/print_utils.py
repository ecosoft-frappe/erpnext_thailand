import frappe
from frappe import get_print as original_get_print
from typing import Literal

def get_print(
	doctype=None,
	name=None,
	print_format=None,
	style=None,
	as_pdf=False,
	doc=None,
	output=None,
	no_letterhead=0,
	password=None,
	pdf_options=None,
	letterhead=None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
):	
	res = original_get_print(
		doctype=doctype,
		name=name,
		print_format=print_format,
		style=style,
		as_pdf=as_pdf,
		doc=doc,
		output=output,
		no_letterhead=no_letterhead,
		password=password,
		pdf_options=pdf_options,
		letterhead=letterhead,
		pdf_generator=pdf_generator,
	)
	if doc and print_format:
		add_comment = frappe.get_value(
			"Print Format", print_format, "add_comment_info")
		if add_comment:
			doc.add_comment(
				comment_type="Info",
				text="Printed: {}".format(print_format),
			)
			frappe.db.commit()
	return res
