"""
Entry point for periodic Google Workspace background sync.
"""
import logging

from app import app
from services.google_sync_worker import GoogleSyncWorker


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    with app.app_context():
        GoogleSyncWorker.run_forever()
