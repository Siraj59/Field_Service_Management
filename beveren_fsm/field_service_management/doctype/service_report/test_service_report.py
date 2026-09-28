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
