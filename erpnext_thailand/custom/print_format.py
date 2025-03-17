import json
from io import BytesIO
from pypdf import PdfWriter

import frappe
from frappe.utils.safe_exec import get_safe_globals


@frappe.whitelist()
def get_print_formats(doctype, docname):
	# Fetch available print formats for the given doctype
	print_formats = frappe.get_all(
		"Print Format", filters={
      		"doc_type": doctype,
        	"disabled": 0},
  		pluck="name",
		order_by="name"
	)
	default_formats = []
	doc = frappe.get_doc(doctype, docname)
	# Filter out print formats that are not default
	final_print_formats = print_formats.copy()
	for print_format in print_formats:
		pf = frappe.get_cached_doc("Print Format", print_format)
		if is_default_print_format(doc, pf):
			default_formats.append(print_format)
		elif pf.hide_if_not_default:
			final_print_formats.remove(print_format)
	# Only if there is 1 default, set it
	default_format = len(default_formats) == 1 and default_formats[0] or ""
	return {
		"print_formats": final_print_formats,
		"default_format": default_format,
	}


def is_default_print_format(doc, print_format):
	is_default = frappe.safe_eval(
		code=print_format.default_condition or "False",
		eval_globals=get_safe_globals(),
		eval_locals={"doc": doc},
	)
	return is_default


def allow_update_standard(doc, method):
	if doc.standard == "Yes":
		prev_doc = doc.get_doc_before_save()
		if prev_doc and (
      			prev_doc.default_condition != doc.default_condition or
      			prev_doc.hide_if_not_default != doc.hide_if_not_default
         	):
			frappe.flags.in_test = 1


@frappe.whitelist()
def download_print_pdf(
	doctype: str | None = None,
	name: str | None = None,
	format: str | None = None,
	# no_letterhead: bool = False,  # For future impl.
	# letterhead: str | None = None,  # For future impl.
	# options: str | None = None,  # For future impl.
):
	""" Inspired by _download_multi_pdf(), but used to generate multiple copies """
	pdf_writer = PdfWriter()

	# Concatenating pdf files
	pf = frappe.get_cached_doc("Print Format", format)
	copies = (pf.add_copies and int(pf.add_copies) or 0) + 1
	for idx in range(copies):
		doc = frappe.get_doc(doctype, name)
		doc.copy = idx  # Pass the number of copy to jinja
		pdf_writer = frappe.get_print(
			doctype,
			name,
			format,
			as_pdf=True,
			output=pdf_writer,
			doc=doc,
			# no_letterhead=no_letterhead,  # For future impl.
			# letterhead=letterhead,  # For future impl.
			# pdf_options=options,  # For future impl.
		)

	with BytesIO() as merged_pdf:
		pdf_writer.write(merged_pdf)
		frappe.local.response.filecontent = merged_pdf.getvalue()
		frappe.local.response.filename = f"{name}.pdf"
		frappe.local.response.type = "pdf"
