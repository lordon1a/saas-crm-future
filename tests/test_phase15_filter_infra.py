import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from routes.contacts import _enforce_filter_rate_limit, contacts_bp
from services.filter_cache_service import FilterCacheService
from services.filter_validation_service import FilterValidationService
from services.saved_filter_service import SavedFilterService
from utils.rate_limiter import (
    clear_rate_limiter_state,
    filter_rate_limit,
    get_rate_limit_status,
)


class TestPhase15FilterCacheService(unittest.TestCase):
    def setUp(self):
        FilterCacheService.clear_all()

    def tearDown(self):
        FilterCacheService.clear_all()

    def test_cache_key_is_deterministic(self):
        filters = {'rules': [{'field': 'name', 'operator': 'contains', 'value': 'acme'}]}

        key_a = FilterCacheService.generate_cache_key(
            'company',
            filters,
            10,
            page=1,
            per_page=20,
            sort_by='name',
            sort_order='asc',
        )
        key_b = FilterCacheService.generate_cache_key(
            'company',
            filters,
            10,
            page=1,
            per_page=20,
            sort_by='name',
            sort_order='asc',
        )

        self.assertEqual(key_a, key_b)

    def test_cache_key_changes_with_pagination_and_sort(self):
        filters = {'rules': [{'field': 'name', 'operator': 'contains', 'value': 'acme'}]}

        page_1_key = FilterCacheService.generate_cache_key('company', filters, 10, page=1, per_page=20)
        page_2_key = FilterCacheService.generate_cache_key('company', filters, 10, page=2, per_page=20)
        sort_key = FilterCacheService.generate_cache_key(
            'company',
            filters,
            10,
            page=1,
            per_page=20,
            sort_by='created_at',
            sort_order='desc',
        )

        self.assertNotEqual(page_1_key, page_2_key)
        self.assertNotEqual(page_1_key, sort_key)

    def test_set_get_and_invalidate_cache(self):
        cache_key = FilterCacheService.generate_cache_key('contact', {'a': 1}, 99, page=1)
        results = [{'id': 1, 'name': 'Jane'}]
        pagination = {'page': 1, 'total': 1}

        FilterCacheService.set_cached_results(
            cache_key=cache_key,
            results=results,
            pagination=pagination,
            ttl=60,
            entity_type='contact',
            workspace_id=99,
        )

        cached = FilterCacheService.get_cached_results(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached[0], results)
        self.assertEqual(cached[1], pagination)

        removed = FilterCacheService.invalidate_cache('contact', 99)
        self.assertEqual(removed, 1)
        self.assertIsNone(FilterCacheService.get_cached_results(cache_key))

    def test_expired_cache_is_removed(self):
        cache_key = FilterCacheService.generate_cache_key('contact', {'a': 1}, 77)
        FilterCacheService.set_cached_results(
            cache_key=cache_key,
            results=[{'id': 1}],
            pagination={'page': 1},
            ttl=60,
            entity_type='contact',
            workspace_id=77,
        )

        # Force expiry without sleeping by moving expiration time into the past.
        FilterCacheService._cache[cache_key]['expires_at'] = FilterCacheService._now() - timedelta(seconds=1)

        self.assertIsNone(FilterCacheService.get_cached_results(cache_key))


class TestPhase15RateLimiter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'test-secret'

    def setUp(self):
        clear_rate_limiter_state()

    def tearDown(self):
        clear_rate_limiter_state()

    def test_status_consumes_until_limit(self):
        with self.app.test_request_context('/any'):
            counts = []
            for _ in range(4):
                current, max_count, window = get_rate_limit_status(42, max_requests=3, window_seconds=60)
                counts.append((current, max_count, window))

            self.assertEqual(counts[0], (0, 3, 60))
            self.assertEqual(counts[1], (1, 3, 60))
            self.assertEqual(counts[2], (2, 3, 60))
            self.assertEqual(counts[3], (3, 3, 60))

    def test_workspace_fallback_key(self):
        with self.app.test_request_context('/fallback'):
            from flask import session

            session['workspace_id'] = 321
            c1, _, _ = get_rate_limit_status(None, max_requests=2, window_seconds=60)
            c2, _, _ = get_rate_limit_status(None, max_requests=2, window_seconds=60)
            c3, _, _ = get_rate_limit_status(None, max_requests=2, window_seconds=60)

            self.assertEqual(c1, 0)
            self.assertEqual(c2, 1)
            self.assertEqual(c3, 2)

    def test_decorator_returns_429_after_limit(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.secret_key = 'decorator-secret'

        @app.route('/limited')
        @filter_rate_limit(max_requests=2, window_seconds=60)
        def limited_endpoint():
            return {'ok': True}, 200

        with app.test_client() as client:
            first = client.get('/limited')
            second = client.get('/limited')
            third = client.get('/limited')

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(third.status_code, 429)
            payload = third.get_json()
            self.assertIn('error', payload)
            self.assertEqual(payload.get('retry_after'), 60)
            self.assertEqual(third.headers.get('Retry-After'), '60')


class TestPhase15ContactsRateLimitHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'contacts-helper-secret'

    def test_helper_allows_request_when_under_limit(self):
        with self.app.test_request_context('/contacts'):
            with patch('routes.contacts.get_rate_limit_status', return_value=(1, 5, 60)):
                result = _enforce_filter_rate_limit(
                    user_id=42,
                    max_requests=5,
                    window_seconds=60,
                )
                self.assertIsNone(result)

    def test_helper_returns_429_payload_when_limit_exceeded(self):
        with self.app.test_request_context('/contacts'):
            with patch('routes.contacts.get_rate_limit_status', return_value=(5, 5, 60)):
                result = _enforce_filter_rate_limit(
                    user_id=42,
                    max_requests=5,
                    window_seconds=60,
                )

                self.assertIsNotNone(result)
                response, status = result
                self.assertEqual(status, 429)
                payload = response.get_json()
                self.assertEqual(payload.get('retry_after'), 60)
                self.assertIn('Rate limit exceeded', payload.get('error', ''))
                self.assertEqual(response.headers.get('Retry-After'), '60')


class TestPhase15ContactsRateLimitIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'contacts-integration-secret'
        cls.app.register_blueprint(contacts_bp)

    def test_contacts_quick_filter_returns_429_when_rate_limited(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(60, 60, 60)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/contacts?quick_filter=today_tasks')

                self.assertEqual(response.status_code, 429)
                payload = response.get_json()
                self.assertEqual(payload.get('retry_after'), 60)
                self.assertIn('Rate limit exceeded', payload.get('error', ''))
                self.assertEqual(response.headers.get('Retry-After'), '60')

    def test_contacts_export_post_returns_429_when_rate_limited(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(20, 20, 60)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.post('/api/v1/contacts/export', json={'filters': {'filters': []}})

                self.assertEqual(response.status_code, 429)
                payload = response.get_json()
                self.assertEqual(payload.get('retry_after'), 60)
                self.assertIn('Rate limit exceeded', payload.get('error', ''))
                self.assertEqual(response.headers.get('Retry-After'), '60')

    def test_companies_quick_filter_returns_429_when_rate_limited(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(60, 60, 60)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/companies?quick_filter=stalled')

                self.assertEqual(response.status_code, 429)
                payload = response.get_json()
                self.assertEqual(payload.get('retry_after'), 60)
                self.assertIn('Rate limit exceeded', payload.get('error', ''))
                self.assertEqual(response.headers.get('Retry-After'), '60')

    def test_companies_export_filtered_returns_429_when_rate_limited(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(20, 20, 60)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.post('/api/v1/companies/export-filtered', json={'filters': {'filters': []}})

                self.assertEqual(response.status_code, 429)
                payload = response.get_json()
                self.assertEqual(payload.get('retry_after'), 60)
                self.assertIn('Rate limit exceeded', payload.get('error', ''))
                self.assertEqual(response.headers.get('Retry-After'), '60')

    def test_contacts_quick_filter_sanitizes_invalid_pagination(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(0, 60, 60)), \
            patch('services.filter_service.FilterService.evaluate_quick_filter', return_value={'filters': []}), \
            patch('services.filter_validation_service.FilterValidationService.validate_filters', return_value=(True, None)), \
            patch('services.filter_validation_service.FilterValidationService.check_workspace_access', return_value=True), \
            patch(
                'services.filter_service.FilterService.apply_filters',
                return_value=([], {'page': 1, 'per_page': 50, 'total': 0, 'pages': 0}),
            ) as apply_filters_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/contacts?quick_filter=today_tasks&page=0&per_page=-10&limit=-5')

            self.assertEqual(response.status_code, 200)
            kwargs = apply_filters_mock.call_args.kwargs
            self.assertEqual(kwargs.get('page'), 1)
            self.assertEqual(kwargs.get('per_page'), 50)

    def test_companies_quick_filter_sanitizes_invalid_pagination(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(0, 60, 60)), \
            patch('services.filter_service.FilterService.evaluate_quick_filter', return_value={'filters': []}), \
            patch('services.filter_validation_service.FilterValidationService.validate_filters', return_value=(True, None)), \
            patch('services.filter_validation_service.FilterValidationService.check_workspace_access', return_value=True), \
            patch(
                'services.filter_service.FilterService.apply_filters',
                return_value=([], {'page': 1, 'per_page': 50, 'total': 0, 'pages': 0}),
            ) as apply_filters_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/companies?quick_filter=stalled&page=-2&per_page=0')

            self.assertEqual(response.status_code, 200)
            kwargs = apply_filters_mock.call_args.kwargs
            self.assertEqual(kwargs.get('page'), 1)
            self.assertEqual(kwargs.get('per_page'), 50)


class TestPhase15FilterValidationService(unittest.TestCase):
    def test_accepts_valid_flat_filters(self):
        is_valid, error = FilterValidationService.validate_filters(
            {
                'filters': [
                    {'field': 'first_name', 'operator': 'contains', 'value': 'ali'},
                    {'field': 'lead_score', 'operator': 'greater_than', 'value': 50},
                ]
            },
            'contact',
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_rejects_unsupported_operator(self):
        is_valid, error = FilterValidationService.validate_filters(
            {'filters': [{'field': 'first_name', 'operator': 'regex', 'value': '^a'}]},
            'contact',
        )
        self.assertFalse(is_valid)
        self.assertIn('unsupported operator', error)

    def test_rejects_invalid_between_value(self):
        is_valid, error = FilterValidationService.validate_filters(
            {'filters': [{'field': 'created_at', 'operator': 'between', 'value': ['2026-01-01']}]},
            'contact',
        )
        self.assertFalse(is_valid)
        self.assertIn('exactly 2 values', error)

    def test_rejects_too_many_filters(self):
        too_many = [
            {'field': 'first_name', 'operator': 'contains', 'value': str(i)}
            for i in range(FilterValidationService.MAX_TOP_LEVEL_FILTERS + 1)
        ]
        is_valid, error = FilterValidationService.validate_filters({'filters': too_many}, 'contact')
        self.assertFalse(is_valid)
        self.assertIn('Too many filters', error)

    def test_accepts_grouped_filters(self):
        is_valid, error = FilterValidationService.validate_filters(
            {
                'groupLogic': 'OR',
                'groups': [
                    {
                        'logic': 'AND',
                        'conditions': [
                            {'field': 'industry', 'operator': 'equals', 'value': 'SaaS'},
                            {'field': 'size', 'operator': 'in', 'value': ['11-50', '51-200']},
                        ],
                    }
                ],
            },
            'company',
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class TestPhase15FilterValidationIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'filter-validation-integration-secret'
        cls.app.register_blueprint(contacts_bp)

    def test_contacts_export_filtered_returns_400_for_invalid_filter_operator(self):
        with patch('routes.contacts.get_rate_limit_status', return_value=(0, 20, 60)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/contacts/export-filtered',
                    json={
                        'filters': {
                            'filters': [
                                {'field': 'first_name', 'operator': 'invalid_op', 'value': 'ali'}
                            ]
                        }
                    },
                )

                self.assertEqual(response.status_code, 400)
                payload = response.get_json()
                self.assertIn('unsupported operator', payload.get('error', ''))


class TestPhase15SavedFilterValidationIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'saved-filter-validation-secret'
        cls.app.register_blueprint(contacts_bp)

    def test_create_saved_filter_returns_400_for_invalid_filter_config(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 77

            response = client.post(
                '/api/v1/saved-filters',
                json={
                    'name': 'Bad Filter',
                    'entity_type': 'contact',
                    'filter_config': {
                        'filters': [
                            {'field': 'first_name', 'operator': 'invalid_op', 'value': 'ali'}
                        ]
                    },
                    'is_shared': False,
                },
            )

            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertIn('unsupported operator', payload.get('error', ''))


class TestPhase15SavedFilterServiceValidation(unittest.TestCase):
    def test_create_filter_rejects_invalid_config_before_db_query(self):
        with patch('services.saved_filter_service.db.session.query') as query_mock:
            with self.assertRaises(ValueError) as context:
                SavedFilterService.create_filter(
                    workspace_id=77,
                    user_id=99,
                    name='Invalid Filter',
                    entity_type='contact',
                    filter_config={
                        'filters': [
                            {'field': 'first_name', 'operator': 'invalid_op', 'value': 'ali'}
                        ]
                    },
                )

        self.assertIn('unsupported operator', str(context.exception))
        query_mock.assert_not_called()

    def test_create_user_defined_filter_rejects_invalid_config(self):
        with patch('services.saved_filter_service.db.session.add') as add_mock:
            with self.assertRaises(ValueError) as context:
                SavedFilterService.create_user_defined_filter(
                    workspace_id=77,
                    user_id=99,
                    user_name='Test User',
                    name='Invalid User Filter',
                    description=None,
                    entity_type='company',
                    filter_config={
                        'filters': [
                            {'field': 'name', 'operator': 'invalid_op', 'value': 'Acme'}
                        ]
                    },
                )

        self.assertIn('unsupported operator', str(context.exception))
        add_mock.assert_not_called()


class TestPhase15SavedFilterEndpointsCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'saved-filter-endpoint-compat-secret'
        cls.app.register_blueprint(contacts_bp)

    def test_get_saved_filters_includes_user_and_shared_collections(self):
        own_filter = SimpleNamespace(
            id=1,
            name='My Filter',
            entity_type='contact',
            filter_config='{"filters": []}',
            is_shared=False,
            user_id=99,
            created_at=datetime(2026, 1, 1),
            updated_at=None,
        )
        shared_filter = SimpleNamespace(
            id=2,
            name='Shared Filter',
            entity_type='contact',
            filter_config='{"filters": []}',
            is_shared=True,
            user_id=10,
            created_at=datetime(2026, 1, 2),
            updated_at=None,
        )

        with patch(
            'services.saved_filter_service.SavedFilterService.get_user_filters',
            return_value=[own_filter, shared_filter],
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/saved-filters?entity_type=contact')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload.get('filters', [])), 2)
        self.assertEqual(len(payload.get('user_filters', [])), 1)
        self.assertEqual(len(payload.get('shared_filters', [])), 1)

    def test_delete_saved_filter_returns_404_for_not_found_error(self):
        with patch(
            'services.saved_filter_service.SavedFilterService.delete_filter',
            side_effect=ValueError('Filter 123 not found'),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.delete('/api/v1/saved-filters/123')

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertIn('not found', payload.get('error', '').lower())

    def test_share_saved_filter_returns_404_for_not_found_error(self):
        with patch(
            'services.saved_filter_service.SavedFilterService.share_filter',
            side_effect=ValueError('Filter 456 not found'),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.patch('/api/v1/saved-filters/456/share', json={'is_shared': True})

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertIn('not found', payload.get('error', '').lower())


if __name__ == '__main__':
    unittest.main()