import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from routes.contacts import contacts_bp


class _DummyColumn:
    def in_(self, _value):
        return self

    def __eq__(self, _other):
        return self


def _fake_user_model(user):
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = user
    return SimpleNamespace(query=user_query)


class TestPhase16CrmPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'phase16-crm-permissions'
        cls.app.register_blueprint(contacts_bp)

    def test_bulk_update_denies_contacts_without_write_access(self):
        fake_contact_query = MagicMock()
        fake_contact_query.filter.return_value.all.return_value = [
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
        ]
        fake_contact_model = type(
            'FakeContactModel',
            (),
            {
                'id': _DummyColumn(),
                'workspace_id': _DummyColumn(),
                'is_deleted': _DummyColumn(),
                'query': fake_contact_query,
            },
        )

        fake_user = SimpleNamespace(id=100, workspace_id=77, role='member', is_active=True)

        with patch('models_crm.Contact', fake_contact_model), patch(
            'models.User', _fake_user_model(fake_user)
        ), patch('utils.permissions.check_entity_access', side_effect=[True, False]):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 100
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/contacts/bulk-update',
                    json={
                        'contact_ids': [1, 2],
                        'updates': {'email': 'new@example.com'},
                    },
                )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Access denied to one or more contacts')
        self.assertEqual(payload.get('denied_ids'), [2])

    def test_bulk_delete_all_contacts_requires_edit_all_permission(self):
        fake_user = SimpleNamespace(id=101, workspace_id=77, role='member', is_active=True)

        with patch('models.User', _fake_user_model(fake_user)), patch(
            'utils.permissions.check_permission', return_value=False
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 101
                    sess['workspace_id'] = 77

                response = client.post('/api/v1/contacts/bulk-delete-all', json={})

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Insufficient permissions')

    def test_bulk_update_rejects_unknown_target_company(self):
        fake_contact_query = MagicMock()
        fake_contact_query.filter.return_value.all.return_value = [
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
        ]
        fake_contact_model = type(
            'FakeContactModel',
            (),
            {
                'id': _DummyColumn(),
                'workspace_id': _DummyColumn(),
                'is_deleted': _DummyColumn(),
                'query': fake_contact_query,
            },
        )

        fake_company_query = MagicMock()
        fake_company_query.filter_by.return_value.first.return_value = None
        fake_company_model = type('FakeCompanyModel', (), {'query': fake_company_query})

        fake_user = SimpleNamespace(id=106, workspace_id=77, role='member', is_active=True)

        with patch('models_crm.Contact', fake_contact_model), patch(
            'models_crm.Company', fake_company_model
        ), patch('models.User', _fake_user_model(fake_user)), patch(
            'utils.permissions.check_entity_access', side_effect=[True, True]
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 106
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/contacts/bulk-update',
                    json={
                        'contact_ids': [1, 2],
                        'updates': {'company_id': 9999},
                    },
                )

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Target company not found')

    def test_bulk_update_denies_target_company_without_access(self):
        fake_contact_query = MagicMock()
        fake_contact_query.filter.return_value.all.return_value = [
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
        ]
        fake_contact_model = type(
            'FakeContactModel',
            (),
            {
                'id': _DummyColumn(),
                'workspace_id': _DummyColumn(),
                'is_deleted': _DummyColumn(),
                'query': fake_contact_query,
            },
        )

        fake_company_query = MagicMock()
        fake_company_query.filter_by.return_value.first.return_value = SimpleNamespace(id=301, workspace_id=77)
        fake_company_model = type('FakeCompanyModel', (), {'query': fake_company_query})

        fake_user = SimpleNamespace(id=107, workspace_id=77, role='member', is_active=True)

        with patch('models_crm.Contact', fake_contact_model), patch(
            'models_crm.Company', fake_company_model
        ), patch('models.User', _fake_user_model(fake_user)), patch(
            'utils.permissions.check_entity_access', side_effect=[True, True, False]
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 107
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/contacts/bulk-update',
                    json={
                        'contact_ids': [1, 2],
                        'updates': {'company_id': 301},
                    },
                )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Access denied to target company')

    def test_merge_contacts_denies_secondary_contact_without_write_access(self):
        fake_contact_query = MagicMock()
        fake_contact_query.filter_by.return_value = fake_contact_query
        fake_contact_query.first.side_effect = [
            SimpleNamespace(id=11, workspace_id=77),
            SimpleNamespace(id=12, workspace_id=77),
        ]
        fake_contact_model = type(
            'FakeContactModel',
            (),
            {
                'query': fake_contact_query,
            },
        )

        fake_user = SimpleNamespace(id=102, workspace_id=77, role='member', is_active=True)

        with patch('models_crm.Contact', fake_contact_model), patch(
            'models.User', _fake_user_model(fake_user)
        ), patch('utils.permissions.check_entity_access', side_effect=[True, False]), patch(
            'services.contact_merge_service.ContactMergeService.merge_contacts'
        ) as merge_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 102
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/contacts/merge',
                    json={
                        'primary_id': 11,
                        'secondary_id': 12,
                    },
                )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Access denied to secondary contact')
        merge_mock.assert_not_called()

    def test_merge_companies_denies_primary_company_without_write_access(self):
        fake_company_query = MagicMock()
        fake_company_query.filter_by.return_value = fake_company_query
        fake_company_query.first.side_effect = [
            SimpleNamespace(id=21, workspace_id=77),
            SimpleNamespace(id=22, workspace_id=77),
        ]
        fake_company_model = type(
            'FakeCompanyModel',
            (),
            {
                'query': fake_company_query,
            },
        )

        fake_user = SimpleNamespace(id=103, workspace_id=77, role='member', is_active=True)

        with patch('models_crm.Company', fake_company_model), patch(
            'models.User', _fake_user_model(fake_user)
        ), patch('utils.permissions.check_entity_access', side_effect=[False, True]), patch(
            'services.company_merge_service.CompanyMergeService.merge_companies'
        ) as merge_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 103
                    sess['workspace_id'] = 77

                response = client.post(
                    '/api/v1/companies/merge',
                    json={
                        'primary_id': 21,
                        'secondary_id': 22,
                    },
                )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Access denied to primary company')
        merge_mock.assert_not_called()

    def test_contact_duplicates_passes_current_user_to_service(self):
        fake_user = SimpleNamespace(id=104, workspace_id=77, role='member', is_active=True)

        with patch('models.User', _fake_user_model(fake_user)), patch(
            'services.contact_merge_service.ContactMergeService.find_duplicates', return_value=[]
        ) as find_duplicates_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 104
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/contacts/duplicates?contact_id=12')

        self.assertEqual(response.status_code, 200)
        find_duplicates_mock.assert_called_once_with(77, 12, current_user=fake_user)

    def test_company_duplicates_returns_401_when_user_missing_in_workspace(self):
        missing_user_model = SimpleNamespace(
            query=SimpleNamespace(filter_by=lambda **_kwargs: SimpleNamespace(first=lambda: None))
        )

        with patch('models.User', missing_user_model):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 105
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/companies/duplicates')

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Authentication required')


if __name__ == '__main__':
    unittest.main()
