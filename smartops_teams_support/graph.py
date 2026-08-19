import time
from datetime import timedelta
from urllib.parse import quote, urlencode

import frappe
import requests
from frappe.utils import add_to_date, get_datetime, get_url, now_datetime

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = "offline_access User.Read User.ReadBasic.All ChannelMessage.Read.All ChannelMessage.Send"
TOKEN_CACHE_KEY = "smartops_teams_support_access_token"
SETTINGS_DOCTYPE = "SmartOps Teams Support Settings"


def settings():
    return frappe.get_single(SETTINGS_DOCTYPE)


def redirect_uri():
    return get_url("/api/method/smartops_teams_support.api.oauth_callback")


def webhook_url():
    return get_url("/api/method/smartops_teams_support.api.graph_webhook")


def token_url(doc=None):
    doc = doc or settings()
    return f"https://login.microsoftonline.com/{doc.tenant_id}/oauth2/v2.0/token"


def authorization_url(state: str, challenge: str):
    doc = settings()
    query = urlencode(
        {
            "client_id": doc.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri(),
            "response_mode": "query",
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://login.microsoftonline.com/{doc.tenant_id}/oauth2/v2.0/authorize?{query}"


def exchange_code(code: str, verifier: str):
    doc = settings()
    response = requests.post(
        token_url(doc),
        data={
            "client_id": doc.client_id,
            "client_secret": doc.get_password("client_secret"),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(),
            "scope": SCOPES,
            "code_verifier": verifier,
        },
        timeout=20,
    )
    response.raise_for_status()
    save_tokens(doc, response.json())


def save_tokens(doc, payload: dict):
    if payload.get("refresh_token"):
        doc.refresh_token = payload["refresh_token"]
        doc.save(ignore_permissions=True)
    frappe.cache().set_value(
        TOKEN_CACHE_KEY,
        payload["access_token"],
        expires_in_sec=max(int(payload.get("expires_in", 3600)) - 60, 60),
    )


def access_token(force_refresh=False):
    if not force_refresh and (token := frappe.cache().get_value(TOKEN_CACHE_KEY)):
        return token.decode() if isinstance(token, bytes) else token

    doc = settings()
    refresh_token = doc.get_password("refresh_token", raise_exception=False)
    if not refresh_token:
        frappe.throw("Connect a Microsoft account in SmartOps Teams Support Settings")
    response = requests.post(
        token_url(doc),
        data={
            "client_id": doc.client_id,
            "client_secret": doc.get_password("client_secret"),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPES,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    save_tokens(doc, payload)
    return payload["access_token"]


def request(method: str, path: str, **kwargs):
    token = access_token()
    for attempt in range(3):
        response = requests.request(
            method,
            f"{GRAPH}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
            **kwargs,
        )
        if response.status_code == 401 and attempt == 0:
            frappe.cache().delete_value(TOKEN_CACHE_KEY)
            token = access_token(force_refresh=True)
            continue
        if response.status_code == 429 and attempt < 2:
            retry_after = response.headers.get("Retry-After", "1")
            time.sleep(min(int(retry_after) if retry_after.isdigit() else 1, 5))
            continue
        response.raise_for_status()
        return response.json() if response.content else {}
    response.raise_for_status()


def me():
    return request("GET", "/me?$select=id,displayName,mail,userPrincipalName")


def user(user_id: str):
    return request(
        "GET",
        f"/users/{quote(user_id, safe='')}?$select=id,displayName,mail,userPrincipalName",
    )


def notification_resource(resource: str):
    return request("GET", "/" + resource.lstrip("/"))


def message(team_id: str, channel_id: str, message_id: str):
    return request(
        "GET",
        f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}/messages/"
        f"{quote(message_id, safe='')}",
    )


def reply(team_id: str, channel_id: str, root_message_id: str, content: str):
    return request(
        "POST",
        f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}/messages/"
        f"{quote(root_message_id, safe='')}/replies",
        json={"body": {"contentType": "html", "content": content}},
    )


def subscribe(team_id: str, channel_id: str, subscription_id: str | None = None):
    expires = add_to_date(now_datetime(), days=2, hours=23, as_datetime=True)
    payload = {"expirationDateTime": expires.isoformat() + "Z"}
    if subscription_id:
        data = request("PATCH", f"/subscriptions/{subscription_id}", json=payload)
    else:
        doc = settings()
        payload.update(
            {
                "changeType": "created,updated",
                "notificationUrl": webhook_url(),
                "lifecycleNotificationUrl": webhook_url(),
                "resource": f"/teams/{team_id}/channels/{channel_id}/messages",
                "includeResourceData": False,
                "clientState": doc.get_password("webhook_secret"),
            }
        )
        data = request("POST", "/subscriptions", json=payload)
    return data["id"], data["expirationDateTime"]


def ensure_subscriptions():
    doc = settings()
    if not doc.enabled or not doc.get_password("refresh_token", raise_exception=False):
        return
    renew_before = now_datetime() + timedelta(hours=24)
    for channel in doc.channels:
        if not channel.enabled:
            continue
        expires_at = get_datetime(channel.expires_at) if channel.expires_at else None
        if channel.subscription_id and expires_at and expires_at > renew_before:
            continue
        try:
            subscription_id, expiry = subscribe(
                channel.team_id, channel.channel_id, channel.subscription_id
            )
        except requests.HTTPError as exc:
            if channel.subscription_id and exc.response is not None and exc.response.status_code == 404:
                subscription_id, expiry = subscribe(channel.team_id, channel.channel_id)
            else:
                frappe.log_error(title=f"Teams subscription failed: {channel.channel_id}")
                continue
        except Exception:
            frappe.log_error(title=f"Teams subscription failed: {channel.channel_id}")
            continue
        frappe.db.set_value(
            channel.doctype,
            channel.name,
            {"subscription_id": subscription_id, "expires_at": expiry},
            update_modified=False,
        )
