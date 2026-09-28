# Copyright (c) 2025, Beveren Software and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


class TestServiceReport(FrappeTestCase):
	def test_time_log_calculates_two_visits_and_keeps_prior_manual_reports(self):
		report = frappe.get_doc({"doctype": "Service Report", "labor_hours": 7, "travel_hours": 2})
		report.calculate_time_entries()
		self.assertEqual((report.labor_hours, report.travel_hours, report.total_hours), (7, 2, 9))

		for activity, start, end in (
			("Travel", "2026-09-13 08:00:00", "2026-09-13 09:00:00"),
			("Work", "2026-09-13 13:00:00", "2026-09-13 19:00:00"),
			("Travel", "2026-09-13 19:00:00", "2026-09-13 20:00:00"),
			("Work", "2026-09-20 10:30:00", "2026-09-20 11:30:00"),
		):
			report.append("time_entries", {"activity_type": activity, "start_datetime": start, "end_datetime": end})

		report.calculate_time_entries()
		self.assertEqual((report.labor_hours, report.travel_hours, report.total_hours), (7, 2, 9))
		self.assertEqual([row.duration_hours for row in report.time_entries], [1, 6, 1, 1])

	def test_time_log_rejects_overlapping_entries(self):
		report = frappe.get_doc({"doctype": "Service Report"})
		report.append("time_entries", {"activity_type": "Work", "start_datetime": "2026-09-13 13:00:00", "end_datetime": "2026-09-13 19:00:00"})
		report.append("time_entries", {"activity_type": "Travel", "start_datetime": "2026-09-13 18:00:00", "end_datetime": "2026-09-13 20:00:00"})
		with self.assertRaises(ValidationError):
			report.calculate_time_entries()

	def test_tool_details_are_snapshotted_and_parts_need_positive_quantity(self):
		tool = frappe.get_doc({
			"doctype": "Service Test Equipment",
			"asset_id": "TEST-X2-001",
			"equipment_name": "RaySafe X2",
			"calibration_due_date": "2027-03-01",
			"pm_due_date": "2027-05-01",
		}).insert()
		report = frappe.get_doc({"doctype": "Service Report"})
		report.append("test_tools", {"test_equipment": tool.name, "used_on": "2026-09-20"})
		report.append("parts_used_rows", {"description": "Battery set", "quantity": 2})
		report.validate_parts_and_tools()
		row = report.test_tools[0]
		self.assertEqual((row.tool_name, str(row.calibration_due_date), str(row.pm_due_date)),
			("RaySafe X2", "2027-03-01", "2027-05-01"))

		tool.calibration_due_date = "2028-03-01"
		tool.save()
		report.validate_parts_and_tools()
		self.assertEqual(str(row.calibration_due_date), "2027-03-01")

		report.parts_used_rows[0].quantity = 0
		with self.assertRaises(ValidationError):
			report.validate_parts_and_tools()

	def test_backdated_fsr_uses_calibration_history_at_service_date(self):
		tool = frappe.get_doc({
			"doctype": "Service Test Equipment",
			"asset_id": "TEST-X2-HISTORY",
			"equipment_name": "RaySafe X2",
			"maintenance_events": [
				{"event_type": "Calibration", "performed_on": "2026-01-01", "next_due_date": "2027-01-01"},
				{"event_type": "Calibration", "performed_on": "2027-02-01", "next_due_date": "2028-02-01"},
			],
		}).insert()
		report = frappe.get_doc({"doctype": "Service Report", "service_date": "2026-09-20 11:30:00"})
		report.append("test_tools", {"test_equipment": tool.name, "used_on": "2026-09-13"})
		report.validate_parts_and_tools()
		self.assertEqual(str(report.test_tools[0].calibration_due_date), "2027-01-01")
		self.assertEqual(report.test_tools[0].snapshot_as_of, "2026-09-13")
