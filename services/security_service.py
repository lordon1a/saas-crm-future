"""Security and compliance service utilities for Phase 9."""
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta

import pyotp

from models import db, User, Customer, Conversation, Message, Note
from models_crm import (
    AuditLog,
    GDPRRequest,
    IPWhitelist,
    Permission,
    Role,
    RolePermission,
    SessionActivity,
    TwoFactorAuth,
    UserRole,
)

logger = logging.getLogger(__name__)


class SecurityService:
    DEFAULT_ROLE_PERMISSIONS = {
        'Admin': ['security.manage', 'workspace.manage', 'users.manage', 'reports.view'],
        'Manager': ['users.manage', 'reports.view'],
        'Agent': ['reports.view'],
        'Read-Only': ['reports.view'],
    }

    @staticmethod
    def ensure_rbac_seed(workspace_id):
        """Seed default roles and permissions for workspace."""
        try:
            for permission_key in {'security.manage', 'workspace.manage', 'users.manage', 'reports.view'}:
                perm = Permission.query.filter_by(key=permission_key).first()
                if not perm:
                    db.session.add(Permission(key=permission_key, description=permission_key))
            db.session.flush()

            for role_name, perm_keys in SecurityService.DEFAULT_ROLE_PERMISSIONS.items():
                role = Role.query.filter_by(workspace_id=workspace_id, name=role_name).first()
                if not role:
                    role = Role(
                        workspace_id=workspace_id,
                        name=role_name,
                        description=f'{role_name} system role',
                        is_system=True,
                    )
                    db.session.add(role)
                    db.session.flush()

                for perm_key in perm_keys:
                    perm = Permission.query.filter_by(key=perm_key).first()
                    exists = RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first()
                    if not exists:
                        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to seed RBAC defaults: %s', exc)
            raise

    @staticmethod
    def get_user_permissions(workspace_id, user_id):
        """Get effective permission keys for user."""
        query = db.session.query(Permission.key).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).join(
            Role, Role.id == RolePermission.role_id
        ).join(
            UserRole, UserRole.role_id == Role.id
        ).filter(
            UserRole.workspace_id == workspace_id,
            UserRole.user_id == user_id,
        )
        return {row.key for row in query.all()}

    @staticmethod
    def assign_role(workspace_id, user_id, role_name):
        """Assign user role by name."""
        role = Role.query.filter_by(workspace_id=workspace_id, name=role_name).first()
        if not role:
            raise ValueError('Role not found')

        try:
            UserRole.query.filter_by(workspace_id=workspace_id, user_id=user_id).delete()
            db.session.add(UserRole(workspace_id=workspace_id, user_id=user_id, role_id=role.id))
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to assign role: %s', exc)
            raise

    @staticmethod
    def list_roles(workspace_id):
        """List roles and members."""
        roles = Role.query.filter_by(workspace_id=workspace_id).order_by(Role.name.asc()).all()
        result = []
        for role in roles:
            members = db.session.query(User.id, User.name, User.email).join(
                UserRole, UserRole.user_id == User.id
            ).filter(
                UserRole.workspace_id == workspace_id,
                UserRole.role_id == role.id,
            ).all()
            result.append({
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'members': [{'id': m.id, 'name': m.name, 'email': m.email} for m in members],
            })
        return result

    @staticmethod
    def setup_2fa(workspace_id, user_id, email):
        """Create or rotate 2FA setup secret."""
        secret = pyotp.random_base32()
        backup_codes = [secrets.token_hex(4) for _ in range(8)]
        backup_hashes = [hashlib.sha256(code.encode('utf-8')).hexdigest() for code in backup_codes]

        row = TwoFactorAuth.query.filter_by(user_id=user_id).first()
        try:
            if not row:
                row = TwoFactorAuth(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    secret_key=secret,
                    backup_codes_json=json.dumps(backup_hashes),
                    is_enabled=False,
                )
                db.session.add(row)
            else:
                row.secret_key = secret
                row.backup_codes_json = json.dumps(backup_hashes)
                row.is_enabled = False

            db.session.commit()

            otp_uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name='WhatsApp CRM')
            return {'secret': secret, 'otp_uri': otp_uri, 'backup_codes': backup_codes}
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to setup 2FA: %s', exc)
            raise

    @staticmethod
    def verify_and_enable_2fa(user_id, token):
        """Verify setup token and enable 2FA."""
        row = TwoFactorAuth.query.filter_by(user_id=user_id).first()
        if not row:
            raise ValueError('2FA setup not found')

        if not pyotp.TOTP(row.secret_key).verify(str(token), valid_window=1):
            return False

        try:
            row.is_enabled = True
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to enable 2FA: %s', exc)
            raise

    @staticmethod
    def disable_2fa(user_id):
        """Disable existing 2FA."""
        row = TwoFactorAuth.query.filter_by(user_id=user_id).first()
        if not row:
            return False

        try:
            row.is_enabled = False
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to disable 2FA: %s', exc)
            raise

    @staticmethod
    def verify_login_2fa(user_id, token):
        """Verify login 2FA token or backup code."""
        row = TwoFactorAuth.query.filter_by(user_id=user_id, is_enabled=True).first()
        if not row:
            return True

        if pyotp.TOTP(row.secret_key).verify(str(token), valid_window=1):
            return True

        code_hash = hashlib.sha256(str(token).encode('utf-8')).hexdigest()
        backup_hashes = json.loads(row.backup_codes_json or '[]')
        if code_hash in backup_hashes:
            try:
                backup_hashes.remove(code_hash)
                row.backup_codes_json = json.dumps(backup_hashes)
                db.session.commit()
                return True
            except Exception as exc:
                db.session.rollback()
                logger.error('Failed to consume backup code: %s', exc)
                return False

        return False

    @staticmethod
    def get_2fa_status(user_id):
        """Return 2FA enabled status."""
        try:
            row = TwoFactorAuth.query.filter_by(user_id=user_id).first()
            return bool(row and row.is_enabled)
        except Exception as exc:
            logger.error('Failed to read 2FA status for user %s: %s', user_id, exc)
            # Fail-open to avoid blocking login when security tables are not ready.
            return False

    @staticmethod
    def is_ip_allowed(workspace_id, ip_address):
        """Validate IP against whitelist if whitelist is configured."""
        try:
            rows = IPWhitelist.query.filter_by(workspace_id=workspace_id, is_active=True).all()
            if not rows:
                return True
            allowed = {row.ip_address for row in rows}
            return ip_address in allowed
        except Exception as exc:
            logger.error('Failed to evaluate IP whitelist for workspace %s: %s', workspace_id, exc)
            # Fail-open to avoid full login outage on schema/runtime issues.
            return True

    @staticmethod
    def list_ip_whitelist(workspace_id):
        """List configured whitelist rows."""
        rows = IPWhitelist.query.filter_by(workspace_id=workspace_id).order_by(IPWhitelist.created_at.desc()).all()
        return [
            {
                'id': row.id,
                'ip_address': row.ip_address,
                'label': row.label,
                'is_active': row.is_active,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def add_ip_whitelist(workspace_id, ip_address, label, created_by):
        """Create whitelist record."""
        try:
            row = IPWhitelist(
                workspace_id=workspace_id,
                ip_address=ip_address,
                label=label,
                created_by=created_by,
                is_active=True,
            )
            db.session.add(row)
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to add whitelist IP: %s', exc)
            raise

    @staticmethod
    def delete_ip_whitelist(workspace_id, row_id):
        """Delete whitelist record."""
        row = IPWhitelist.query.filter_by(workspace_id=workspace_id, id=row_id).first()
        if not row:
            return False
        try:
            db.session.delete(row)
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to delete whitelist IP: %s', exc)
            raise

    @staticmethod
    def record_session_activity(workspace_id, user_id, session_token, ip_address, user_agent, timeout_minutes):
        """Create or refresh session activity row."""
        row = SessionActivity.query.filter_by(session_token=session_token).first()
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        try:
            if not row:
                row = SessionActivity(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    session_token=session_token,
                    ip_address=ip_address,
                    user_agent=(user_agent or '')[:500],
                    last_seen_at=datetime.utcnow(),
                    expires_at=expires_at,
                    is_active=True,
                )
                db.session.add(row)
            else:
                row.last_seen_at = datetime.utcnow()
                row.expires_at = expires_at
                row.is_active = True
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to record session activity: %s', exc)
            return None

    @staticmethod
    def get_compliance_report(workspace_id, days=30):
        """Generate compliance summary from audit logs."""
        start = datetime.utcnow() - timedelta(days=days)
        logs = AuditLog.query.filter(
            AuditLog.workspace_id == workspace_id,
            AuditLog.created_at >= start,
        ).all()

        by_action = {}
        by_user = {}
        for row in logs:
            by_action[row.action] = by_action.get(row.action, 0) + 1
            key = str(row.user_id or 'unknown')
            by_user[key] = by_user.get(key, 0) + 1

        return {
            'days': days,
            'total_events': len(logs),
            'by_action': by_action,
            'by_user': by_user,
        }

    @staticmethod
    def create_gdpr_export(workspace_id, requested_by, target_user_id):
        """Generate GDPR data export payload for target user data."""
        payload = {
            'user': None,
            'customers': [],
            'conversations': [],
            'messages': [],
            'notes': [],
            'audit_logs': [],
        }

        user = User.query.filter_by(id=target_user_id, workspace_id=workspace_id).first()
        if user:
            payload['user'] = {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role}

        customers = Customer.query.filter_by(workspace_id=workspace_id).all()
        payload['customers'] = [{'id': c.id, 'phone': c.phone_number, 'name': c.profile_name} for c in customers]

        convs = Conversation.query.filter_by(workspace_id=workspace_id).all()
        payload['conversations'] = [{'id': c.id, 'customer_id': c.customer_id, 'status': c.status} for c in convs]

        payload['messages'] = [
            {'id': m.id, 'conversation_id': m.conversation_id, 'sender_id': m.sender_id, 'created_at': m.created_at.isoformat() if m.created_at else None}
            for m in Message.query.join(Conversation).filter(Conversation.workspace_id == workspace_id).all()
        ]

        payload['notes'] = [
            {'id': n.id, 'conversation_id': n.conversation_id, 'user_id': n.user_id}
            for n in Note.query.join(Conversation).filter(Conversation.workspace_id == workspace_id).all()
        ]

        payload['audit_logs'] = [
            {'id': a.id, 'action': a.action, 'entity_type': a.entity_type, 'created_at': a.created_at.isoformat() if a.created_at else None}
            for a in AuditLog.query.filter_by(workspace_id=workspace_id).all()
        ]

        req = GDPRRequest(
            workspace_id=workspace_id,
            requested_by=requested_by,
            request_type='export',
            status='completed',
            target_user_id=target_user_id,
            result_json=json.dumps(payload, ensure_ascii=False),
            completed_at=datetime.utcnow(),
        )

        try:
            db.session.add(req)
            db.session.commit()
            return req
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to create GDPR export request: %s', exc)
            raise

    @staticmethod
    def create_gdpr_delete(workspace_id, requested_by, target_user_id):
        """Delete target user account in workspace and record GDPR request."""
        req = GDPRRequest(
            workspace_id=workspace_id,
            requested_by=requested_by,
            request_type='delete',
            status='pending',
            target_user_id=target_user_id,
        )

        try:
            db.session.add(req)
            db.session.flush()

            user = User.query.filter_by(id=target_user_id, workspace_id=workspace_id).first()
            if user:
                db.session.delete(user)

            req.status = 'completed'
            req.completed_at = datetime.utcnow()
            req.result_json = json.dumps({'deleted_user_id': target_user_id}, ensure_ascii=False)
            db.session.commit()
            return req
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to process GDPR delete request: %s', exc)
            raise
