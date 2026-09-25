import csv
import datetime
import re

import frappe
import requests
from frappe import _
from lxml import etree
from num2words import num2words
from frappe.defaults import get_user_default_as_list


def amount_in_bahttext(amount):
	return num2words(amount, to="currency", lang="th")


def amount_to_text(amount, currency=None, lang=None):
	try:
		currency = currency or frappe.defaults.get_global_default("currency")
		lang = lang or ("th" if currency == "THB" else "en")
		return num2words(amount, to="currency", lang=lang, currency=currency).title()
	except Exception:
		return ""


def full_thai_date(date_str):
	if not date_str:
		return ""
	date = datetime.datetime.strptime(str(date_str), "%Y-%m-%d")
	month_name = "x มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม".split()[
		date.month
	]
	thai_year = date.year + 543
	return f"{date.day} {month_name} {thai_year}"  # 30 ตุลาคม 2560


def get_prefix_for_address(data):
	prefix_thambol, prefix_amphur, prefix_province = "", "", ""
	companies = get_user_default_as_list("company", frappe.session.user)
	company = (
		companies[0]
		if companies
		else frappe.db.get_single_value("Global Defaults", "default_company")
	)
	company_doc = frappe.get_cached_doc("Company", company)
	if company_doc.enable_prefix_for_address:
		prefix_thambol = company_doc.prefix_thambol_other_province or ""
		prefix_amphur = company_doc.prefix_amphur_other_province or ""
		prefix_province = company_doc.prefix_province_other_province or ""
		if "กรุงเทพมหานคร" in [data.get("vProvince", ""), data.get("province", "")]:
			prefix_thambol = company_doc.prefix_thambol_bangkok or ""
			prefix_amphur = company_doc.prefix_amphur_bangkok or ""
			prefix_province = company_doc.prefix_province_bangkok or ""
	return prefix_thambol, prefix_amphur, prefix_province


@frappe.whitelist()
def get_address_by_tax_id(tax_id: str | None = None, branch: str | None = None):
	"""Get address information from Revenue Department Web Service by Tax ID and Branch number.

	Args:
	        tax_id (str): Tax ID of the company
	        branch (str): Branch number of the company

	Returns:
	        dict: Dictionary containing address information
	                  Empty dict if there's an error

	Raises:
	        frappe.ValidationError: If tax_id or branch is not provided, or tax_id is not 13 digits
	"""
	if not (tax_id and branch):
		frappe.throw(_("Please provide both Tax ID and Branch number"))
	# tax_id is put into the SOAP payload as is, so allow only a 13-digit Thai Tax ID
	tax_id = re.sub(r"[\s-]", "", tax_id)
	if not re.fullmatch(r"[0-9]{13}", tax_id):
		frappe.throw(_("Tax ID must be 13 digits"))

	# API Configuration
	url = "https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx"
	querystring = {"wsdl": ""}
	headers = {"content-type": "application/soap+xml; charset=utf-8"}

	# Convert branch number, default to "0" if not numeric
	branch_number = int(branch if branch.isnumeric() else "0")

	# Prepare SOAP payload
	payload = (
		"<soap:Envelope xmlns:soap='http://www.w3.org/2003/05/soap-envelope' "
		"xmlns:vat='https://rdws.rd.go.th/serviceRD3/vatserviceRD3'>"
		"<soap:Header/>"
		"<soap:Body>"
		"<vat:Service>"
		"<vat:username>anonymous</vat:username>"
		"<vat:password>anonymous</vat:password>"
		f"<vat:TIN>{tax_id}</vat:TIN>"
		"<vat:Name></vat:Name>"
		"<vat:ProvinceCode>0</vat:ProvinceCode>"
		f"<vat:BranchNumber>{branch_number}</vat:BranchNumber>"
		"<vat:AmphurCode>0</vat:AmphurCode>"
		"</vat:Service>"
		"</soap:Body>"
		"</soap:Envelope>"
	)

	# Setup session with SSL verification disabled
	session = requests.Session()
	session.verify = False

	# Make the API request
	response = session.post(url, data=payload, headers=headers, params=querystring)
	response.raise_for_status()  # Raise exception for HTTP errors

	# Parse XML response
	result = etree.fromstring(response.content)
	# Process response data
	data = {}
	value = False
	for element in result.iter():
		tag = etree.QName(element).localname
		if not value and tag[:1] == "v":
			value = tag
			continue
		if value and tag == "anyType":
			data[value] = element.text.strip()
		value = False

	if data.get("vmsgerr"):
		frappe.throw(data.get("vmsgerr"))

	return finalize_address_dict(data)


def finalize_address_dict(data):
	def get_part(data, key, value):
		return data.get(key, "-") != "-" and value % (map[key], data.get(key)) or ""

	prefix_thambol, prefix_amphur, prefix_province = get_prefix_for_address(data)

	map = {
		"vBuildingName": "อาคาร",
		"vFloorNumber": "ชั้น",
		"vVillageName": "หมู่บ้าน",
		"vRoomNumber": "ห้อง",
		"vMooNumber": "หมู่ที่",
		"vSoiName": "ซอย",
		"vStreetName": "ถนน",
		"vThambol": prefix_thambol,
		"vAmphur": prefix_amphur,
		"vProvince": prefix_province,
	}

	name = f"{data.get('vBranchTitleName')} {data.get('vBranchName')}"
	if "vSurname" in data and data["vSurname"] not in ("-", "", None):
		name = f"{name} {data['vSurname']}"
	house = data.get("vHouseNumber", "")
	village = get_part(data, "vVillageName", "%s %s")
	soi = get_part(data, "vSoiName", "%s %s")
	moo = get_part(data, "vMooNumber", "%s %s")
	building = get_part(data, "vBuildingName", "%s %s")
	floor = get_part(data, "vFloorNumber", "%s %s")
	room = get_part(data, "vRoomNumber", "%s %s")
	street = get_part(data, "vStreetName", "%s%s")
	thambon = get_part(data, "vThambol", "%s%s")
	amphur = get_part(data, "vAmphur", "%s%s")
	province = get_part(data, "vProvince", "%s%s")
	postal = data.get("vPostCode", "")

	address_parts = filter(
		lambda x: x != "", [house, village, soi, moo, building, floor, room, street]
	)
	return {
		"name": name,
		"address_line1": " ".join(address_parts),
		"city": thambon,
		"county": amphur,
		"state": province,
		"pincode": postal,
	}


def import_thai_zip_code_data():
	file_path = f"{frappe.get_app_path('erpnext_thailand')}/public/files/thai_zip_code.csv"
	with open(file_path, encoding="utf-8") as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			values = {
				"zip_code": row["Zip Code"],
				"tambon": row["Tambon"],
				"amphur": row["Amphur"],
				"province": row["Province"],
			}
			# A tambon can have more than one zip code, so the ID alone is not unique.
			# Keep the ID as name for the first one, use "ID-ZipCode" for the others.
			name = row["ID"]
			if frappe.db.get_value("Thai Zip Code", name, "zip_code") not in (
				None,
				row["Zip Code"],
			):
				name = f"{row['ID']}-{row['Zip Code']}"
			if frappe.db.exists("Thai Zip Code", name):
				# Update names that were corrected in the CSV
				frappe.db.set_value("Thai Zip Code", name, values, update_modified=False)
				continue
			doc = frappe.get_doc({"doctype": "Thai Zip Code", "name": name, **values})
			doc.insert(ignore_permissions=True)
		frappe.db.commit()
	return "Import completed successfully."


@frappe.whitelist()
def get_location_by_zip_code(zip_code):
	locations = frappe.get_all(
		"Thai Zip Code",
		filters={"zip_code": zip_code},
		fields=["name", "zip_code", "tambon", "amphur", "province"],
	)
	location_list = []
	for loc in locations:
		prefix_thambol, prefix_amphur, prefix_province = get_prefix_for_address(loc)
		location_list.append(
			{
				"id": loc["name"],
				"zip_code": loc["zip_code"],
				"tambon": "{}{}".format(prefix_thambol, loc["tambon"]),
				"amphur": "{}{}".format(prefix_amphur, loc["amphur"]),
				"province": "{}{}".format(prefix_province, loc["province"]),
			}
		)
	return location_list
