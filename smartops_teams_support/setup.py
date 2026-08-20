from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install():
    create_custom_fields(
        {
            "HD Ticket": [
                {
                    "fieldname": "is_teams_ticket",
                    "label": "Teams Ticket",
                    "fieldtype": "Check",
                    "read_only": 1,
                    "hidden": 1,
                    "insert_after": "description",
                },
                {
                    "fieldname": "teams_team_id",
                    "label": "Teams Team ID",
                    "fieldtype": "Data",
                    "read_only": 1,
                    "hidden": 1,
                    "insert_after": "is_teams_ticket",
                },
                {
                    "fieldname": "teams_channel_id",
                    "label": "Teams Channel ID",
                    "fieldtype": "Data",
                    "read_only": 1,
                    "hidden": 1,
                    "insert_after": "teams_team_id",
                },
                {
                    "fieldname": "teams_root_message_id",
                    "label": "Teams Root Message ID",
                    "fieldtype": "Data",
                    "read_only": 1,
                    "hidden": 1,
                    "insert_after": "teams_channel_id",
                },
                {
                    "fieldname": "teams_thread_url",
                    "label": "Teams Thread",
                    "fieldtype": "Data",
                    "options": "URL",
                    "length": 1000,
                    "read_only": 1,
                    "insert_after": "teams_root_message_id",
                },
            ]
        },
        update=True,
    )
