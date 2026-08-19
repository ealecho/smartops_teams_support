import hashlib

import frappe
from frappe.model.document import Document


class SmartOpsTeamsMessageLink(Document):
    def autoname(self):
        source = f"{self.team_id}:{self.channel_id}:{self.message_id}"
        self.name = hashlib.sha256(source.encode()).hexdigest()

    def validate(self):
        if not self.communication:
            return
        duplicate = frappe.db.exists(
            self.doctype,
            {"communication": self.communication, "name": ["!=", self.name or ""]},
        )
        if duplicate:
            frappe.throw("A Teams message link already exists for this communication")
