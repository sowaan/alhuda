# Copyright (c) 2026, Al Huda and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})

	# Company, From Date and To Date are marked reqd in the filter UI; on the
	# report's initial auto-run those defaults may not have resolved yet, so
	# return empty data here instead of frappe.throw (which would surface as
	# a stuck error/loading state rather than the normal "set filters" hint).
	if not (filters.company and filters.from_date and filters.to_date):
		return get_columns([], []), []

	salary_slips = get_salary_slips(filters)
	if not salary_slips:
		return get_columns([], []), []

	salary_slip_names = [d.name for d in salary_slips]
	earning_types, deduction_types = get_earning_and_deduction_types(salary_slip_names)
	columns = get_columns(earning_types, deduction_types)

	earning_map = get_component_amount_map(salary_slip_names, "earnings")
	deduction_map = get_component_amount_map(salary_slip_names, "deductions")
	employee_info_map = get_employee_info_map([d.employee for d in salary_slips])

	branch_wise_data = group_by_branch_and_department(
		salary_slips, employee_info_map, earning_map, deduction_map
	)

	data = []
	grand_total = get_zero_totals(earning_types, deduction_types)

	for branch in sorted(branch_wise_data, key=str.lower):
		departments = branch_wise_data[branch]

		# Branch Header Information: total employees and total salary expenditure
		# for the branch, computed up front so it can be shown before the
		# department/employee breakdown.
		branch_total = get_zero_totals(earning_types, deduction_types)
		for rows in departments.values():
			for row in rows:
				add_employee_to_totals(branch_total, row, earning_types, deduction_types)

		data.append(section_row(_("Branch: {0}").format(branch), branch_total, indent=0))

		sr = 0
		for department in sorted(departments, key=str.lower):
			data.append(section_row(_("Department: {0}").format(department), None, indent=1))

			dept_total = get_zero_totals(earning_types, deduction_types)
			for row in departments[department]:
				sr += 1
				data.append(employee_row(sr, row, earning_types, deduction_types))
				add_employee_to_totals(dept_total, row, earning_types, deduction_types)

			data.append(section_row(_("Department Total"), dept_total, indent=1))

		data.append(section_row(_("Branch Total"), branch_total, indent=0))
		merge_totals(grand_total, branch_total)

	data.append(section_row(_("Grand Total"), grand_total, indent=0))

	return columns, data


def get_columns(earning_types, deduction_types):
	columns = [
		{"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 260},
		{"label": _("Sr #"), "fieldname": "sr", "fieldtype": "Int", "width": 60},
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 110,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 140,
		},
		{"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 110},
		{"label": _("SSN"), "fieldname": "ssn", "fieldtype": "Data", "width": 130},
		{"label": _("EOBI Number"), "fieldname": "eobi_number", "fieldtype": "Data", "width": 130},
		{"label": _("No. of Employees"), "fieldname": "no_of_employees", "fieldtype": "Int", "width": 120},
	]

	for earning in earning_types:
		columns.append(
			{"label": earning, "fieldname": frappe.scrub(earning), "fieldtype": "Currency", "width": 120}
		)

	columns.append({"label": _("Gross Pay"), "fieldname": "gross_pay", "fieldtype": "Currency", "width": 130})

	for deduction in deduction_types:
		columns.append(
			{"label": deduction, "fieldname": frappe.scrub(deduction), "fieldtype": "Currency", "width": 120}
		)

	columns.extend(
		[
			{"label": _("Loan Repayment"), "fieldname": "loan_repayment", "fieldtype": "Currency", "width": 130},
			{"label": _("Total Deduction"), "fieldname": "total_deduction", "fieldtype": "Currency", "width": 130},
			{
				"label": _("Payable Salary (Net Pay)"),
				"fieldname": "net_pay",
				"fieldtype": "Currency",
				"width": 150,
			},
		]
	)
	return columns


def get_salary_slips(filters):
	conditions = ["company = %(company)s", "start_date >= %(from_date)s", "end_date <= %(to_date)s"]
	values = {
		"company": filters.company,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.branch:
		conditions.append("branch = %(branch)s")
		values["branch"] = filters.branch

	if filters.department:
		conditions.append("department = %(department)s")
		values["department"] = filters.department

	# Salary Slips with Zero Payable Salary are not filtered out anywhere here,
	# by design, so they still appear in the register.
	docstatus_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
	conditions.append("docstatus = %(docstatus)s")
	values["docstatus"] = docstatus_map.get(filters.docstatus, 1)

	return frappe.db.sql(
		f"""
		select
			name, employee, employee_name, designation, branch, department,
			gross_pay, total_deduction, total_loan_repayment, net_pay
		from `tabSalary Slip`
		where {" and ".join(conditions)}
		""",
		values,
		as_dict=1,
	)


def get_earning_and_deduction_types(salary_slip_names):
	if not salary_slip_names:
		return [], []

	rows = frappe.db.sql(
		"""
		select distinct salary_component, parentfield
		from `tabSalary Detail`
		where parent in %(names)s and amount != 0
		""",
		{"names": salary_slip_names},
		as_dict=1,
	)
	earning_types = sorted({d.salary_component for d in rows if d.parentfield == "earnings"})
	deduction_types = sorted({d.salary_component for d in rows if d.parentfield == "deductions"})
	return earning_types, deduction_types


def get_component_amount_map(salary_slip_names, parentfield):
	if not salary_slip_names:
		return {}

	rows = frappe.db.sql(
		"""
		select parent, salary_component, amount
		from `tabSalary Detail`
		where parent in %(names)s and parentfield = %(parentfield)s
		""",
		{"names": salary_slip_names, "parentfield": parentfield},
		as_dict=1,
	)

	amount_map = {}
	for d in rows:
		amount_map.setdefault(d.parent, {})[d.salary_component] = flt(d.amount)
	return amount_map


def get_employee_info_map(employees):
	if not employees:
		return {}

	rows = frappe.db.get_all(
		"Employee",
		filters={"name": ["in", list(set(employees))]},
		fields=["name", "date_of_joining", "custom_social_security_number", "custom_eobi_number"],
	)
	return {d.name: d for d in rows}


def group_by_branch_and_department(salary_slips, employee_info_map, earning_map, deduction_map):
	grouped = {}

	for ss in salary_slips:
		branch_label = ss.branch or _("No Branch")
		department_label = ss.department or _("No Department")
		employee_info = employee_info_map.get(ss.employee) or frappe._dict()

		row = frappe._dict(
			employee=ss.employee,
			employee_name=ss.employee_name,
			designation=ss.designation,
			date_of_joining=employee_info.date_of_joining,
			ssn=employee_info.custom_social_security_number,
			eobi_number=employee_info.custom_eobi_number,
			earnings=earning_map.get(ss.name, {}),
			deductions=deduction_map.get(ss.name, {}),
			loan_repayment=flt(ss.total_loan_repayment),
			gross_pay=flt(ss.gross_pay),
			total_deduction=flt(ss.total_deduction) + flt(ss.total_loan_repayment),
			net_pay=flt(ss.net_pay),
		)
		grouped.setdefault(branch_label, {}).setdefault(department_label, []).append(row)

	# Sort employees within each department by Date of Joining, oldest first.
	# Employees without a recorded joining date are sorted last rather than erroring.
	for departments in grouped.values():
		for rows in departments.values():
			rows.sort(key=lambda r: (r.date_of_joining or getdate("9999-12-31"), r.employee_name or ""))

	return grouped


def get_zero_totals(earning_types, deduction_types):
	totals = {
		"no_of_employees": 0,
		"gross_pay": 0.0,
		"loan_repayment": 0.0,
		"total_deduction": 0.0,
		"net_pay": 0.0,
	}
	for component in earning_types + deduction_types:
		totals[frappe.scrub(component)] = 0.0
	return totals


def add_employee_to_totals(totals, row, earning_types, deduction_types):
	totals["no_of_employees"] += 1
	totals["gross_pay"] += row.gross_pay
	totals["loan_repayment"] += row.loan_repayment
	totals["total_deduction"] += row.total_deduction
	totals["net_pay"] += row.net_pay
	for earning in earning_types:
		totals[frappe.scrub(earning)] += row.earnings.get(earning, 0.0)
	for deduction in deduction_types:
		totals[frappe.scrub(deduction)] += row.deductions.get(deduction, 0.0)


def merge_totals(target, source):
	for key in target:
		target[key] += source[key]


def employee_row(sr, row, earning_types, deduction_types):
	data_row = {
		"indent": 2,
		"sr": sr,
		"employee": row.employee,
		"particulars": row.employee_name,
		"designation": row.designation,
		"date_of_joining": row.date_of_joining,
		"ssn": row.ssn,
		"eobi_number": row.eobi_number,
	}
	for earning in earning_types:
		data_row[frappe.scrub(earning)] = row.earnings.get(earning, 0.0)
	data_row["gross_pay"] = row.gross_pay
	for deduction in deduction_types:
		data_row[frappe.scrub(deduction)] = row.deductions.get(deduction, 0.0)
	data_row["loan_repayment"] = row.loan_repayment
	data_row["total_deduction"] = row.total_deduction
	data_row["net_pay"] = row.net_pay
	return data_row


def section_row(label, totals, indent):
	row = {"particulars": label, "indent": indent, "is_bold": 1}
	if totals:
		row.update(totals)
	return row
