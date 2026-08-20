import base64
import hashlib
import json
import secrets

import frappe
from werkzeug.wrappers import Response

from smartops_teams_support import graph

OAUTH_CACHE_PREFIX = "smartops_teams_support_oauth:"


@frappe.whitelist()
def get_authorization_url():
    frappe.only_for("System Manager")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    frappe.cache().set_value(
        OAUTH_CACHE_PREFIX + state,
        json.dumps({"verifier": verifier}),
        expires_in_sec=600,
    )
    return graph.authorization_url(state, challenge)


@frappe.whitelist(allow_guest=True)
def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        frappe.respond_as_web_page("Microsoft connection failed", error or "Missing OAuth response")
        return
    key = OAUTH_CACHE_PREFIX + state
    cached = frappe.cache().get_value(key)
    frappe.cache().delete_value(key)
    if not cached:
        frappe.respond_as_web_page("Microsoft connection failed", "The request is invalid or expired")
        return
    values = json.loads(cached.decode() if isinstance(cached, bytes) else cached)
    try:
        graph.exchange_code(code, values["verifier"])
        profile = graph.me()
        doc = frappe.get_single("SmartOps Teams Support Settings")
        doc.connected_user_id = profile["id"]
        doc.connected_user_name = profile.get("displayName") or profile.get("userPrincipalName")
        doc.save(ignore_permissions=True)
    except Exception as exc:
        graph.log_microsoft_error("Microsoft account connection failed", exc)
        frappe.respond_as_web_page(
            "Microsoft connection failed",
            "The error was recorded in Frappe Error Log. Return to SmartOps settings and try again.",
        )
        return
    frappe.respond_as_web_page("Microsoft account connected", "You can close this window.", success=True)


@frappe.whitelist()
def sync_subscriptions():
    frappe.only_for("System Manager")
    doc = frappe.get_single("SmartOps Teams Support Settings")
    if not doc.enabled:
        frappe.throw("Enable SmartOps Teams Support before syncing subscriptions")
    if not doc.get_password("refresh_token", raise_exception=False):
        frappe.throw("Microsoft is not connected. Use Connect Microsoft Account first")
    frappe.enqueue(
        "smartops_teams_support.graph.ensure_subscriptions",
        queue="short",
        enqueue_after_commit=True,
    )


@frappe.whitelist()
def get_connection_status():
    frappe.only_for("System Manager")
    doc = frappe.get_single("SmartOps Teams Support Settings")
    if not doc.get_password("refresh_token", raise_exception=False):
        return {"connected": False, "message": "No Microsoft refresh token is stored"}
    try:
        profile = graph.me()
    except Exception as exc:
        graph.log_microsoft_error("Microsoft connection check failed", exc)
        return {"connected": False, "message": "Microsoft rejected the saved connection"}
    return {
        "connected": True,
        "account": profile.get("displayName") or profile.get("userPrincipalName"),
    }


@frappe.whitelist()
def get_joined_teams():
    frappe.only_for("System Manager")
    return graph.joined_teams()


@frappe.whitelist()
def get_team_channels(team_id: str):
    frappe.only_for("System Manager")
    if not team_id:
        frappe.throw("Team is required")
    return graph.team_channels(team_id)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def graph_webhook():
    validation_token = frappe.form_dict.get("validationToken")
    if validation_token is not None:
        return Response(validation_token, status=200, content_type="text/plain")

    payload = frappe.request.get_json(silent=True) or {}
    doc = frappe.get_single("SmartOps Teams Support Settings")
    expected = doc.get_password("webhook_secret", raise_exception=False) or ""
    if not expected:
        return Response("", status=202, content_type="text/plain")
    accepted = [
        item
        for item in payload.get("value", [])
        if secrets.compare_digest(str(item.get("clientState", "")), expected)
    ]
    if accepted:
        frappe.enqueue(
            "smartops_teams_support.sync.process_notifications",
            queue="short",
            items=accepted,
        )
    return Response("", status=202, content_type="text/plain")
