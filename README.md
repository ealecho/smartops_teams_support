# SmartOps Teams Support

Microsoft Teams channel integration for Frappe Helpdesk. New channel threads become Helpdesk tickets, channel replies become ticket communications, and agent replies return to the original Teams thread.

The app runs entirely inside Frappe: webhooks use whitelisted methods, work is queued through Frappe workers, subscriptions renew through the scheduler, and credentials are stored in encrypted Password fields.

## Requirements

- Frappe Framework v15
- Frappe Helpdesk (`frappe/helpdesk`, branch `main`)
- A Microsoft Entra Web app and a licensed support account that belongs to every configured Team/channel

## Install

For the complete Frappe Cloud and Microsoft Entra walkthrough, testing steps, and troubleshooting guide, see [Setup tutorial](docs/setup-tutorial.md).

```bash
bench get-app https://github.com/ealecho/smartops_teams_support
bench --site <site> install-app smartops_teams_support
bench --site <site> migrate
```

On Frappe Cloud, add Helpdesk branch `main` to the private bench and install it first. Then add this repository, deploy the bench update, and install the app on the site.

## Microsoft Entra configuration

Add these delegated Microsoft Graph permissions and grant admin consent:

- `ChannelMessage.Read.All`
- `ChannelMessage.Send`
- `User.ReadBasic.All`
- `Team.ReadBasic.All`
- `Channel.ReadBasic.All`
- `User.Read`
- `offline_access`

Use these URLs, replacing `<site-url>` with the site origin:

```text
Redirect URI: <site-url>/api/method/smartops_teams_support.api.oauth_callback
Webhook URL:  <site-url>/api/method/smartops_teams_support.api.graph_webhook
```

Open **SmartOps Teams Support Settings**, enter the Entra credentials, save, then use **Connect Microsoft Account**. After connection, use **Fetch Support Channels** to add mappings and **Sync Subscriptions**.

Connecting is normally a one-time step; the stored refresh token maintains access. Reconnect only when the settings indicator turns red, Microsoft consent is revoked, or tenant credential policy requires it. OAuth, connection-check, and subscription failures are recorded in Frappe **Error Log** without credentials.

## Scope

V1 synchronizes new text/HTML threads, replies, and edits. It does not import history or synchronize attachments, reactions, cards, deletions, or ticket status.
