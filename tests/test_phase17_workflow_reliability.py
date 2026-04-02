import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.workflow_service import WorkflowService


class _DummyComparator:
    def __eq__(self, _other):
        return self

    def __ne__(self, _other):
        return self

    def __le__(self, _other):
        return self

    def __lt__(self, _other):
        return self

    def __ge__(self, _other):
        return self

    def in_(self, _values):
        return self


class _FakeQueueQuery:
    def __init__(self, items, claimable_ids):
        self._items = list(items)
        self._claimable_ids = set(claimable_ids)
        self._filter_by_kwargs = None

    def filter(self, *_args, **_kwargs):
        self._filter_by_kwargs = None
        return self

    def limit(self, _count):
        return self

    def all(self):
        return list(self._items)

    def filter_by(self, **kwargs):
        self._filter_by_kwargs = kwargs
        return self

    def update(self, _values, synchronize_session=False):
        _ = synchronize_session
        if not self._filter_by_kwargs:
            return 0

        item_id = self._filter_by_kwargs.get('id')
        status = self._filter_by_kwargs.get('status')
        if status == 'pending' and item_id in self._claimable_ids:
            return 1
        return 0


class TestPhase17WorkflowReliability(unittest.TestCase):
    def test_queue_delayed_action_deduplicates_same_minute_bucket(self):
        existing_item = SimpleNamespace(id=55, scheduled_at=datetime.utcnow())

        fake_query = MagicMock()
        fake_query.filter_by.return_value.filter.return_value.first.return_value = existing_item

        fake_queue_model = type(
            'FakeQueueModel',
            (),
            {
                'query': fake_query,
                'status': _DummyComparator(),
                'scheduled_at': _DummyComparator(),
            },
        )

        db_mock = SimpleNamespace(session=MagicMock())
        action = SimpleNamespace(id=31, workflow_id=9, workspace_id=77, delay_minutes=10)
        entity = type('ContactEntity', (), {'id': 101})()

        with patch('models_crm.WorkflowExecutionQueue', fake_queue_model), patch('models.db', db_mock):
            result = WorkflowService._queue_delayed_action(action, entity, {})

        self.assertEqual(result.get('status'), 'deduplicated')
        self.assertEqual(result.get('queue_item_id'), 55)
        db_mock.session.add.assert_not_called()
        db_mock.session.commit.assert_not_called()

    def test_queue_delayed_action_creates_queue_item_when_no_duplicate(self):
        fake_query = MagicMock()
        fake_query.filter_by.return_value.filter.return_value.first.return_value = None

        created_items = []

        class FakeQueueModel:
            query = fake_query
            status = _DummyComparator()
            scheduled_at = _DummyComparator()

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.id = 999
                created_items.append(self)

        db_mock = SimpleNamespace(session=MagicMock())
        action = SimpleNamespace(id=32, workflow_id=11, workspace_id=88, delay_minutes=3)
        entity = type('DealEntity', (), {'id': 202})()

        with patch('models_crm.WorkflowExecutionQueue', FakeQueueModel), patch('models.db', db_mock):
            result = WorkflowService._queue_delayed_action(action, entity, {})

        self.assertEqual(result.get('status'), 'queued')
        self.assertEqual(result.get('queue_item_id'), 999)
        self.assertEqual(len(created_items), 1)
        db_mock.session.add.assert_called_once_with(created_items[0])
        db_mock.session.commit.assert_called_once()

    def test_process_queue_claims_pending_items_before_execution(self):
        item_a = SimpleNamespace(
            id=1,
            action_id=101,
            entity_type='contact',
            entity_id=5001,
            status='pending',
            executed_at=None,
        )
        item_b = SimpleNamespace(
            id=2,
            action_id=102,
            entity_type='contact',
            entity_id=5002,
            status='pending',
            executed_at=None,
        )

        queue_query = _FakeQueueQuery(items=[item_a, item_b], claimable_ids={1})
        fake_queue_model = type(
            'FakeQueueModel',
            (),
            {
                'query': queue_query,
                'status': _DummyComparator(),
                'scheduled_at': _DummyComparator(),
            },
        )

        action_get = MagicMock(side_effect=lambda action_id: SimpleNamespace(id=action_id))
        fake_action_model = type(
            'FakeActionModel',
            (),
            {
                'query': SimpleNamespace(get=action_get),
            },
        )

        db_mock = SimpleNamespace(session=MagicMock())

        with patch('models_crm.WorkflowExecutionQueue', fake_queue_model), patch(
            'models_crm.WorkflowAction', fake_action_model
        ), patch('models.db', db_mock), patch.object(
            WorkflowService, '_load_entity', return_value=SimpleNamespace(id=5001)
        ) as load_entity_mock, patch.object(
            WorkflowService, 'execute_action', return_value={'status': 'success'}
        ) as execute_action_mock:
            processed = WorkflowService.process_queue()

        self.assertEqual(processed, 1)
        self.assertEqual(item_a.status, 'executed')
        self.assertIsNotNone(item_a.executed_at)
        self.assertEqual(item_b.status, 'pending')
        self.assertEqual(action_get.call_count, 1)
        self.assertEqual(load_entity_mock.call_count, 1)
        execute_action_mock.assert_called_once()

    def test_close_date_trigger_skips_when_already_triggered_today(self):
        workflow = SimpleNamespace(id=81, workspace_id=42)
        deal = SimpleNamespace(id=991, workspace_id=42, closedate=datetime.utcnow() + timedelta(days=3))

        workflow_filter_result = MagicMock()
        workflow_filter_result.all.side_effect = [[], [], [workflow]]
        workflow_query = MagicMock()
        workflow_query.filter.return_value = workflow_filter_result

        fake_workflow_model = type(
            'FakeWorkflowModel',
            (),
            {
                'trigger_type': _DummyComparator(),
                'is_active': _DummyComparator(),
                'query': workflow_query,
            },
        )

        deal_query = MagicMock()
        deal_query.filter.return_value.limit.return_value.all.return_value = [deal]
        fake_deal_model = type(
            'FakeDealModel',
            (),
            {
                'workspace_id': _DummyComparator(),
                'closedate': _DummyComparator(),
                'query': deal_query,
            },
        )

        execution_query = MagicMock()
        execution_query.filter_by.return_value.filter.return_value.first.return_value = SimpleNamespace(id=11)
        fake_execution_model = type(
            'FakeExecutionModel',
            (),
            {
                'started_at': _DummyComparator(),
                'query': execution_query,
            },
        )

        fake_contact_model = type('FakeContactModel', (), {})
        db_mock = SimpleNamespace(session=MagicMock())

        with patch('models_crm.WorkflowAutomation', fake_workflow_model), patch(
            'models_crm.Deal', fake_deal_model
        ), patch('models_crm.Contact', fake_contact_model), patch(
            'models_crm.WorkflowExecution', fake_execution_model
        ), patch('models.db', db_mock), patch.object(
            WorkflowService, 'trigger_event'
        ) as trigger_event_mock:
            WorkflowService.check_time_based_triggers()

        trigger_event_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
