import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.pipeline_service import PipelineService


class _FakeQuery:
    def __init__(self, deals):
        self._deals = deals

    def filter_by(self, **_kwargs):
        return self

    def options(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._deals


class _FakeDeal:
    def __init__(self, value, stage=None, forecast_category='pipeline'):
        self.value = value
        self.stage = stage
        self.forecast_category = forecast_category

    def get_weighted_value(self):
        if self.stage:
            return float(self.value) * (self.stage.probability / 100.0)
        return 0.0


class TestPhase26PipelineForecast(unittest.TestCase):
    @staticmethod
    def _run_forecast(deals):
        fake_deal_model = type(
            'FakeDealModel',
            (),
            {
                'stage': object(),
                'query': _FakeQuery(deals),
            },
        )

        with patch('services.pipeline_service.Deal', fake_deal_model), patch(
            'services.pipeline_service.db.joinedload',
            lambda _field: None,
        ):
            return PipelineService.calculate_forecast(workspace_id=1)

    def test_calculate_forecast_rounds_and_sorts_stage_breakdown(self):
        prospecting = SimpleNamespace(name='Prospecting', order=2, probability=25)
        qualified = SimpleNamespace(name='Qualified', order=1, probability=50)

        deals = [
            _FakeDeal(value=99.99, stage=prospecting, forecast_category='pipeline'),
            _FakeDeal(value=200.00, stage=qualified, forecast_category='commit'),
        ]

        result = self._run_forecast(deals)

        self.assertEqual(result['total_deals'], 2)
        self.assertEqual(result['total_forecast'], 125.0)
        self.assertEqual(result['by_category']['pipeline'], 99.99)
        self.assertEqual(result['by_category']['commit'], 200.0)
        self.assertEqual(result['by_category']['best_case'], 0.0)

        self.assertEqual(
            [row['stage_name'] for row in result['by_stage']],
            ['Qualified', 'Prospecting'],
        )
        self.assertEqual(result['by_stage'][0]['weighted_value'], 100.0)
        self.assertEqual(result['by_stage'][1]['weighted_value'], 25.0)

    def test_calculate_forecast_handles_missing_stage_relation(self):
        deals = [
            _FakeDeal(value=50.0, stage=None, forecast_category='best_case'),
        ]

        result = self._run_forecast(deals)

        self.assertEqual(result['total_deals'], 1)
        self.assertEqual(result['total_forecast'], 0.0)
        self.assertEqual(result['by_category']['best_case'], 50.0)
        self.assertEqual(result['by_stage'][0]['stage_name'], 'Unknown')
        self.assertEqual(result['by_stage'][0]['stage_order'], 9999)
        self.assertEqual(result['by_stage'][0]['total_value'], 50.0)
        self.assertEqual(result['by_stage'][0]['weighted_value'], 0.0)


if __name__ == '__main__':
    unittest.main()
