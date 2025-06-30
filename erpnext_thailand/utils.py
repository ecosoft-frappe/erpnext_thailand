import datetime
import csv
import frappe
from frappe import _
from num2words import num2words
import requests
from lxml import etree


def amount_in_bahttext(amount):
	return num2words(amount, to="currency", lang="th")


def amount_to_text(amount, currency=None, lang=None):
    try:
        currency = currency or frappe.defaults.get_global_default("currency")
        lang = lang or ("th" if currency == "THB" else "en")
        return num2words(amount, to="currency", lang=lang, currency=currency).title()
    except:
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


@frappe.whitelist()
def get_address_by_tax_id(tax_id=False, branch=False):
	"""Get address information from Revenue Department Web Service by Tax ID and Branch number.

	Args:
		tax_id (str): Tax ID of the company
		branch (str): Branch number of the company

	Returns:
		dict: Dictionary containing address information
			  Empty dict if there's an error

	Raises:
		frappe.ValidationError: If tax_id or branch is not provided
	"""
	if not (tax_id and branch):
		frappe.throw(_('Please provide both Tax ID and Branch number'))

	# API Configuration
	url = "https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx"
	querystring = {"wsdl": ""}
	headers = {"content-type": "application/soap+xml; charset=utf-8"}

	# Convert branch number, default to "0" if not numeric
	branch_number = int(branch if branch.isnumeric() else "0")

	# Prepare SOAP payload
	payload = (
		'<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
		'xmlns:vat="https://rdws.rd.go.th/serviceRD3/vatserviceRD3">'
		'<soap:Header/>'
		'<soap:Body>'
		'<vat:Service>'
		'<vat:username>anonymous</vat:username>'
		'<vat:password>anonymous</vat:password>'
		f'<vat:TIN>{tax_id}</vat:TIN>'
		'<vat:Name></vat:Name>'
		'<vat:ProvinceCode>0</vat:ProvinceCode>'
		f'<vat:BranchNumber>{branch_number}</vat:BranchNumber>'
		'<vat:AmphurCode>0</vat:AmphurCode>'
		'</vat:Service>'
		'</soap:Body>'
		'</soap:Envelope>'
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

	map = {
		"vBuildingName": "อาคาร",
		"vFloorNumber": "ชั้น",
		"vVillageName": "หมู่บ้าน",
		"vRoomNumber": "ห้อง",
		# "vHouseNumber": "เลขที่",
		"vMooNumber": "หมู่ที่",
		"vSoiName": "ซอย",
		"vStreetName": "ถนน",
		"vThambol": "ต.",
		"vAmphur": "อ.",
		"vProvince": "จ.",
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

	if province == "จ.กรุงเทพมหานคร":
		thambon = data.get("vThambol") and f"แขวง{data['vThambol']}" or ""
		amphur = data.get("vAmphur") and f"เขต{data['vAmphur']}" or ""
		province = data.get("vProvince") and f"{data['vProvince']}" or ""

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
	with open(file_path, mode="r", encoding="utf-8") as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			if frappe.db.exists("Thai Zip Code", row["ID"]):
				continue
			doc = frappe.get_doc({
				"doctype": "Thai Zip Code",
				"name": row["ID"],
				"zip_code": row["Zip Code"],
				"tambon": row["Tambon"],
				"amphur": row["Amphur"],
				"province": row["Province"],
			})
			doc.insert(ignore_permissions=True)
			frappe.db.commit()
	return "Import completed successfully."


@frappe.whitelist()
def get_location_by_zip_code(zip_code):
	locations = frappe.get_all("Thai Zip Code", filters={"zip_code": zip_code}, fields=["name", "zip_code", "tambon", "amphur", "province"])
	return [
		{
			'id': loc['name'],
			'zip_code': loc['zip_code'],
			'tambon': loc['tambon'],
			'amphur': loc['amphur'],
			'province': loc['province']
		}
		for loc in locations
	]
