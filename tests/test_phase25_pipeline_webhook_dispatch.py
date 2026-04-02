import unittest
from unittest.mock import patch

from services.pipeline_service import PipelineService


class TestPhase25PipelineWebhookDispatch(unittest.TestCase):
    @patch("services.webhook_service.WebhookService.dispatch_event")
    def test_emit_webhook_event_dispatches_via_webhook_service(self, mock_dispatch):
        payload = {"deal_id": 42, "name": "Deal A"}

        PipelineService._emit_webhook_event(7, "deal.updated", payload)

        mock_dispatch.assert_called_once_with(7, "deal.updated", payload)

    @patch("services.webhook_service.WebhookService.dispatch_event", side_effect=RuntimeError("boom"))
    def test_emit_webhook_event_is_non_blocking_on_dispatch_error(self, _mock_dispatch):
        # Should not raise even when webhook transport fails.
        PipelineService._emit_webhook_event(7, "deal.updated", {"deal_id": 42})
