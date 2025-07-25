__version__ = "1.0.1"

# Monkey patching
# ------------------
import erpnext.accounts.doctype.gl_entry.gl_entry as gl_entry

import erpnext_thailand.custom.gl_entry as patch

gl_entry.rename_temporarily_named_docs = patch.rename_temporarily_named_docs

import frappe as frappe

import erpnext_thailand.custom.print_utils as patch_print_utils

frappe.get_print = patch_print_utils.get_print
