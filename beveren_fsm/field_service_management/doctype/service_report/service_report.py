# Copyright (c) 2025, Beveren Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime


class ServiceReport(Document):
	def validate(self):
		self.calculate_time_entries()
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

	def calculate_time_entries(self):
		"""Keep the existing manual totals for older reports without a time log."""
		if not self.time_entries:
			self.total_hours = flt(self.labor_hours) + flt(self.travel_hours)
			return

		totals = {"Work": 0.0, "Travel": 0.0}
		intervals = []
		for row in self.time_entries:
			if not row.activity_type or not row.start_datetime or not row.end_datetime:
				frappe.throw(_("Time entry {0} needs an activity, start, and end.").format(row.idx))
			start = get_datetime(row.start_datetime)
			end = get_datetime(row.end_datetime)
			if end <= start:
				frappe.throw(_("Time entry {0} must end after it starts.").format(row.idx))
			if row.activity_type not in totals:
				frappe.throw(_("Time entry {0} has an invalid activity type.").format(row.idx))
			row.duration_hours = flt((end - start).total_seconds() / 3600, 3)
			totals[row.activity_type] += row.duration_hours
			intervals.append((start, end, row.idx))

		intervals.sort()
		for previous, current in zip(intervals, intervals[1:]):
			if current[0] < previous[1]:
				frappe.throw(_("Time entries {0} and {1} overlap.").format(previous[2], current[2]))

		self.labor_hours = flt(totals["Work"], 3)
		self.travel_hours = flt(totals["Travel"], 3)
		self.total_hours = flt(self.labor_hours + self.travel_hours, 3)

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
