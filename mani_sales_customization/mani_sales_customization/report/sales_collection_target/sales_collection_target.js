// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Collection Target"] = {
	"filters": [
		{
			"fieldname":"sales_person",
			"label": __("Sales Person"),
			"fieldtype": "Link",
			"options": "Sales Person",
			"reqd": 1,
			"width": "100px"
		},
		{
			"fieldname":"year",
			"label": __("Year"),
			"fieldtype": "Select",
			"options": "2022\n2023\n2024\n2025\n2026\n2027",
			"reqd": 1,
			"width": "100px"
		},
	]
};
