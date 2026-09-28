# Copyright (c) 2025, Beveren Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceReport(Document):
	def validate(self):
		if self.service_appointment:
			appointment = frappe.get_doc("Service Appointment", self.service_appointment)
			if appointment.customer != self.customer:
				frappe.throw(_("The appointment belongs to a different customer."))
			if appointment.service_order and self.service_order != appointment.service_order:
				frappe.throw(_("The service order must match the appointment's order."))
		if self.service_order:
			order = frappe.get_doc("Service Order", self.service_order)
			if order.customer != self.customer:
				frappe.throw(_("The service order belongs to a different customer."))
			if self.service_quotation and order.service_quotation != self.service_quotation:
				frappe.throw(_("The quotation must match the service order's quotation."))

	def before_submit(self):
		for field in ("reported_problem", "action_performed", "testing_and_results", "disposition"):
			if not self.get(field):
				frappe.throw(_("{0} is required to finalize the FSR.").format(self.meta.get_field(field).label))


@frappe.whitelist()
def make_service_report(appointment_name):
	"""Open a new, unsaved FSR with the job context already filled in."""
	appointment = frappe.get_doc("Service Appointment", appointment_name)
	appointment.check_permission("read")
	if not frappe.has_permission("Service Report", "create"):
		frappe.throw(_("You do not have permission to create a Service Report."), frappe.PermissionError)

	order = frappe.get_doc("Service Order", appointment.service_order) if appointment.service_order else None
	return {
		"customer": appointment.customer,
		"service_appointment": appointment.name,
		"service_order": appointment.service_order,
		"service_quotation": order.service_quotation if order else None,
		"purchase_order": order.purchase_order if order else None,
		"service_date": appointment.actual_start_datetime or appointment.scheduled_start_datetime,
		"technician": ", ".join(
			row.full_name or row.service_technician for row in appointment.service_technicians
		),
		"work_summary": appointment.description,
		"serial_no": order.serial_no if order else None,
		"item_code": order.item_code if order else None,
	}
