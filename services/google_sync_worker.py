"""
Google background sync worker.

Runs Gmail and Calendar sync for each active Google integration.
"""
import logging
import time

from config import Config
from models import db
from models_crm import GoogleIntegration
from services.calendar_sync_service import CalendarSyncService
from services.gmail_sync_service import GmailSyncService

logger = logging.getLogger(__name__)


class GoogleSyncWorker:
    """Background worker for periodic Gmail and Calendar sync."""

    @staticmethod
    def run_once() -> dict:
        """Run one full sync cycle for all active integrations."""
        if not Config.GOOGLE_SYNC_ENABLED:
            logger.info('Google sync worker is disabled by configuration')
            return {
                'enabled': False,
                'integrations': 0,
                'gmail_ok': 0,
                'calendar_ok': 0,
                'errors': 0,
            }

        rows = GoogleIntegration.query.filter_by(is_active=True).all()
        stats = {
            'enabled': True,
            'integrations': len(rows),
            'gmail_ok': 0,
            'calendar_ok': 0,
            'errors': 0,
        }

        for row in rows:
            try:
                gmail_result = GmailSyncService.sync_recent_emails(
                    workspace_id=row.workspace_id,
                    user_id=row.user_id,
                    max_results=Config.GOOGLE_SYNC_GMAIL_MAX_RESULTS,
                )
                if gmail_result and gmail_result.get('success'):
                    stats['gmail_ok'] += 1
                else:
                    stats['errors'] += 1
                    logger.warning(
                        'Gmail sync failed for workspace=%s user=%s: %s',
                        row.workspace_id,
                        row.user_id,
                        gmail_result,
                    )
            except Exception as exc:
                stats['errors'] += 1
                db.session.rollback()
                logger.exception(
                    'Unhandled Gmail sync error for workspace=%s user=%s: %s',
                    row.workspace_id,
                    row.user_id,
                    exc,
                )

            try:
                calendar_result = CalendarSyncService.sync_recent_events(
                    workspace_id=row.workspace_id,
                    user_id=row.user_id,
                    days_back=Config.GOOGLE_SYNC_CALENDAR_DAYS_BACK,
                    days_forward=Config.GOOGLE_SYNC_CALENDAR_DAYS_FORWARD,
                )
                if calendar_result and calendar_result.get('success'):
                    stats['calendar_ok'] += 1
                else:
                    stats['errors'] += 1
                    logger.warning(
                        'Calendar sync failed for workspace=%s user=%s: %s',
                        row.workspace_id,
                        row.user_id,
                        calendar_result,
                    )
            except Exception as exc:
                stats['errors'] += 1
                db.session.rollback()
                logger.exception(
                    'Unhandled Calendar sync error for workspace=%s user=%s: %s',
                    row.workspace_id,
                    row.user_id,
                    exc,
                )

        logger.info(
            'Google sync cycle done: integrations=%s gmail_ok=%s calendar_ok=%s errors=%s',
            stats['integrations'],
            stats['gmail_ok'],
            stats['calendar_ok'],
            stats['errors'],
        )
        return stats

    @staticmethod
    def run_forever() -> None:
        """Run sync cycle continuously with configured interval."""
        interval = max(30, int(Config.GOOGLE_SYNC_INTERVAL_SECONDS or 300))
        logger.info('Google sync worker started with interval=%s seconds', interval)

        while True:
            start = time.time()
            GoogleSyncWorker.run_once()
            elapsed = time.time() - start
            sleep_seconds = max(1, interval - int(elapsed))
            time.sleep(sleep_seconds)
