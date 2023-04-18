# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_columns(filters):
	columns = [{
		"fieldname": "cost_center",
		"label": "Cost Center",
		"type":"Data",
		"width":"80px"
	}]
        
	columns = columns + get_month_labels(filters.get('year'))
	# columns = [
	# _("Null Column") + "Data:150",
	# _("Total Outstanding") + "Data:150",
	# _("March(Target)") + "Data:150",
	# _("March(Achieved)") + "Data:150",
	# _("March(Variance)") + "Data:150"]
	# frappe.throw(str(columns))

	
	return columns

def get_data(filters):
	sales_data = frappe.db.sql("""
	select 

	sum(ps.payment_amount) as sales_target,st.sales_person,si.cost_center,month(si.posting_date) as month,year(si.posting_date) as year 

	from 

	`tabSales Invoice` si inner join `tabPayment Schedule` ps on si.name = ps.parent 
	left join `tabSales Team` st on st.parent = si.name

	where si.docstatus = 1 and st.sales_person = %(sales_person)s and year(si.posting_date) = %(year)s

	group by si.cost_center,month(si.posting_date),year(si.posting_date)

	order by month(si.posting_date),year(si.posting_date)
	""",{
		"sales_person":filters.get('sales_person'),
        "year":filters.get('year')
	},as_dict=1)

	payment_data = frappe.db.sql("""
	select sum(per.allocated_amount) as paid_amount,st.sales_person,pe.cost_center,month(pe.posting_date) as month,year(pe.posting_date) as year 

	from 

	`tabPayment Entry Reference` per inner join `tabPayment Entry`  pe on pe.name = per.parent 
	left join `tabSales Team` st on st.parent = per.reference_name

	where 

	per.reference_doctype = "Sales Invoice" and pe.docstatus = 1 and st.sales_person = %(sales_person)s and year(pe.posting_date) = %(year)s

	group by 

	month(pe.posting_date),year(pe.posting_date),pe.cost_center

	""",({
		"sales_person":filters.get('sales_person'),
        "year":filters.get('year')
	}),as_dict=1)

	# frappe.msgprint(str(sales_data))
	# frappe.msgprint(str(payment_data))
	res_dict = merge_sales_payment_dicts(sales_data,payment_data)
	final_res = group_by_cost_center(res_dict)
	# frappe.msgprint(str(final_res))
	return final_res


def merge_sales_payment_dicts(sales_list, payment_list):
    merged_list = []
    
    # Create a dictionary of sales records
    sales_dict = {}
    for sales_record in sales_list:
        key = (sales_record["sales_person"], sales_record["cost_center"], sales_record["month"], sales_record["year"])
        sales_dict[key] = sales_record
    
    # Merge the payment records with the sales records
    for payment_record in payment_list:
        key = (payment_record["sales_person"], payment_record["cost_center"], payment_record["month"], payment_record["year"])
        merged_dict = {
            "sales_target-{}-{}".format(payment_record["month"], payment_record["year"]): 0.0,
            "paid_amount-{}-{}".format(payment_record["month"], payment_record["year"]): payment_record["paid_amount"],
            "variance-{}-{}".format(payment_record["month"], payment_record["year"]): 0.0,
            "sales_person": payment_record["sales_person"],
            "cost_center": payment_record["cost_center"],
        }
        if key in sales_dict:
            sales_record = sales_dict[key]
            merged_dict["sales_target-{}-{}".format(payment_record["month"], payment_record["year"])] = sales_record["sales_target"]
            merged_dict["variance-{}-{}".format(payment_record["month"], payment_record["year"])] = sales_record["sales_target"] - payment_record["paid_amount"]
            del sales_dict[key]
        else:
            merged_dict["variance-{}-{}".format(payment_record["month"], payment_record["year"])] = -payment_record["paid_amount"]
        merged_list.append(merged_dict)
    
    # Add any remaining sales records to the merged list
    for sales_record in sales_dict.values():
        merged_dict = {
            "sales_target-{}-{}".format(sales_record["month"], sales_record["year"]): sales_record["sales_target"],
            "paid_amount-{}-{}".format(sales_record["month"], sales_record["year"]): 0.0,
            "variance-{}-{}".format(sales_record["month"], sales_record["year"]): sales_record["sales_target"],
            "sales_person": sales_record["sales_person"],
            "cost_center": sales_record["cost_center"],
        }
        merged_list.append(merged_dict)
    
    return merged_list

def group_by_cost_center(data):
    result = []
    cost_centers = set(d['cost_center'] for d in data)
    for cost_center in cost_centers:
        target = {}
        for d in data:
            if d['cost_center'] == cost_center:
                target.update(d)
        result.append(target)
    return result


def get_month_labels(year):
    import calendar
    """
    Returns a list of dictionaries with fieldname and label for each month in the given year.
    """
    month_labels = []
    for month in range(1, 13):
        month_name = calendar.month_name[month]
        month_labels.append({
            "fieldname": f"sales_target-{month}-{year}",
            "label": f"Target-{month_name}({year})",
			"type":"float",
			"width":"80px"
        })
        month_labels.append({
            "fieldname": f"paid_amount-{month}-{year}",
            "label": f"Achieved-{month_name}({year})",
			"type":"float",
			"width":"80px"
        })
        month_labels.append({
            "fieldname": f"variance-{month}-{year}",
            "label": f"Variance-{month_name}({year})",
			"type":"float",
			"width":"80px"
        })
    return month_labels