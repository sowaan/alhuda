// Copyright (c) 2026, Al Huda and contributors
// For license information, please see license.txt

frappe.query_reports["Department and Branch Wise Salary Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			// TODO: re-lock to "AL-HUDA INTERNATIONAL WELFARE FOUNDATION" with
			// read_only: 1 once that company has real Salary Slip data; left
			// open for now purely for cross-company testing.
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			width: "150px",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			width: "150px",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			width: "150px",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
			width: "100px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
			width: "100px",
		},
		{
			fieldname: "docstatus",
			label: __("Document Status"),
			fieldtype: "Select",
			options: ["Draft", "Submitted", "Cancelled"],
			default: "Submitted",
			width: "100px",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.is_bold) {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};
