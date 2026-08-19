import html
import frappe
import requests

from smartops_teams_support import graph
from smartops_teams_support.utils import parse_resource, safe_html, ticket_subject

LINK_DOCTYPE = "SmartOps Teams Message Link"
SETTINGS_DOCTYPE = "SmartOps Teams Support Settings"


def channel_mapping(team_id: str, channel_id: str):
    return frappe.db.get_value(
        "SmartOps Teams Channel",
        {
            "parent": SETTINGS_DOCTYPE,
            "parenttype": SETTINGS_DOCTYPE,
            "enabled": 1,
            "team_id": team_id,
            "channel_id": channel_id,
        },
        ["name", "team_id", "channel_id", "helpdesk_team"],
        as_dict=True,
    )


def message_link(team_id: str, channel_id: str, message_id: str):
    name = frappe.db.get_value(
        LINK_DOCTYPE,
        {"team_id": team_id, "channel_id": channel_id, "message_id": message_id},
    )
    return frappe.get_doc(LINK_DOCTYPE, name) if name else None


def root_link(team_id: str, channel_id: str, root_message_id: str):
    name = frappe.db.get_value(
        LINK_DOCTYPE,
        {
            "team_id": team_id,
            "channel_id": channel_id,
            "message_id": root_message_id,
            "direction": "Inbound",
        },
    )
    return frappe.get_doc(LINK_DOCTYPE, name) if name else None


def author(message: dict, fallback: str):
    sender = (message.get("from") or {}).get("user") or {}
    profile = {}
    if sender.get("id"):
        try:
            profile = graph.user(sender["id"])
        except requests.RequestException:
            frappe.log_error(title="Teams user profile lookup failed")
    return {
        "name": profile.get("displayName") or sender.get("displayName") or "Teams user",
        "email": profile.get("mail") or profile.get("userPrincipalName") or fallback,
    }


def rendered_message(message: dict, message_author: dict):
    content = safe_html(message.get("body", {}).get("content", ""))
    result = f"<p><strong>{html.escape(message_author['name'])}</strong> via Microsoft Teams</p><p>{content}</p>"
    if message.get("webUrl"):
        result += f'<p><a href="{html.escape(message["webUrl"], quote=True)}">Open thread in Teams</a></p>'
    return result


def create_root(mapping, message: dict, settings_doc):
    existing = message_link(mapping.team_id, mapping.channel_id, message["id"])
    if existing:
        return existing
    message_author = author(message, settings_doc.fallback_requester)
    description = rendered_message(message, message_author)
    ticket = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": ticket_subject(message),
            "description": description,
            "raised_by": message_author["email"],
            "agent_group": mapping.helpdesk_team or None,
            "is_teams_ticket": 1,
            "teams_team_id": mapping.team_id,
            "teams_channel_id": mapping.channel_id,
            "teams_root_message_id": message["id"],
            "teams_thread_url": message.get("webUrl"),
        }
    ).insert(ignore_permissions=True)
    return frappe.get_doc(
        {
            "doctype": LINK_DOCTYPE,
            "team_id": mapping.team_id,
            "channel_id": mapping.channel_id,
            "message_id": message["id"],
            "root_message_id": message["id"],
            "ticket": ticket.name,
            "direction": "Inbound",
            "status": "Sent",
        }
    ).insert(ignore_permissions=True)


def create_reply(mapping, message: dict, root_message_id: str, settings_doc):
    root = root_link(mapping.team_id, mapping.channel_id, root_message_id)
    if not root:
        create_root(mapping, graph.message(mapping.team_id, mapping.channel_id, root_message_id), settings_doc)
        root = root_link(mapping.team_id, mapping.channel_id, root_message_id)
    message_author = author(message, settings_doc.fallback_requester)
    communication = frappe.get_doc(
        {
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": "Chat",
            "sent_or_received": "Received",
            "subject": "Teams reply",
            "sender": message_author["email"],
            "content": rendered_message(message, message_author),
            "status": "Linked",
            "reference_doctype": "HD Ticket",
            "reference_name": root.ticket,
        }
    ).insert(ignore_permissions=True)
    frappe.get_doc(
        {
            "doctype": LINK_DOCTYPE,
            "team_id": mapping.team_id,
            "channel_id": mapping.channel_id,
            "message_id": message["id"],
            "root_message_id": root_message_id,
            "ticket": root.ticket,
            "communication": communication.name,
            "direction": "Inbound",
            "status": "Sent",
        }
    ).insert(ignore_permissions=True)


def update_message(link, message: dict, settings_doc):
    content = rendered_message(message, author(message, settings_doc.fallback_requester))
    if link.communication:
        frappe.db.set_value("Communication", link.communication, "content", content)
    elif link.message_id == link.root_message_id:
        frappe.db.set_value(
            "HD Ticket",
            link.ticket,
            {"subject": ticket_subject(message), "description": content},
        )


def handle_lifecycle(item: dict):
    channel = frappe.db.get_value(
        "SmartOps Teams Channel",
        {"subscription_id": item.get("subscriptionId")},
        ["name", "team_id", "channel_id"],
        as_dict=True,
    )
    if not channel:
        return
    subscription_id, expiry = graph.subscribe(channel.team_id, channel.channel_id)
    frappe.db.set_value(
        "SmartOps Teams Channel",
        channel.name,
        {"subscription_id": subscription_id, "expires_at": expiry},
        update_modified=False,
    )


def process_notification(item: dict, settings_doc):
    if item.get("lifecycleEvent") in {"subscriptionRemoved", "reauthorizationRequired"}:
        handle_lifecycle(item)
        return
    team_id, channel_id, resource_message_id = parse_resource(item.get("resource", ""))
    mapping = channel_mapping(team_id, channel_id)
    if not mapping:
        return
    message = graph.notification_resource(item["resource"])
    if message.get("messageType") not in (None, "message"):
        return
    sender = (message.get("from") or {}).get("user") or {}
    if sender.get("id") == settings_doc.connected_user_id:
        return
    message_id = (item.get("resourceData") or {}).get("id") or message.get("id") or resource_message_id
    message["id"] = message_id
    existing = message_link(team_id, channel_id, message_id)
    if existing:
        update_message(existing, message, settings_doc)
    elif message.get("replyToId"):
        create_reply(mapping, message, message["replyToId"], settings_doc)
    else:
        create_root(mapping, message, settings_doc)


def process_notifications(items: list[dict]):
    settings_doc = frappe.get_single(SETTINGS_DOCTYPE)
    if not settings_doc.enabled:
        return
    for item in items:
        try:
            process_notification(item, settings_doc)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Teams notification processing failed")
