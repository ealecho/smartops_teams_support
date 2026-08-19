app_name = "smartops_teams_support"
app_title = "SmartOps Teams Support"
app_publisher = "ERP Champions"
app_description = "Microsoft Teams channel integration for Frappe Helpdesk"
app_email = ""
app_license = "MIT"

required_apps = ["helpdesk"]

after_install = "smartops_teams_support.setup.install"
after_migrate = "smartops_teams_support.setup.install"

override_doctype_class = {
    "HD Ticket": "smartops_teams_support.ticket.TeamsHDTicket",
}

scheduler_events = {
    "hourly": ["smartops_teams_support.graph.ensure_subscriptions"],
}
