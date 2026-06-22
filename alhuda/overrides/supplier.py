import frappe
from frappe import _

RESTRICTED_COMPANY = "AL-HUDA INTERNATIONAL WELFARE FOUNDATION"


def validate_duplicate_supplier(doc, method=None):
	"""Block saving a Supplier (beneficiary case) if another Supplier already
	exists for the same CNIC No, Project and Approved Amount, whose Periodicity
	Date Range (From Date/To Date) overlaps with this one's.

	Only enforced for AL-HUDA INTERNATIONAL WELFARE FOUNDATION.
	"""
	if doc.custom_company != RESTRICTED_COMPANY:
		return

	if not (
		doc.custom_cnic_no
		and doc.project
		and doc.custom_from_date
		and doc.custom_to_date
		and doc.custom_approved_amount
	):
		return

	# Two date ranges overlap when one starts before the other ends, in both directions.
	duplicate = frappe.db.sql(
		"""
		select name from `tabSupplier`
		where name != %(name)s
			and custom_cnic_no = %(cnic_no)s
			and project = %(project)s
			and custom_approved_amount = %(approved_amount)s
			and custom_company = %(company)s
			and custom_from_date <= %(to_date)s
			and custom_to_date >= %(from_date)s
		limit 1
		""",
		{
			"name": doc.name,
			"cnic_no": doc.custom_cnic_no,
			"project": doc.project,
			"approved_amount": doc.custom_approved_amount,
			"company": RESTRICTED_COMPANY,
			"from_date": doc.custom_from_date,
			"to_date": doc.custom_to_date,
		},
	)

	if duplicate:
		frappe.throw(
			_(
				"Supplier already exists with the same CNIC No, Project and Approved "
				"Amount, with an overlapping Periodicity Date Range: {0}"
			).format(frappe.utils.get_link_to_form("Supplier", duplicate[0][0])),
			title=_("Duplicate Supplier"),
		)
