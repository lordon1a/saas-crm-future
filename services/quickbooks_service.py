import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet

from config import Config
from models import db
from models_crm import (
    Activity,
    Company,
    Deal,
    QuickBooksIntegration,
    QuickBooksInvoice,
    QuickBooksSyncError,
)


class QuickBooksService:
    @staticmethod
    def _base_url():
        env = (Config.QUICKBOOKS_ENVIRONMENT or 'sandbox').lower()
        if env == 'production':
            return 'https://quickbooks.api.intuit.com'
        return 'https://sandbox-quickbooks.api.intuit.com'

    @staticmethod
    def _token_url():
        return 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'

    @staticmethod
    def is_configured() -> bool:
        return bool(Config.QUICKBOOKS_CLIENT_ID and Config.QUICKBOOKS_CLIENT_SECRET and Config.QUICKBOOKS_REDIRECT_URI)

    @staticmethod
    def _validate_configuration():
        if not QuickBooksService.is_configured():
            raise ValueError('QuickBooks OAuth is not configured')

    @staticmethod
    def _fernet_instance() -> Fernet:
        digest = hashlib.sha256(Config.SECRET_KEY.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        return Fernet(fernet_key)

    @staticmethod
    def _encrypt_value(value):
        if not value:
            return None
        return QuickBooksService._fernet_instance().encrypt(str(value).encode('utf-8')).decode('utf-8')

    @staticmethod
    def _decrypt_value(value):
        if not value:
            return None
        return QuickBooksService._fernet_instance().decrypt(value.encode('utf-8')).decode('utf-8')

    @staticmethod
    def generate_authorization_url(state):
        QuickBooksService._validate_configuration()
        params = {
            'client_id': Config.QUICKBOOKS_CLIENT_ID,
            'response_type': 'code',
            'scope': ' '.join(Config.QUICKBOOKS_SCOPES or ['com.intuit.quickbooks.accounting']),
            'redirect_uri': Config.QUICKBOOKS_REDIRECT_URI,
            'state': state,
        }
        return 'https://appcenter.intuit.com/connect/oauth2?' + urlencode(params)

    @staticmethod
    def exchange_code_for_tokens(code):
        QuickBooksService._validate_configuration()
        if not code:
            raise ValueError('Authorization code is required')

        basic = base64.b64encode(f"{Config.QUICKBOOKS_CLIENT_ID}:{Config.QUICKBOOKS_CLIENT_SECRET}".encode('utf-8')).decode('ascii')
        response = requests.post(
            QuickBooksService._token_url(),
            headers={
                'Authorization': f'Basic {basic}',
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': Config.QUICKBOOKS_REDIRECT_URI,
            },
            timeout=20,
        )
        payload = response.json() if response.content else {}
        if not response.ok:
            raise ValueError(payload.get('error_description') or payload.get('error') or 'QuickBooks token exchange failed')

        now = datetime.utcnow()
        return {
            'access_token': payload.get('access_token'),
            'refresh_token': payload.get('refresh_token'),
            'token_expires_at': now + timedelta(seconds=int(payload.get('expires_in') or 3600)),
            'refresh_expires_at': now + timedelta(seconds=int(payload.get('x_refresh_token_expires_in') or 86400)),
            'scopes': payload.get('scope', ''),
        }

    @staticmethod
    def refresh_access_token(integration):
        if not integration or not integration.refresh_token:
            raise ValueError('QuickBooks refresh token is missing')

        QuickBooksService._validate_configuration()
        refresh_token = QuickBooksService._decrypt_value(integration.refresh_token)
        basic = base64.b64encode(f"{Config.QUICKBOOKS_CLIENT_ID}:{Config.QUICKBOOKS_CLIENT_SECRET}".encode('utf-8')).decode('ascii')
        response = requests.post(
            QuickBooksService._token_url(),
            headers={
                'Authorization': f'Basic {basic}',
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            },
            timeout=20,
        )
        payload = response.json() if response.content else {}
        if not response.ok:
            raise ValueError(payload.get('error_description') or payload.get('error') or 'QuickBooks token refresh failed')

        now = datetime.utcnow()
        integration.access_token = QuickBooksService._encrypt_value(payload.get('access_token'))
        integration.refresh_token = QuickBooksService._encrypt_value(payload.get('refresh_token') or refresh_token)
        integration.token_expires_at = now + timedelta(seconds=int(payload.get('expires_in') or 3600))
        integration.refresh_expires_at = now + timedelta(seconds=int(payload.get('x_refresh_token_expires_in') or 86400))
        integration.updated_at = now
        db.session.commit()

    @staticmethod
    def _ensure_valid_access_token(integration):
        if not integration:
            raise ValueError('QuickBooks integration not found')
        if integration.token_expires_at and integration.token_expires_at <= datetime.utcnow() + timedelta(seconds=30):
            QuickBooksService.refresh_access_token(integration)
        return QuickBooksService._decrypt_value(integration.access_token)

    @staticmethod
    def upsert_integration(workspace_id, user_id, token_payload, realm_id, company_name=None):
        row = QuickBooksIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not row:
            row = QuickBooksIntegration(workspace_id=workspace_id, user_id=user_id, access_token='')
            db.session.add(row)

        row.realm_id = (realm_id or '').strip() or None
        row.company_name = (company_name or row.company_name or '').strip() or None
        row.access_token = QuickBooksService._encrypt_value(token_payload.get('access_token'))
        row.refresh_token = QuickBooksService._encrypt_value(token_payload.get('refresh_token'))
        row.token_expires_at = token_payload.get('token_expires_at')
        row.refresh_expires_at = token_payload.get('refresh_expires_at')
        row.scopes = token_payload.get('scopes') if isinstance(token_payload.get('scopes'), str) else json.dumps(token_payload.get('scopes') or [])
        row.is_active = True
        row.last_error = None
        db.session.commit()
        return row

    @staticmethod
    def get_active_integration(workspace_id, user_id):
        return QuickBooksIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id, is_active=True).first()

    @staticmethod
    def serialize_integration(row):
        if not row:
            return {
                'connected': False,
                'realm_id': None,
                'company_name': None,
                'token_expires_at': None,
                'last_sync_at': None,
                'last_error': None,
            }

        return {
            'connected': bool(row.is_active),
            'realm_id': row.realm_id,
            'company_name': row.company_name,
            'token_expires_at': row.token_expires_at.isoformat() if row.token_expires_at else None,
            'last_sync_at': row.last_sync_at.isoformat() if row.last_sync_at else None,
            'last_error': row.last_error,
        }

    @staticmethod
    def disconnect(workspace_id, user_id):
        row = QuickBooksService.get_active_integration(workspace_id, user_id)
        if not row:
            return False

        row.is_active = False
        row.access_token = ''
        row.refresh_token = None
        row.token_expires_at = None
        row.refresh_expires_at = None
        row.realm_id = None
        db.session.commit()
        return True

    @staticmethod
    def log_sync_error(workspace_id, operation, error_message, integration_id=None, invoice_id=None, http_status=None, retry_count=0, will_retry=False, next_retry_at=None, correlation_id=None):
        correlation_id = correlation_id or secrets.token_hex(16)
        row = QuickBooksSyncError(
            workspace_id=workspace_id,
            integration_id=integration_id,
            invoice_id=invoice_id,
            correlation_id=correlation_id,
            operation=operation,
            error_message=(error_message or 'Unknown error')[:4000],
            http_status=http_status,
            retry_count=retry_count,
            will_retry=bool(will_retry),
            next_retry_at=next_retry_at,
        )
        db.session.add(row)

        if integration_id:
            integration = QuickBooksIntegration.query.get(integration_id)
            if integration:
                integration.last_error = row.error_message

        if retry_count >= max(1, int(Config.QUICKBOOKS_MAX_RETRIES or 3)):
            db.session.add(Activity(
                workspace_id=workspace_id,
                activity_type='system',
                subject='QuickBooks sync failure alert',
                body=f'Operation: {operation}\nCorrelation: {correlation_id}\nError: {row.error_message}',
                extra_data=json.dumps({'quickbooks_error_id': None, 'correlation_id': correlation_id}),
            ))

        db.session.commit()
        return row

    @staticmethod
    def create_invoice_for_deal(workspace_id, user_id, deal_id):
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
        if not deal:
            raise ValueError('Deal not found')

        if deal.status != 'won':
            raise ValueError('Invoice can only be created for won deals')

        existing = QuickBooksInvoice.query.filter_by(workspace_id=workspace_id, deal_id=deal_id).first()
        if existing:
            return existing

        integration = QuickBooksService.get_active_integration(workspace_id, user_id)
        invoice = QuickBooksInvoice(
            workspace_id=workspace_id,
            integration_id=integration.id if integration else None,
            deal_id=deal.id,
            company_id=deal.company_id,
            created_by=user_id,
            amount=deal.value or Decimal('0'),
            due_date=(deal.expected_close_date or datetime.utcnow().date()) + timedelta(days=14),
            sync_status='pending',
            payment_status='unpaid',
        )
        db.session.add(invoice)
        db.session.commit()

        if integration:
            QuickBooksService.push_invoice_to_quickbooks(invoice.id)
        else:
            invoice.sync_status = 'failed'
            invoice.error_message = 'QuickBooks is not connected'
            db.session.commit()
            QuickBooksService.log_sync_error(
                workspace_id=workspace_id,
                operation='invoice.create',
                error_message='QuickBooks is not connected',
                invoice_id=invoice.id,
                retry_count=0,
                will_retry=False,
            )

        return invoice

    @staticmethod
    def push_invoice_to_quickbooks(invoice_id):
        invoice = QuickBooksInvoice.query.get(invoice_id)
        if not invoice:
            raise ValueError('Invoice not found')

        integration = QuickBooksIntegration.query.get(invoice.integration_id) if invoice.integration_id else None
        if not integration or not integration.realm_id:
            raise ValueError('QuickBooks integration is not ready')

        correlation_id = secrets.token_hex(16)
        try:
            access_token = QuickBooksService._ensure_valid_access_token(integration)
            company = Company.query.get(invoice.company_id) if invoice.company_id else None
            endpoint = f"{QuickBooksService._base_url()}/v3/company/{integration.realm_id}/invoice"
            payload = {
                'DocNumber': invoice.doc_number or f'DEAL-{invoice.deal_id}',
                'TxnDate': datetime.utcnow().date().isoformat(),
                'DueDate': invoice.due_date.isoformat() if invoice.due_date else None,
                'PrivateNote': f'CRM Deal #{invoice.deal_id}',
                'Line': [
                    {
                        'DetailType': 'SalesItemLineDetail',
                        'Amount': float(invoice.amount or 0),
                        'Description': f'Deal {invoice.deal_id} - {company.name if company else "Customer"}',
                        'SalesItemLineDetail': {
                            'Qty': 1,
                        },
                    }
                ],
                'CustomerMemo': {
                    'value': 'Generated from CRM',
                },
            }

            response = requests.post(
                endpoint,
                params={'minorversion': 65},
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=25,
            )
            body = response.json() if response.content else {}

            if not response.ok:
                retry_count = (invoice.retry_count or 0) + 1
                max_retries = max(1, int(Config.QUICKBOOKS_MAX_RETRIES or 3))
                will_retry = retry_count < max_retries
                next_retry = datetime.utcnow() + timedelta(minutes=2 ** min(retry_count, 6)) if will_retry else None

                invoice.retry_count = retry_count
                invoice.next_retry_at = next_retry
                invoice.sync_status = 'failed'
                invoice.error_message = (json.dumps(body) if body else response.text)[:2000]
                db.session.commit()

                QuickBooksService.log_sync_error(
                    workspace_id=invoice.workspace_id,
                    integration_id=integration.id,
                    invoice_id=invoice.id,
                    correlation_id=correlation_id,
                    operation='invoice.create',
                    error_message=invoice.error_message,
                    http_status=response.status_code,
                    retry_count=retry_count,
                    will_retry=will_retry,
                    next_retry_at=next_retry,
                )
                return invoice

            qb_invoice = (body.get('Invoice') or {}) if isinstance(body, dict) else {}
            invoice.quickbooks_invoice_id = str(qb_invoice.get('Id') or '') or invoice.quickbooks_invoice_id
            invoice.doc_number = qb_invoice.get('DocNumber') or invoice.doc_number
            invoice.sync_status = 'synced'
            invoice.error_message = None
            invoice.last_synced_at = datetime.utcnow()
            invoice.next_retry_at = None
            invoice.retry_count = 0
            integration.last_sync_at = datetime.utcnow()
            db.session.commit()
            return invoice
        except Exception as exc:
            retry_count = (invoice.retry_count or 0) + 1
            max_retries = max(1, int(Config.QUICKBOOKS_MAX_RETRIES or 3))
            will_retry = retry_count < max_retries
            next_retry = datetime.utcnow() + timedelta(minutes=2 ** min(retry_count, 6)) if will_retry else None

            invoice.retry_count = retry_count
            invoice.next_retry_at = next_retry
            invoice.sync_status = 'failed'
            invoice.error_message = str(exc)[:2000]
            db.session.commit()

            QuickBooksService.log_sync_error(
                workspace_id=invoice.workspace_id,
                integration_id=integration.id if integration else None,
                invoice_id=invoice.id,
                correlation_id=correlation_id,
                operation='invoice.create',
                error_message=str(exc),
                retry_count=retry_count,
                will_retry=will_retry,
                next_retry_at=next_retry,
            )
            return invoice

    @staticmethod
    def sync_payment_statuses(workspace_id, user_id):
        integration = QuickBooksService.get_active_integration(workspace_id, user_id)
        if not integration or not integration.realm_id:
            return {'synced': 0, 'paid': 0, 'skipped': 0}

        rows = QuickBooksInvoice.query.filter_by(workspace_id=workspace_id, sync_status='synced').all()
        synced = 0
        paid = 0
        skipped = 0

        access_token = QuickBooksService._ensure_valid_access_token(integration)
        for row in rows:
            if not row.quickbooks_invoice_id:
                skipped += 1
                continue

            try:
                endpoint = f"{QuickBooksService._base_url()}/v3/company/{integration.realm_id}/invoice/{row.quickbooks_invoice_id}"
                response = requests.get(
                    endpoint,
                    params={'minorversion': 65},
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Accept': 'application/json',
                    },
                    timeout=20,
                )
                if not response.ok:
                    QuickBooksService.log_sync_error(
                        workspace_id=workspace_id,
                        integration_id=integration.id,
                        invoice_id=row.id,
                        operation='invoice.sync',
                        error_message=response.text[:1000],
                        http_status=response.status_code,
                        retry_count=row.retry_count,
                        will_retry=False,
                    )
                    skipped += 1
                    continue

                body = response.json() if response.content else {}
                invoice_data = (body.get('Invoice') or {}) if isinstance(body, dict) else {}
                balance = Decimal(str(invoice_data.get('Balance', row.amount or 0)))
                row.last_synced_at = datetime.utcnow()
                synced += 1

                if balance <= Decimal('0') and row.payment_status != 'paid':
                    row.payment_status = 'paid'
                    row.paid_at = datetime.utcnow()
                    paid += 1

                    deal = Deal.query.filter_by(id=row.deal_id, workspace_id=workspace_id).first()
                    if deal and deal.status == 'open':
                        deal.status = 'won'
                        deal.closed_at = datetime.utcnow()

                    db.session.add(Activity(
                        workspace_id=workspace_id,
                        activity_type='system',
                        deal_id=row.deal_id,
                        company_id=row.company_id,
                        user_id=user_id,
                        subject='QuickBooks invoice marked paid',
                        body=f'Invoice {row.doc_number or row.quickbooks_invoice_id} is paid.',
                    ))
            except Exception as exc:
                QuickBooksService.log_sync_error(
                    workspace_id=workspace_id,
                    integration_id=integration.id,
                    invoice_id=row.id,
                    operation='invoice.sync',
                    error_message=str(exc),
                    retry_count=row.retry_count,
                    will_retry=False,
                )
                skipped += 1

        integration.last_sync_at = datetime.utcnow()
        db.session.commit()
        return {'synced': synced, 'paid': paid, 'skipped': skipped}

    @staticmethod
    def sync_pending_invoices(workspace_id, user_id):
        rows = QuickBooksInvoice.query.filter_by(workspace_id=workspace_id).filter(QuickBooksInvoice.sync_status.in_(['pending', 'failed'])).all()
        pushed = 0
        for row in rows:
            if row.next_retry_at and row.next_retry_at > datetime.utcnow():
                continue
            QuickBooksService.push_invoice_to_quickbooks(row.id)
            pushed += 1
        payment_result = QuickBooksService.sync_payment_statuses(workspace_id, user_id)
        return {
            'pushed': pushed,
            'payments': payment_result,
        }

    @staticmethod
    def list_invoices(workspace_id, limit=50):
        rows = QuickBooksInvoice.query.filter_by(workspace_id=workspace_id).order_by(QuickBooksInvoice.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [
            {
                'id': row.id,
                'deal_id': row.deal_id,
                'company_id': row.company_id,
                'quickbooks_invoice_id': row.quickbooks_invoice_id,
                'doc_number': row.doc_number,
                'sync_status': row.sync_status,
                'payment_status': row.payment_status,
                'amount': float(row.amount or 0),
                'currency': row.currency,
                'due_date': row.due_date.isoformat() if row.due_date else None,
                'paid_at': row.paid_at.isoformat() if row.paid_at else None,
                'last_synced_at': row.last_synced_at.isoformat() if row.last_synced_at else None,
                'error_message': row.error_message,
            }
            for row in rows
        ]

    @staticmethod
    def list_errors(workspace_id, limit=50):
        rows = QuickBooksSyncError.query.filter_by(workspace_id=workspace_id).order_by(QuickBooksSyncError.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [
            {
                'id': row.id,
                'correlation_id': row.correlation_id,
                'operation': row.operation,
                'error_message': row.error_message,
                'http_status': row.http_status,
                'retry_count': row.retry_count,
                'will_retry': row.will_retry,
                'next_retry_at': row.next_retry_at.isoformat() if row.next_retry_at else None,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def get_deal_invoice(workspace_id, deal_id):
        row = QuickBooksInvoice.query.filter_by(workspace_id=workspace_id, deal_id=deal_id).first()
        if not row:
            return None
        return {
            'id': row.id,
            'deal_id': row.deal_id,
            'quickbooks_invoice_id': row.quickbooks_invoice_id,
            'doc_number': row.doc_number,
            'sync_status': row.sync_status,
            'payment_status': row.payment_status,
            'amount': float(row.amount or 0),
            'currency': row.currency,
            'due_date': row.due_date.isoformat() if row.due_date else None,
            'paid_at': row.paid_at.isoformat() if row.paid_at else None,
            'error_message': row.error_message,
        }
