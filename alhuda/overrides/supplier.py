import frappe
from frappe import _

RESTRICTED_COMPANY = "AL-HUDA INTERNATIONAL WELFARE FOUNDATION"


def validate_duplicate_supplier(doc, method=None):
	"""Block saving a Supplier (beneficiary case) if another Supplier already
	exists for the same Supplier Name and CNIC No, with the same Project,
	Periodicity Date Range (From Date/To Date) and Approved Amount.

	Only enforced for AL-HUDA INTERNATIONAL WELFARE FOUNDATION.
	"""
	if doc.custom_company != RESTRICTED_COMPANY:
		return

	if not (
		doc.supplier_name
		and doc.custom_cnic_no
		and doc.project
		and doc.custom_from_date
		and doc.custom_to_date
		and doc.custom_approved_amount
	):
		return

	duplicate = frappe.db.get_value(
		"Supplier",
		{
			"name": ["!=", doc.name],			
			"custom_cnic_no": doc.custom_cnic_no,
			"project": doc.project,
			"custom_from_date": doc.custom_from_date,
			"custom_to_date": doc.custom_to_date,
			"custom_approved_amount": doc.custom_approved_amount,
			"custom_company": RESTRICTED_COMPANY,
		},
		"name",
	)

	if duplicate:
		frappe.throw(
			_(
				"Supplier already exists with the same detail (CNIC No, "
				"Project, Periodicity Date Range and Approved Amount): {0}"
			).format(frappe.utils.get_link_to_form("Supplier", duplicate)),
			title=_("Duplicate Supplier"),
		)
