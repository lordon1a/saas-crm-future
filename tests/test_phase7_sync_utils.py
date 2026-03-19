import unittest
import importlib.util

from services.email_tracking_service import EmailTrackingService


HAS_GOOGLE_CLIENT = importlib.util.find_spec('googleapiclient') is not None


class TestPhase7SyncUtils(unittest.TestCase):
    def test_extract_single_email(self):
        if not HAS_GOOGLE_CLIENT:
            self.skipTest('googleapiclient is not installed in current environment')
        from services.gmail_sync_service import GmailSyncService

        self.assertEqual(
            GmailSyncService._extract_email('Jane Doe <Jane@Example.com>'),
            'jane@example.com',
        )

    def test_extract_multiple_emails(self):
        if not HAS_GOOGLE_CLIENT:
            self.skipTest('googleapiclient is not installed in current environment')
        from services.gmail_sync_service import GmailSyncService

        emails = GmailSyncService._extract_emails(
            'Alice <alice@example.com>, bob@example.com, Carol <CAROL@example.com>'
        )
        self.assertEqual(
            emails,
            ['alice@example.com', 'bob@example.com', 'carol@example.com'],
        )

    def test_calendar_parse_datetime_value(self):
        if not HAS_GOOGLE_CLIENT:
            self.skipTest('googleapiclient is not installed in current environment')
        from services.calendar_sync_service import CalendarSyncService

        dt = CalendarSyncService._parse_datetime({'dateTime': '2026-03-17T10:30:00Z'})
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.day, 17)

    def test_calendar_parse_date_value(self):
        if not HAS_GOOGLE_CLIENT:
            self.skipTest('googleapiclient is not installed in current environment')
        from services.calendar_sync_service import CalendarSyncService

        dt = CalendarSyncService._parse_datetime({'date': '2026-03-17'})
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.day, 17)

    def test_tracking_pixel_inserted_before_body(self):
        html = '<html><body><p>Hello</p></body></html>'
        out = EmailTrackingService.add_tracking_pixel(html, 'abc123', 'https://crm.test')
        self.assertIn('https://crm.test/track/open/abc123', out)
        self.assertLess(out.index('/track/open/abc123'), out.lower().index('</body>'))

    def test_tracking_links_rewritten(self):
        html = '<a href="https://example.com/page">go</a> <a href="mailto:a@b.com">mail</a>'
        out = EmailTrackingService.rewrite_links(html, 'track123', 'https://crm.test')
        self.assertIn('/track/click/track123?url=https%3A//example.com/page', out)
        self.assertIn('href="mailto:a@b.com"', out)


if __name__ == '__main__':
    unittest.main()
