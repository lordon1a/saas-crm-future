import importlib.util
import unittest

from flask import Flask

from models import db, User, Workspace
import models_crm  # noqa: F401
from models_crm import AuditLog, IPWhitelist, Role
from services.security_service import SecurityService


HAS_PYOTP = importlib.util.find_spec('pyotp') is not None


class TestPhase9Security(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(cls.app)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws = Workspace(company_name='Security Test Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Security User',
            email='security@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_rbac_seed_creates_default_roles(self):
        SecurityService.ensure_rbac_seed(self.workspace_id)
        role_names = {row.name for row in Role.query.filter_by(workspace_id=self.workspace_id).all()}
        self.assertTrue({'Admin', 'Manager', 'Agent', 'Read-Only'}.issubset(role_names))

    def test_ip_whitelist_enforcement(self):
        self.assertTrue(SecurityService.is_ip_allowed(self.workspace_id, '10.0.0.1'))

        row = IPWhitelist(
            workspace_id=self.workspace_id,
            ip_address='10.0.0.1',
            label='Office',
            is_active=True,
        )
        db.session.add(row)
        db.session.commit()

        self.assertTrue(SecurityService.is_ip_allowed(self.workspace_id, '10.0.0.1'))
        self.assertFalse(SecurityService.is_ip_allowed(self.workspace_id, '10.0.0.2'))

    def test_compliance_report_counts_actions(self):
        db.session.add(AuditLog(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            action='auth.login',
            entity_type='user',
            entity_id=str(self.user_id),
        ))
        db.session.add(AuditLog(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            action='auth.login',
            entity_type='user',
            entity_id=str(self.user_id),
        ))
        db.session.commit()

        report = SecurityService.get_compliance_report(self.workspace_id, days=30)
        self.assertEqual(report['total_events'], 2)
        self.assertEqual(report['by_action'].get('auth.login'), 2)

    def test_2fa_setup_and_enable(self):
        if not HAS_PYOTP:
            self.skipTest('pyotp is not installed')

        import pyotp

        setup = SecurityService.setup_2fa(self.workspace_id, self.user_id, 'security@example.com')
        self.assertIn('secret', setup)
        self.assertIn('backup_codes', setup)

        token = pyotp.TOTP(setup['secret']).now()
        enabled = SecurityService.verify_and_enable_2fa(self.user_id, token)
        self.assertTrue(enabled)
        self.assertTrue(SecurityService.get_2fa_status(self.user_id))


if __name__ == '__main__':
    unittest.main()
