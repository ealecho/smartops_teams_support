import html

import frappe
from frappe import _
from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import HDTicket
from helpdesk.utils import is_agent

from smartops_teams_support import graph
from smartops_teams_support.sync import LINK_DOCTYPE
from smartops_teams_support.utils import safe_html


class TeamsHDTicket(HDTicket):
    @frappe.whitelist()
    def reply_via_agent(
        self,
        message: str,
        from_email: dict | None = None,
        to: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        attachments: list[str] = [],
    ):
        if not self.is_teams_ticket:
            return super().reply_via_agent(message, from_email, to, cc, bcc, attachments)
        if not is_agent():
            frappe.throw(_("You are not permitted to reply as an agent"), frappe.PermissionError)
        if attachments:
            frappe.throw(_("Attachments are not supported for Teams tickets yet"))
        if not frappe.db.get_single_value("SmartOps Teams Support Settings", "enabled"):
            frappe.throw(_("SmartOps Teams Support is disabled"))

        communication = frappe.get_doc(
            {
                "doctype": "Communication",
                "communication_type": "Communication",
                "communication_medium": "Chat",
                "sent_or_received": "Sent",
                "subject": f"Re: {self.subject}",
                "sender": frappe.session.user,
                "recipients": self.raised_by,
                "content": message,
                "status": "Linked",
                "reference_doctype": "HD Ticket",
                "reference_name": self.name,
            }
        ).insert(ignore_permissions=True)
        link = frappe.get_doc(
            {
                "doctype": LINK_DOCTYPE,
                "team_id": self.teams_team_id,
                "channel_id": self.teams_channel_id,
                "message_id": f"pending:{communication.name}",
                "root_message_id": self.teams_root_message_id,
                "ticket": self.name,
                "communication": communication.name,
                "direction": "Outbound",
                "status": "Pending",
            }
        ).insert(ignore_permissions=True)
        frappe.enqueue(
            "smartops_teams_support.ticket.send_to_teams",
            queue="short",
            enqueue_after_commit=True,
            link_name=link.name,
        )
        return communication.name


def send_to_teams(link_name: str):
    link = frappe.get_doc(LINK_DOCTYPE, link_name)
    if link.status == "Sent":
        return
    communication = frappe.get_doc("Communication", link.communication)
    agent_name = frappe.db.get_value("User", communication.sender, "full_name") or communication.sender
    content = (
        f"<p><strong>Support – {html.escape(agent_name)}</strong></p>"
        f"<p>{safe_html(communication.content)}</p>"
    )
    try:
        response = graph.reply(link.team_id, link.channel_id, link.root_message_id, content)
        frappe.db.set_value(
            LINK_DOCTYPE,
            link.name,
            {"message_id": response["id"], "status": "Sent", "error": ""},
        )
    except Exception as exc:
        frappe.db.set_value(
            LINK_DOCTYPE,
            link.name,
            {"status": "Failed", "error": str(exc)[:500]},
        )
        frappe.log_error(title=f"Teams reply failed: ticket {link.ticket}")
        frappe.get_doc(
            {
                "doctype": "HD Ticket Comment",
                "reference_ticket": link.ticket,
                "commented_by": "Administrator",
                "content": _("The latest reply could not be delivered to Microsoft Teams. Check the Error Log."),
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
        raise
