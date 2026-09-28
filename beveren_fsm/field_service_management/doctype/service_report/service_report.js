frappe.ui.form.on("Service Report", {
  refresh(frm) {
    toggle_time_totals(frm);
  },
  time_entries_add(frm) {
    toggle_time_totals(frm);
  },
  time_entries_remove(frm) {
    toggle_time_totals(frm);
    if (!(frm.doc.time_entries || []).length) {
      frm.set_value("labor_hours", 0);
      frm.set_value("travel_hours", 0);
      frm.set_value("total_hours", 0);
    } else update_time_totals(frm);
  },
  service_appointment(frm) {
    if (!frm.doc.service_appointment) return;
    frappe.db.get_doc("Service Appointment", frm.doc.service_appointment).then((appointment) => {
      frm.set_value("customer", appointment.customer);
      frm.set_value("service_order", appointment.service_order);
      frm.set_value("service_date", appointment.actual_start_datetime || appointment.scheduled_start_datetime);
      frm.set_value("technician", (appointment.service_technicians || [])
        .map((row) => row.full_name || row.service_technician).join(", "));
    });
  },
  service_order(frm) {
    if (!frm.doc.service_order) return;
    frappe.db.get_value("Service Order", frm.doc.service_order,
      ["customer", "service_quotation", "purchase_order", "serial_no", "item_code"]
    ).then(({ message }) => {
      if (!message) return;
      for (const field of ["customer", "service_quotation", "purchase_order", "serial_no", "item_code"]) {
        if (message[field] && !frm.doc[field]) frm.set_value(field, message[field]);
      }
    });
  },
});

function toggle_time_totals(frm) {
  const has_entries = !!(frm.doc.time_entries || []).length;
  frm.set_df_property("labor_hours", "read_only", has_entries);
  frm.set_df_property("travel_hours", "read_only", has_entries);
}

function update_time_totals(frm) {
  const rows = frm.doc.time_entries || [];
  if (!rows.length) return;
  const totals = { Work: 0, Travel: 0 };
  for (const row of rows) {
    if (row.activity_type in totals) totals[row.activity_type] += Number(row.duration_hours) || 0;
  }
  frm.set_value("labor_hours", Number(totals.Work.toFixed(3)));
  frm.set_value("travel_hours", Number(totals.Travel.toFixed(3)));
  frm.set_value("total_hours", Number((totals.Work + totals.Travel).toFixed(3)));
}

function update_time_entry(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  let hours = 0;
  if (row.start_datetime && row.end_datetime) {
    const start = new Date(row.start_datetime.replace(" ", "T"));
    const end = new Date(row.end_datetime.replace(" ", "T"));
    if (Number.isFinite(start.getTime()) && Number.isFinite(end.getTime()) && end > start) {
      hours = Number(((end - start) / 3600000).toFixed(3));
    }
  }
  frappe.model.set_value(cdt, cdn, "duration_hours", hours).then(() => update_time_totals(frm));
}

frappe.ui.form.on("Service Report Time Entry", {
  time_entries_add(frm) {
    toggle_time_totals(frm);
  },
  time_entries_remove(frm) {
    toggle_time_totals(frm);
    if (!(frm.doc.time_entries || []).length) {
      frm.set_value("labor_hours", 0);
      frm.set_value("travel_hours", 0);
      frm.set_value("total_hours", 0);
    } else update_time_totals(frm);
  },
  activity_type: update_time_entry,
  start_datetime: update_time_entry,
  end_datetime: update_time_entry,
});

frappe.ui.form.on("Service Report Test Tool", {
  test_equipment: update_tool_snapshot,
  used_on: update_tool_snapshot,
});

function update_tool_snapshot(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const selected = row.test_equipment;
    if (!selected) return;
    const asOf = (row.used_on || frm.doc.service_date || "").slice(0, 10);
    if (row.snapshot_for === selected && row.snapshot_as_of === asOf) return;
    if (row.snapshot_for !== selected) frappe.model.set_value(cdt, cdn, "snapshot_for", null);
    frappe.db.get_doc("Service Test Equipment", selected).then((tool) => {
      if (locals[cdt][cdn].test_equipment !== selected) return;
      const events = tool.maintenance_events || [];
      const latest = (type) => events
        .filter((event) => event.event_type === type && (!asOf || event.performed_on <= asOf))
        .sort((a, b) => (b.performed_on || "").localeCompare(a.performed_on || ""))[0];
      const calibration = latest("Calibration");
      const pm = latest("Preventive Maintenance");
      const hasHistory = (type) => events.some((event) => event.event_type === type);
      return Promise.all([
        frappe.model.set_value(cdt, cdn, "tool_name", tool.equipment_name),
        frappe.model.set_value(cdt, cdn, "calibration_due_date",
          calibration ? calibration.next_due_date : (hasHistory("Calibration") ? null : tool.calibration_due_date || null)),
        frappe.model.set_value(cdt, cdn, "pm_due_date",
          pm ? pm.next_due_date : (hasHistory("Preventive Maintenance") ? null : tool.pm_due_date || null)),
        frappe.model.set_value(cdt, cdn, "calibration_certificate", calibration?.certificate || null),
      ]).then(() => frm.refresh_field("test_tools"));
    });
}
