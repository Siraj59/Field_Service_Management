import json

import frappe


@frappe.whitelist()
def create_service_invoice(doctype, docname, customer, items=None):
	items = json.loads(items) if items else []
	invoice = frappe.new_doc("Sales Invoice")
	invoice.customer = customer
	invoice.custom_reference_service_doctype = doctype
	invoice.custom_reference_service_document = docname
	if doctype in ("Service Order", "Service Appointment"):
		service_doc = frappe.get_doc(doctype, docname)
		service_doc.check_permission("read")
		if service_doc.customer != customer:
			frappe.throw("Invoice customer must match the service job customer")
		order_name = docname if doctype == "Service Order" else service_doc.service_order
		if order_name:
			order = frappe.get_doc("Service Order", order_name)
			invoice.po_no = order.purchase_order
	for item in items:
		invoice.append(
			"items",
			{
				"item_code": item["item_code"],
				"qty": item["qty"],
				"rate": item["rate"],
				"amount": item["amount"],
			},
		)
	invoice.insert()
	return invoice.name


def update_invoice_status(doc, method):
	if not (doc.custom_reference_service_doctype and doc.custom_reference_service_document):
		return

	# Derive billed quantities from submitted invoices, so cancellation and partial
	# invoicing cannot double-count quantities or leave a cancelled invoice billed.
	invoice_names = frappe.get_all(
		"Sales Invoice",
		filters={
			"custom_reference_service_doctype": doc.custom_reference_service_doctype,
			"custom_reference_service_document": doc.custom_reference_service_document,
			"docstatus": 1,
		},
		pluck="name",
	)
	invoice_names = [name for name in invoice_names if name != doc.name]
	if method == "on_submit":
		invoice_names.append(doc.name)
	invoice_item_codes = {}
	if invoice_names:
		for item in frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": ["in", invoice_names]},
			fields=["item_code", "qty"],
		):
			invoice_item_codes[item.item_code] = invoice_item_codes.get(item.item_code, 0) + item.qty

	# Load the referenced service document
	ref_doctype = doc.custom_reference_service_doctype
	ref_docname = doc.custom_reference_service_document
	service_doc = frappe.get_doc(ref_doctype, ref_docname)

	updated = False
	child_tables = ["items"]  # Extend this list if there are more child tables to update (Services, Parts)
	for table in child_tables:
		if not hasattr(service_doc, table):
			frappe.throw(f"No '{table}' child table found in {ref_doctype}")

		for row in getattr(service_doc, table):
			remaining = invoice_item_codes.get(row.item_code, 0)
			invoiced_qty = min(row.qty, remaining)
			invoice_item_codes[row.item_code] = max(0, remaining - invoiced_qty)
			status = (
				"Invoiced" if invoiced_qty >= row.qty else
				"Partly Invoiced" if invoiced_qty > 0 else "Not Invoiced"
			)
			if row.invoiced_qty != invoiced_qty or row.invoice_status != status:
				row.invoiced_qty = invoiced_qty
				row.invoice_status = status
				updated = True

	if updated:
		service_doc.save()
		frappe.msgprint(
			f"Updated invoice status for <strong>Services and Parts</strong> in "
			f"<strong>{ref_doctype}</strong> {ref_docname}"
		)

	update_associated_docs_invoice_status(doc, method)


def update_associated_docs_invoice_status(doc, method):
	if not (doc.custom_reference_service_doctype and doc.custom_reference_service_document):
		return

	source_doc = frappe.get_doc(doc.custom_reference_service_doctype, doc.custom_reference_service_document)
	source_items = source_doc.get("items", [])

	possible_doctypes = {"Service Order", "Service Appointment"}
	target_doctype = (possible_doctypes - {doc.custom_reference_service_doctype}).pop()

	if target_doctype == "Service Order":
		target_docnames = [source_doc.service_order] if source_doc.service_order else []
	elif target_doctype == "Service Appointment":
		target_docnames = frappe.get_all(
			target_doctype, filters={"service_order": source_doc.name}, pluck="name"
		)
	else:
		target_docnames = []

	# For Service Appointments, update other similar appointments in the same order
	if doc.custom_reference_service_doctype == "Service Appointment":
		similar_appointments = frappe.get_all(
			source_doc.doctype,
			filters={"service_order": source_doc.service_order, "name": ["!=", source_doc.name]},
			pluck="name",
		)
		for appointment_name in similar_appointments:
			update_target_documents(source_doc.doctype, appointment_name, source_items)

	for target_name in target_docnames:
		update_target_documents(target_doctype, target_name, source_items)


def update_target_documents(target_doctype, target_docname, source_items):
	target_doc = frappe.get_doc(target_doctype, target_docname)

	# Build a lookup for items in the target document by item_code
	target_items_lookup = {row.item_code: row for row in target_doc.get("items", [])}

	updated = False
	for item in source_items:
		target_row = target_items_lookup.get(item.item_code)
		# Update only if the invoice status is different from the source's current status
		if target_row and target_row.invoice_status != item.invoice_status:
			target_row.invoice_status = item.invoice_status
			target_row.invoiced_qty = item.invoiced_qty
			updated = True

	if updated:
		target_doc.save()
		frappe.msgprint(
			f"Updated invoice status for <strong>Services and Parts</strong> in "
			f"<strong>{target_doctype}</strong> {target_docname}"
		)


def update_per_billed_status(doc, method):
	total_amount = 0.0
	billed_amount = 0.0

	if not (doc.custom_reference_service_doctype and doc.custom_reference_service_document):
		return

	ref_doc = frappe.get_doc(doc.custom_reference_service_doctype, doc.custom_reference_service_document)

	for item in ref_doc.get("items", []):
		full_amount = item.amount or 0.0
		total_amount += full_amount

		invoiced_qty = item.get("invoiced_qty", 0)
		item_qty = item.qty or 0
		proportion_invoiced = (invoiced_qty / item_qty) if item_qty else 0

		billed_amount += full_amount * proportion_invoiced

	ref_doc.per_billed = (billed_amount / total_amount) * 100 if total_amount else 0.0
	ref_doc.save()


@frappe.whitelist()
def update_appointment_from_api(
	name, scheduled_start_datetime, scheduled_finish_datetime, service_technicians, items
):
	appointment = frappe.get_doc("Service Appointment", name)
	# delete all items from the appointment
	appointment.service_technicians = []
	appointment.items = []

	for item in items:
		appointment.append(
			"items",
			{
				"item_code": item["item_code"],
				"qty": item["qty"],
				"rate": item["rate"],
				"amount": item["amount"],
			},
		)

	for service_technician in service_technicians:
		appointment.append(
			"service_technicians",
			{
				"service_technician": service_technician["service_technician"],
				"full_name": service_technician["full_name"],
				# "service_area": service_technician["service_area"],
				# "specialization": service_technician["specialization"]
			},
		)

	appointment.scheduled_start_datetime = scheduled_start_datetime
	appointment.scheduled_finish_datetime = scheduled_finish_datetime

	appointment.save()
	return appointment.name
