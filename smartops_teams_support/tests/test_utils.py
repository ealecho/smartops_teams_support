from unittest import TestCase

from smartops_teams_support.utils import parse_resource, safe_html, ticket_subject


class TestUtils(TestCase):
    def test_graph_resource_variants(self):
        self.assertEqual(
            parse_resource("teams('team')/channels('channel')/messages('message')"),
            ("team", "channel", "message"),
        )
        self.assertEqual(
            parse_resource("teams/team/channels/channel/messages/message"),
            ("team", "channel", "message"),
        )

    def test_message_html_is_plain_and_escaped(self):
        self.assertEqual(safe_html("<p>Hello <b>& welcome</b></p>"), "Hello &amp; welcome")

    def test_subject_is_bounded(self):
        self.assertEqual(len(ticket_subject({"body": {"content": "x" * 200}})), 120)
