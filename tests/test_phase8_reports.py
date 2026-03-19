import importlib.util
import unittest

from services.report_service import ReportService


HAS_OPENPYXL = importlib.util.find_spec('openpyxl') is not None
HAS_REPORTLAB = importlib.util.find_spec('reportlab') is not None


class TestPhase8Reports(unittest.TestCase):
    def test_custom_report_invalid_dimension(self):
        with self.assertRaises(ValueError):
            ReportService.run_custom_report(1, {'dimension': 'invalid', 'metric': 'count'})

    def test_custom_report_invalid_metric(self):
        with self.assertRaises(ValueError):
            ReportService.run_custom_report(1, {'dimension': 'stage', 'metric': 'invalid'})

    def test_excel_export_bytes(self):
        if not HAS_OPENPYXL:
            self.skipTest('openpyxl is not installed')

        payload = ReportService.export_excel('Test Report', {
            'generated_at': '2026-03-17T00:00:00',
            'data': {'rows': [{'dimension': 'A', 'value': 10}]}
        })
        self.assertIsInstance(payload, bytes)
        self.assertTrue(payload.startswith(b'PK'))

    def test_pdf_export_bytes(self):
        if not HAS_REPORTLAB:
            self.skipTest('reportlab is not installed')

        payload = ReportService.export_pdf('Test Report', {
            'generated_at': '2026-03-17T00:00:00',
            'data': {'rows': [{'dimension': 'A', 'value': 10}]}
        })
        self.assertIsInstance(payload, bytes)
        self.assertTrue(payload.startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
