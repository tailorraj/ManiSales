# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.accounts.report.financial_statements import get_period_list
from erpnext.accounts.utils import get_fiscal_year
from collections import defaultdict
from datetime import datetime,date
from functools import reduce


def execute(filters=None):
	period_list = get_period_list(filters.fiscal_year, filters.fiscal_year, '', '',
		'Fiscal Year', filters.period, company=filters.company)

	columns, data = get_data_column(filters , period_list), get_data(filters , period_list)
	return columns, data

def get_data_column(filters , period_list):
	
	columns = get_columns(filters, period_list)
	return columns

def get_columns(filters, period_list):
	fieldtype, options = "Currency", "currency"

	columns = [
	{
	"fieldname": "cost_center",
	"label": _("Cost Center"),
	"fieldtype": "Link",
	"options": "Cost Center",
	"width": 150
	},
	{
	"fieldname": "sales_person",
	"label": _("Sales Person"),
	"fieldtype": "Link",
	"options": "Sales Person",
	"width": 150
	}]
	
	for period in period_list:
		target_key = 'target_{}'.format(period.key)
		variance_key = 'variance_{}'.format(period.key)
		cf_key = 'carryforward_{}'.format(period.key)

		columns.extend([
			{
			"fieldname": target_key,
			"label": _("Target ({})").format(period.label),
			"fieldtype": fieldtype,
			"options": options,
			"width": 150
		}, 
		{
			"fieldname": cf_key,
			"label": _("Carry Forwarded").format(period.label),
			"fieldtype": fieldtype,
			"options": options,
			"width": 150
		}, 
		{
			"fieldname": period.key,
			"label": _("Achieved ({})").format(period.label),
			"fieldtype": fieldtype,
			"options": options,
			"width": 150
		}, {
			"fieldname": variance_key,
			"label": _("Variance ({})").format(period.label),
			"fieldtype": fieldtype,
			"options": options,
			"width": 150
		}])

	columns.extend([{
		"fieldname": "total_target",
		"label": _("Total Target"),
		"fieldtype": fieldtype,
		"options": options,
		"width": 150
	}, {
		"fieldname": "total_achieved",
		"label": _("Total Achieved"),
		"fieldtype": fieldtype,
		"options": options,
		"width": 150
	}, {
		"fieldname": "total_variance",
		"label": _("Total Variance"),
		"fieldtype": fieldtype,
		"options": options,
		"width": 150
	}])

	return columns

def get_data(filters , period_list):
	fiscal_year = get_fiscal_year(fiscal_year=filters.get("fiscal_year"), as_dict=1)
	from_date,to_date = fiscal_year.year_start_date, fiscal_year.year_end_date

	sales_data = frappe.db.sql("""
	select 
	sum(ps.payment_amount) as sales_target,si.sales_executive,si.cost_center, month(ps.due_date) as month, year(ps.due_date) as year 
	from 
	`tabSales Invoice` si inner join `tabPayment Schedule` ps on si.name = ps.parent
	where si.docstatus = 1 and ps.due_date between %(from_date)s and %(to_date)s
	group by si.cost_center,month(ps.due_date),year(ps.due_date),si.sales_executive
	""",{
		"from_date":from_date,
		"to_date":to_date
	},as_dict=1)

	payment_data = frappe.db.sql("""
	select sum(per.allocated_amount) as paid_amount,si.sales_executive,si.cost_center,month(pe.posting_date) as month,year(pe.posting_date) as year
	from 
	`tabPayment Entry Reference` per inner join `tabPayment Entry`  pe on pe.name = per.parent 
	left join `tabSales Invoice` si on si.name = per.reference_name
	where pe.docstatus = 1 and pe.posting_date between %(from_date)s and %(to_date)s
	group by 
	month(pe.posting_date),year(pe.posting_date),si.cost_center,si.sales_executive
	""",({
		"from_date":from_date,
		"to_date":to_date
	}),as_dict=1)

	payment_data_before = frappe.db.sql("""
	select sum(per.allocated_amount) as paid_amount,si.sales_executive,si.cost_center,month(pe.posting_date) as month,year(pe.posting_date) as year
	from 
	`tabPayment Entry Reference` per inner join `tabPayment Entry`  pe on pe.name = per.parent 
	left join `tabSales Invoice` si on si.name = per.reference_name
	where pe.docstatus = 1 and pe.posting_date < %(from_date)s
	group by 
	month(pe.posting_date),year(pe.posting_date),si.cost_center,si.sales_executive
	""",({
		"from_date":from_date,
	}),as_dict=1)

	# total_carryforward_payment_before = reduce(sum_of_amount , payment_data_before , 0.0) 
	
	
	journal_entry_data = frappe.db.sql("""
	select sum(jea.credit_in_account_currency) as paid_amount,si.sales_executive,si.cost_center,month(je.posting_date) as month,year(je.posting_date) as year
	from 
	`tabJournal Entry Account` jea inner join `tabJournal Entry`  je on je.name = jea.parent 
	left join `tabSales Invoice` si on si.name = jea.reference_name
	where jea.reference_type = "Sales Invoice" and je.docstatus = 1 and je.posting_date between %(from_date)s and %(to_date)s
	group by 
	month(je.posting_date),year(je.posting_date),si.cost_center,si.sales_executive
	""",({
		"from_date":from_date,
		"to_date":to_date
	}),as_dict=1) 

	journal_entry_data_before = frappe.db.sql("""
	select sum(jea.credit_in_account_currency) as paid_amount,si.sales_executive,si.cost_center,month(je.posting_date) as month,year(je.posting_date) as year
	from 
	`tabJournal Entry Account` jea inner join `tabJournal Entry`  je on je.name = jea.parent 
	left join `tabSales Invoice` si on si.name = jea.reference_name
	where jea.reference_type = "Sales Invoice" and je.docstatus = 1 and je.posting_date < %(from_date)s
	group by 
	month(je.posting_date),year(je.posting_date),si.cost_center,si.sales_executive
	""",({
		"from_date":from_date,
	}),as_dict=1) 

	merged_sales_data = sales_data
	merged_payment_data = merge_lists(payment_data , journal_entry_data)
	merged_carryforwared_data_dict = merge_carryforward_lists(payment_data_before , journal_entry_data_before)
	grouped_data = aggregate_data(filters.get('period'), merged_sales_data, merged_payment_data, period_list , merged_carryforwared_data_dict)
	return grouped_data

def sum_of_amount(acc , data):
	acc += data["paid_amount"]
	return acc

def aggregate_data(period, sales_data, payment_data,period_list , merged_carryforwared_data):
	period_dict = {'Monthly': 1, 'Quarterly': 3, 'Half-Yearly': 6, 'Yearly': 12}
	period_value = period_dict[period]

	agg_data = defaultdict(lambda: defaultdict(float))

	for p in period_list:
		payments_ = []
		sales_ = []
		date_time = datetime.now()

		if period_value == 1:
			date_time = datetime.strptime(p.key, "%b_%Y")
			sales_ = list(filter(lambda x : x['month'] == date_time.month and x['year'] == date_time.year, sales_data))
			payments_ = list(filter(lambda x : x['month'] == date_time.month and x['year'] == date_time.year, payment_data))
		elif period_value == 12:
			sales_ = list(filter(lambda x : filter_year(x,p), sales_data))
			payments_ = list(filter(lambda x : filter_year(x,p), payment_data))
		else:
			sales_ = list(filter(lambda x : filter_month_year(x,p), sales_data))
			payments_ = list(filter(lambda x : filter_month_year(x,p), payment_data))

		for d in sales_:
			key = (d['sales_executive'], d['cost_center'], p.key)
			agg_data[key]['sales_target'] += d['sales_target']

		for d in payments_:
			key = (d['sales_executive'], d['cost_center'], p.key)
			agg_data[key]['paid_amount'] += d['paid_amount']

	result = []
	total_target = 0
	total_achieved = 0
	total_variance = 0

	new_agg_data = defaultdict(lambda: defaultdict(list))
	new_agg_total_target = defaultdict(lambda: defaultdict(float))
	new_agg_total_archived = defaultdict(lambda: defaultdict(float))
	new_agg_total_variance = defaultdict(lambda: defaultdict(float))

	prev_variance = {}
	for key, value in agg_data.items():
		sales_person, cost_center, period = key
		sales_target = value['sales_target']
		paid_amount = value['paid_amount']
		variance = sales_target - paid_amount
		
		
		total_target += sales_target
		total_achieved += paid_amount
		total_variance += variance

		target_key = 'target_{}'.format(period)
		carry_forward_key = 'carryforward_{}'.format(period)
		variance_key = 'variance_{}'.format(period)
		period_key = period

		new_key = (sales_person,cost_center)

		if not new_agg_data[new_key]:
			new_agg_data[new_key] = []

		if new_key not in prev_variance:
			prev_variance[new_key] = merged_carryforwared_data[new_key]["paid_amount"] if new_key in merged_carryforwared_data else 0.0
		
		agg_sales_target = sales_target + prev_variance[new_key]
		carry_forward_amount = prev_variance[new_key]
		agg_variance = agg_sales_target - paid_amount
		
		new_agg_data[new_key].append({
			period_key : paid_amount,
			carry_forward_key : carry_forward_amount,
			target_key : sales_target,
			variance_key : agg_variance
		})
		prev_variance[new_key] = agg_variance
		new_agg_total_target[new_key]["sales_target"] += sales_target
		new_agg_total_archived[new_key]["paid_amount"] += paid_amount
		new_agg_total_variance[new_key]["variance"] += variance

	for key, value in new_agg_data.items():
		sales_person,cost_center = key

		single_result = {}
		single_result["cost_center"] = cost_center
		single_result["sales_person"] = sales_person
		for items in value:
			single_result.update(items)

		single_result.update({
			"total_target" : new_agg_total_target[key]["sales_target"],
			"total_achieved" : new_agg_total_archived[key]["paid_amount"],
			"total_variance" : new_agg_total_variance[key]["variance"]
		})

		result.append(single_result)

	return result

def filter_month_year(x , p):
	start_ = p.from_date
	end_ = p.to_date

	month = int(x['month'])
	year = int(x['year'])

	return month >= start_.month and year >= start_.year and month <= end_.month and year <= end_.year

def filter_year(x , p):
	start_ = p.from_date
	end_ = p.to_date

	return x['year'] >= start_.year and x['year'] <= end_.year

def merge_lists(List1, List2):
    merged_list = List1 + List2
    merged_dict = {}

    for d in merged_list:
        key = (d['sales_executive'], d['cost_center'], d['month'], d['year'])
        if key in merged_dict:
            merged_dict[key]['paid_amount'] += d['paid_amount']
        else:
            merged_dict[key] = d

    return list(merged_dict.values())

def merge_carryforward_lists(List1, List2):
    merged_list = List1 + List2
    merged_dict = {}

    for d in merged_list:
        key = (d['sales_executive'], d['cost_center'])
        if key in merged_dict:
            merged_dict[key]['paid_amount'] += d['paid_amount']
        else:
            merged_dict[key] = d

    return merged_dict

def merge_sales_lists(List1, List2):
    merged_list = List1 + List2
    merged_dict = {}

    for d in merged_list:
        key = (d['sales_executive'], d['cost_center'], d['month'], d['year'])
        if key in merged_dict:
            merged_dict[key]['sales_target'] += d['sales_target']
        else:
            merged_dict[key] = d

    return list(merged_dict.values())	
# def get_columns(filters):
# 	columns = [{
# 		"fieldname": "cost_center",
# 		"label": "Cost Center",
# 		"type":"Data",
# 		"width":"80px"
# 	},
# 	{
# 		"fieldname": "sales_person",
# 		"label": "Sales Person",
# 		"type":"Link",
# 		"options":"Sales Person",
# 		"width":"80px"
# 	}]
# 	columns = columns + get_month_labels(filters.get('year'))

# 	columns.extend(
# 		[
# 			{
# 				"fieldname": "total_target",
# 				"label": _("Total Target"),
# 				"fieldtype": "Float",
# 				"width": 150,
# 			},
# 			{
# 				"fieldname": "total_achieved",
# 				"label": _("Total Achieved"),
# 				"fieldtype": "Float",
# 				"width": 150,
# 			},
# 			{
# 				"fieldname": "total_variance",
# 				"label": _("Total Variance"),
# 				"fieldtype": "Float",
# 				"width": 150,
# 			},
# 		]
# 	)
# 	# columns = [
# 	# _("Null Column") + "Data:150",
# 	# _("Total Outstanding") + "Data:150",
# 	# _("March(Target)") + "Data:150",
# 	# _("March(Achieved)") + "Data:150",
# 	# _("March(Variance)") + "Data:150"]
# 	# frappe.throw(str(columns))

	
# 	return columns

# def get_data(filters):
# 	pass
# 	sales_data = frappe.db.sql("""
# 	select 

# 	sum(ps.payment_amount) as sales_target,st.sales_person,si.cost_center,month(si.posting_date) as month,year(si.posting_date) as year 

# 	from 

# 	`tabSales Invoice` si inner join `tabPayment Schedule` ps on si.name = ps.parent 
# 	left join `tabSales Team` st on st.parent = si.name

# 	where si.docstatus = 1 and year(si.posting_date) = %(year)s

# 	group by si.cost_center,month(si.posting_date),year(si.posting_date),st.sales_person

# 	order by month(si.posting_date),year(si.posting_date)
# 	""",{
#         "year":filters.get('year')
# 	},as_dict=1)

# 	payment_data = frappe.db.sql("""
# 	select sum(per.allocated_amount) as paid_amount,st.sales_person,pe.cost_center,month(pe.posting_date) as month,year(pe.posting_date) as year 

# 	from 

# 	`tabPayment Entry Reference` per inner join `tabPayment Entry`  pe on pe.name = per.parent 
# 	left join `tabSales Team` st on st.parent = per.reference_name

# 	where 

# 	per.reference_doctype = "Sales Invoice" and pe.docstatus = 1 and year(pe.posting_date) = %(year)s

# 	group by 

# 	month(pe.posting_date),year(pe.posting_date),pe.cost_center,st.sales_person

# 	""",({
#         "year":filters.get('year')
# 	}),as_dict=1)

	# frappe.msgprint(str(sales_data))
	# frappe.msgprint(str(payment_data))
# 	res_dict = merge_sales_payment_dicts(sales_data,payment_data)
# 	grouped_data = group_by_cost_center(res_dict)
# 	frappe.msgprint(str(grouped_data))
# 	return grouped_data


# def merge_sales_payment_dicts(sales_list, payment_list):
#     merged_list = []
    
#     # Create a dictionary of sales records
#     sales_dict = {}
#     for sales_record in sales_list:
#         key = (sales_record["sales_person"], sales_record["cost_center"], sales_record["month"], sales_record["year"])
#         sales_dict[key] = sales_record
    
#     # Merge the payment records with the sales records
#     for payment_record in payment_list:
#         key = (payment_record["sales_person"], payment_record["cost_center"], payment_record["month"], payment_record["year"])
#         merged_dict = {
#             "sales_target-{}-{}".format(payment_record["month"], payment_record["year"]): 0.0,
#             "paid_amount-{}-{}".format(payment_record["month"], payment_record["year"]): payment_record["paid_amount"],
#             "variance-{}-{}".format(payment_record["month"], payment_record["year"]): 0.0,
#             "sales_person": payment_record["sales_person"],
#             "cost_center": payment_record["cost_center"],
#         }
#         if key in sales_dict:
#             sales_record = sales_dict[key]
#             merged_dict["sales_target-{}-{}".format(payment_record["month"], payment_record["year"])] = sales_record["sales_target"]
#             merged_dict["variance-{}-{}".format(payment_record["month"], payment_record["year"])] = sales_record["sales_target"] - payment_record["paid_amount"]
#             del sales_dict[key]
#         else:
#             merged_dict["variance-{}-{}".format(payment_record["month"], payment_record["year"])] = -payment_record["paid_amount"]
#         merged_list.append(merged_dict)
    
#     # Add any remaining sales records to the merged list
#     for sales_record in sales_dict.values():
#         merged_dict = {
#             "sales_target-{}-{}".format(sales_record["month"], sales_record["year"]): sales_record["sales_target"],
#             "paid_amount-{}-{}".format(sales_record["month"], sales_record["year"]): 0.0,
#             "variance-{}-{}".format(sales_record["month"], sales_record["year"]): sales_record["sales_target"],
#             "sales_person": sales_record["sales_person"],
#             "cost_center": sales_record["cost_center"],
#         }
#         merged_list.append(merged_dict)
    
#     return merged_list

# def group_by_cost_center(data):
#     result = []
#     cost_centers = set(d['cost_center'] for d in data)
#     for cost_center in cost_centers:
#         target = {}
#         for d in data:
#             if d['cost_center'] == cost_center:
#                 target.update(d)
#         result.append(target)
#     return result


# def get_month_labels(year):
#     import calendar
#     """
#     Returns a list of dictionaries with fieldname and label for each month in the given year.
#     """
#     month_labels = []
#     for month in range(1, 13):
#         month_name = calendar.month_name[month]
#         month_labels.append({
#             "fieldname": f"sales_target-{month}-{year}",
#             "label": f"Target-{month_name}({year})",
# 			"type":"float",
# 			"width":"80px"
#         })
#         month_labels.append({
#             "fieldname": f"paid_amount-{month}-{year}",
#             "label": f"Achieved-{month_name}({year})",
# 			"type":"float",
# 			"width":"80px"
#         })
#         month_labels.append({
#             "fieldname": f"variance-{month}-{year}",
#             "label": f"Variance-{month_name}({year})",
# 			"type":"float",
# 			"width":"80px"
#         })
#     return month_labels