# Copyright (c) 2025, Beveren Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate


class ServiceReport(Document):
	def validate(self):
		self.calculate_time_entries()
		self.validate_parts_and_tools()
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

	def validate_parts_and_tools(self):
		for row in self.parts_used_rows:
			if flt(row.quantity) <= 0:
				frappe.throw(_("Part row {0} needs a quantity greater than zero.").format(row.idx))

		for row in self.test_tools:
			if not row.test_equipment:
				frappe.throw(_("Test tool row {0} needs a tool from the register.").format(row.idx))
			as_of = getdate(row.used_on or self.service_date) if (row.used_on or self.service_date) else None
			# Keep a historical snapshot. Later updates to a tool's due dates do not
			# change a submitted FSR or an amendment of that FSR.
			if row.snapshot_for == row.test_equipment and row.snapshot_as_of == str(as_of):
				continue
			tool = frappe.get_doc("Service Test Equipment", row.test_equipment)
			row.tool_name = tool.equipment_name
			def event_at_service(event_type):
				events = [event for event in tool.maintenance_events if event.event_type == event_type]
				eligible = [event for event in events if not as_of or getdate(event.performed_on) <= as_of]
				return events, max(eligible, key=lambda event: getdate(event.performed_on)) if eligible else None

			calibrations, calibration = event_at_service("Calibration")
			pm_events, pm = event_at_service("Preventive Maintenance")
			row.calibration_due_date = calibration.next_due_date if calibration else (
				tool.calibration_due_date if not calibrations else None
			)
			row.pm_due_date = pm.next_due_date if pm else (tool.pm_due_date if not pm_events else None)
			row.calibration_certificate = calibration.certificate if calibration else None
			row.snapshot_for = row.test_equipment
			row.snapshot_as_of = str(as_of)

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
