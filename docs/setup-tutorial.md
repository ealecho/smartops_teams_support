# Setup tutorial

This tutorial configures a two-way support channel:

```text
Customer staff in Teams ↔ SmartOps Teams Support ↔ ERP Champions in Helpdesk
```

Customer staff stay in Microsoft Teams. Support agents stay in Frappe Helpdesk. A new Teams channel post creates a ticket, Teams thread replies update that ticket, and public Helpdesk replies return to the original Teams thread.

## 1. Prerequisites

- A Frappe Cloud private bench running Frappe v15
- Frappe Helpdesk installed on the same site
- This app installed after Helpdesk
- A Microsoft Entra administrator
- A licensed Microsoft 365 support account that is a member of every Team and channel being mapped
- At least one active agent in each mapped Helpdesk team

Helpdesk and Frappe must be version-compatible. If Frappe Cloud reports an incompatible dependency, either update the bench within its current major version or pin Helpdesk to a revision that supports the installed Frappe version. Do not edit Helpdesk's dependency declaration to bypass the check.

On Frappe Cloud, add and deploy apps through the dashboard. Select the affected site so managed migrations run. Avoid running deployments or migrations over SSH; use SSH for read-only diagnostics unless Frappe Cloud Support instructs otherwise.

## 2. Install on Frappe Cloud

1. Open the site's private Bench Group.
2. Add `https://github.com/frappe/helpdesk`, using a branch compatible with the bench.
3. Add `https://github.com/ealecho/smartops_teams_support`, branch `main`.
4. Deploy the Bench Group and select the target site.
5. On the site's **Apps** page, install Helpdesk first.
6. Install **SmartOps Teams Support** second.

The app adds hidden Teams identifiers and a clickable Teams thread URL to `HD Ticket`. Managed site migration applies these fields and future schema updates.

## 3. Register the Microsoft Entra application

In the Microsoft Entra admin centre, open **Identity → Applications → App registrations → New registration**.

Use:

- Name: `SmartOps Teams Support`
- Account type: accounts in this organisational directory only
- Platform: **Web**
- Redirect URI:

```text
https://<your-site>/api/method/smartops_teams_support.api.oauth_callback
```

The URI must use HTTPS, must not have a trailing slash, and must be registered under **Web**, not SPA. `AADSTS900971: No reply address provided` means this Web redirect URI is missing from the Entra registration.

Copy the **Directory (tenant) ID** and **Application (client) ID** from Overview. Under **Certificates & secrets**, create a client secret and copy its **Value**, not its Secret ID. Never commit or paste the secret into logs, issues, or chat.

## 4. Grant Microsoft Graph permissions

Under **API permissions → Microsoft Graph → Delegated permissions**, add:

- `ChannelMessage.Read.All`
- `ChannelMessage.Send`
- `Channel.ReadBasic.All`
- `Team.ReadBasic.All`
- `User.ReadBasic.All`
- `User.Read`
- `offline_access`

Grant admin consent for the tenant. If permissions are added later, reconnect the Microsoft account so the replacement token includes them.

Application permissions are not needed for this integration. The connected account can only discover and synchronize Teams and channels it can access.

## 5. Connect Microsoft

Open **SmartOps Teams Support Settings** and enter:

- Enabled
- Tenant ID
- Client ID
- Client Secret
- Fallback Requester Email

The fallback requester is used only when Microsoft does not provide the Teams author's email. Use a real shared support address, not placeholder data.

Save and click **Connect Microsoft Account**. Complete sign-in using the licensed support account. Reload the settings page and verify the green message:

```text
Microsoft connected and verified as <account>
```

Connecting is normally a one-time operation. The encrypted refresh token maintains access. Reconnect when the indicator turns red, Microsoft consent is revoked, tenant token policy expires the connection, or the Entra credentials change.

## 6. Map support channels

Click **Fetch Support Channels**:

1. Select a Microsoft Team.
2. Select one or more channels.
3. Select the destination Helpdesk Team.
4. Add the channels and save.
5. Click **Sync Subscriptions**.

The app stores the Team and channel IDs automatically. Only channels visible to the connected Microsoft account appear.

Before testing, inspect every matching Helpdesk Assignment Rule. A round-robin rule must contain at least one active user. An empty Users table causes Helpdesk ticket creation to fail with `IndexError: list index out of range`. Add agents or disable the unused rule.

Microsoft limits Teams change-notification subscriptions to 60 minutes. The app requests 55 minutes and renews them every 30 minutes. Successful rows show a Subscription ID and expiry time.

## 7. End-to-end test

Post a new top-level Teams channel message from an account other than the connected support account:

```text
Invoice submission test E2E-001

Hello support,

I cannot submit invoice INV-TEST-001. The cost centre is already selected.

Please advise.
```

Verify:

1. One Helpdesk ticket is created in the mapped team.
2. The description shows the Teams author and an **Open thread in Teams** link.
3. A public Helpdesk agent reply appears under the original Teams post.
4. A reply inside that Teams thread appears on the existing ticket.
5. No second ticket is created for the thread reply.

Use a brand-new post for each retry. The app does not import history or replay notifications that previously failed.

## 8. Troubleshooting

### The settings page says Microsoft is not connected

The indicator performs a live Microsoft check; the displayed account name alone is not proof of a working connection. Click **Connect Microsoft Account** again. OAuth, connection-check, and subscription failures are recorded in Frappe **Error Log** without credentials.

### Sync Subscriptions does nothing

Confirm all three are true:

- Settings is enabled.
- The Microsoft indicator is green.
- The channel mapping row is enabled.

After syncing, the mapping must contain both **Subscription ID** and **Expires At**. Look for an Error Log named `Teams subscription failed: <channel-id>` if they remain empty.

### Teams message arrives but no ticket is created

Look for `Teams notification processing failed` in Frappe Error Log. Common causes are:

- the mapped Helpdesk assignment rule has no users;
- a site migration did not apply the latest custom-field schema;
- the connected account posted the message and it was ignored to prevent a reply loop;
- an older Helpdesk release has different ticket fields or hooks.

Use Frappe Cloud's deployment logs to confirm the managed migration completed. The Teams Thread field should be a Data field with length `1000`.

### Test message from the connected account is ignored

This is intentional. Outbound Helpdesk replies are posted through that account, so ignoring its messages prevents them from returning as new tickets. Test with a different Teams user.

### Useful Error Log titles

- `Microsoft account connection failed`
- `Microsoft connection check failed`
- `Teams subscription failed: <channel-id>`
- `Teams notification processing failed`
- `Teams reply failed: ticket <ticket-id>`

## 9. Supported scope

The current version supports new text/HTML channel posts, thread replies, message edits, and public agent replies. It does not import history or synchronize attachments, reactions, Adaptive Cards, deletions, or Helpdesk status changes.
