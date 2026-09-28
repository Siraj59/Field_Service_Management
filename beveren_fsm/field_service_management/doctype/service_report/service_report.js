frappe.ui.form.on("Service Report", {
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
