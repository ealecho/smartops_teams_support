import frappe
from frappe import _
from frappe.model.document import Document


class SmartOpsTeamsSupportSettings(Document):
    def before_save(self):
        if not self.get_password("webhook_secret", raise_exception=False):
            self.webhook_secret = frappe.generate_hash(length=40)

        seen = set()
        for row in self.channels:
            key = (row.team_id, row.channel_id)
            if key in seen:
                frappe.throw(_("Each Team and Channel pair may only be configured once"))
            seen.add(key)
