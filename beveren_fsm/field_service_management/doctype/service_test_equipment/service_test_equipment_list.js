frappe.listview_settings["Service Test Equipment"] = {
  add_fields: ["status", "calibration_required", "calibration_due_date", "pm_due_date"],
  get_indicator(doc) {
    if (doc.status !== "Active") return [__(doc.status), "red", `status,=,${doc.status}`];
    const today = frappe.datetime.get_today();
    const soon = frappe.datetime.add_days(today, 30);
    if ((doc.calibration_required && (!doc.calibration_due_date || doc.calibration_due_date < today))
      || (doc.pm_due_date && doc.pm_due_date < today)) {
      return [__("Attention Needed"), "red", "status,=,Active"];
    }
    if ((doc.calibration_required && doc.calibration_due_date <= soon)
      || (doc.pm_due_date && doc.pm_due_date <= soon)) {
      return [__("Due Within 30 Days"), "orange", "status,=,Active"];
    }
    return [__("Current"), "green", "status,=,Active"];
  },
};
