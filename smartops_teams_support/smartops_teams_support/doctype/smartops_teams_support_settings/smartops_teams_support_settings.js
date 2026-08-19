frappe.ui.form.on("SmartOps Teams Support Settings", {
  refresh(frm) {
    if (frm.is_new()) return;

    frm.add_custom_button(__("Connect Microsoft Account"), async () => {
      const result = await frappe.call("smartops_teams_support.api.get_authorization_url");
      window.location.assign(result.message);
    });

    frm.add_custom_button(__("Sync Subscriptions"), async () => {
      await frappe.call("smartops_teams_support.api.sync_subscriptions");
      frappe.show_alert({ message: __("Subscription sync queued"), indicator: "green" });
    });
  },
});
