frappe.ui.form.on("SmartOps Teams Support Settings", {
  refresh(frm) {
    if (frm.is_new()) return;

    frappe
      .call("smartops_teams_support.api.get_connection_status")
      .then(({ message }) => {
        if (message.connected) {
          frm.set_intro(
            __("Microsoft connected and verified as {0}", [message.account]),
            "green"
          );
        } else {
          frm.set_intro(__("Microsoft not connected: {0}", [message.message]), "red");
        }
      });

    frm.add_custom_button(__("Connect Microsoft Account"), async () => {
      const result = await frappe.call("smartops_teams_support.api.get_authorization_url");
      window.location.assign(result.message);
    });

    frm.add_custom_button(__("Sync Subscriptions"), async () => {
      await frappe.call("smartops_teams_support.api.sync_subscriptions");
      frappe.show_alert({ message: __("Subscription sync queued"), indicator: "green" });
    });

    frm.add_custom_button(__("Fetch Support Channels"), async () => {
      const { message: teams } = await frappe.call(
        "smartops_teams_support.api.get_joined_teams"
      );
      if (!teams.length) {
        frappe.msgprint(__("The connected Microsoft account has no Teams."));
        return;
      }

      frappe.prompt(
        {
          fieldname: "team_id",
          fieldtype: "Select",
          label: __("Microsoft Team"),
          options: teams.map((team) => ({ label: team.displayName, value: team.id })),
          reqd: 1,
        },
        async ({ team_id }) => {
          const team = teams.find((item) => item.id === team_id);
          const { message: channels } = await frappe.call(
            "smartops_teams_support.api.get_team_channels",
            { team_id }
          );
          const existing = new Set((frm.doc.channels || []).map((row) => row.channel_id));
          const available = channels.filter((channel) => !existing.has(channel.id));
          if (!available.length) {
            frappe.msgprint(__("All accessible channels in this Team are already mapped."));
            return;
          }

          frappe.prompt(
            [
              {
                fieldname: "channel_ids",
                fieldtype: "MultiCheck",
                label: __("Channels"),
                options: available.map((channel) => ({
                  label: channel.displayName,
                  value: channel.id,
                })),
                columns: 2,
                reqd: 1,
              },
              {
                fieldname: "helpdesk_team",
                fieldtype: "Link",
                label: __("Helpdesk Team"),
                options: "HD Team",
                reqd: 1,
              },
            ],
            ({ channel_ids, helpdesk_team }) => {
              channel_ids.forEach((channel_id) => {
                const channel = available.find((item) => item.id === channel_id);
                frm.add_child("channels", {
                  team_name: team.displayName,
                  team_id,
                  channel_name: channel.displayName,
                  channel_id,
                  helpdesk_team,
                  enabled: 1,
                });
              });
              frm.refresh_field("channels");
              frappe.show_alert({
                message: __("Channels added. Save and sync subscriptions."),
                indicator: "green",
              });
            },
            __("Select Support Channels"),
            __("Add Channels")
          );
        },
        __("Fetch Support Channels"),
        __("Next")
      );
    });
  },
});
