# Copyright (c) 2026, Beveren Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ServiceTestEquipment(Document):
	def validate(self):
		latest = {}
		for row in self.maintenance_events:
			if row.next_due_date and getdate(row.next_due_date) < getdate(row.performed_on):
				frappe.throw(_("Activity {0}: the next due date cannot precede the work date.").format(row.idx))
			if row.event_type in ("Calibration", "Preventive Maintenance") and row.next_due_date:
				previous = latest.get(row.event_type)
				if previous is None or getdate(row.performed_on) > getdate(previous.performed_on):
					latest[row.event_type] = row

		if "Calibration" in latest:
			self.calibration_due_date = latest["Calibration"].next_due_date
		if "Preventive Maintenance" in latest:
			self.pm_due_date = latest["Preventive Maintenance"].next_due_date
