import unittest
from datetime import UTC, datetime, timedelta

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import NotificationPreference, Task, TaskNotification
from services.task_service import TaskService


class TestPhase20TaskOverdueStatus(unittest.TestCase):
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

        ws1 = Workspace(company_name='Phase20 Workspace 1')
        ws2 = Workspace(company_name='Phase20 Workspace 2')
        db.session.add_all([ws1, ws2])
        db.session.flush()

        user1 = User(
            workspace_id=ws1.id,
            name='Phase20 User 1',
            email='phase20-user1@example.com',
            password_hash='hash',
            role='admin',
        )
        user2 = User(
            workspace_id=ws2.id,
            name='Phase20 User 2',
            email='phase20-user2@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add_all([user1, user2])
        db.session.flush()

        pref1 = NotificationPreference(
            workspace_id=ws1.id,
            user_id=user1.id,
            task_overdue_enabled=True,
        )
        pref2 = NotificationPreference(
            workspace_id=ws2.id,
            user_id=user2.id,
            task_overdue_enabled=True,
        )
        db.session.add_all([pref1, pref2])
        db.session.commit()

        self.ws1_id = ws1.id
        self.ws2_id = ws2.id
        self.user1_id = user1.id
        self.user2_id = user2.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _create_task(self, workspace_id, status, end_time, assignee_id=None):
        task = Task(
            workspace_id=workspace_id,
            title=f'Phase20 {status} task',
            status=status,
            end_time=end_time,
            assignee_id=assignee_id,
        )
        db.session.add(task)
        db.session.flush()
        return task

    def test_mark_overdue_updates_active_statuses_and_skips_terminal(self):
        now = datetime.now(UTC).replace(tzinfo=None)

        not_started = self._create_task(
            workspace_id=self.ws1_id,
            status='not_started',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )
        in_progress = self._create_task(
            workspace_id=self.ws1_id,
            status='in_progress',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )
        blocked = self._create_task(
            workspace_id=self.ws1_id,
            status='blocked',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )
        legacy_pending = self._create_task(
            workspace_id=self.ws1_id,
            status='pending',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )

        completed = self._create_task(
            workspace_id=self.ws1_id,
            status='completed',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )
        cancelled = self._create_task(
            workspace_id=self.ws1_id,
            status='cancelled',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user1_id,
        )
        future_task = self._create_task(
            workspace_id=self.ws1_id,
            status='not_started',
            end_time=now + timedelta(hours=2),
            assignee_id=self.user1_id,
        )

        other_workspace = self._create_task(
            workspace_id=self.ws2_id,
            status='not_started',
            end_time=now - timedelta(hours=2),
            assignee_id=self.user2_id,
        )

        db.session.commit()

        TaskService.mark_overdue_tasks(self.ws1_id)

        for task_id in [not_started.id, in_progress.id, blocked.id, legacy_pending.id]:
            refreshed = db.session.get(Task, task_id)
            self.assertEqual(refreshed.status, 'overdue')

        self.assertEqual(db.session.get(Task, completed.id).status, 'completed')
        self.assertEqual(db.session.get(Task, cancelled.id).status, 'cancelled')
        self.assertEqual(db.session.get(Task, future_task.id).status, 'not_started')
        self.assertEqual(db.session.get(Task, other_workspace.id).status, 'not_started')

        notifications = TaskNotification.query.filter_by(
            workspace_id=self.ws1_id,
            user_id=self.user1_id,
            notification_type='task_overdue',
        ).all()
        self.assertEqual(len(notifications), 4)

    def test_mark_overdue_respects_notification_preference(self):
        now = datetime.now(UTC).replace(tzinfo=None)

        pref = NotificationPreference.query.filter_by(
            workspace_id=self.ws1_id,
            user_id=self.user1_id,
        ).first()
        pref.task_overdue_enabled = False
        db.session.commit()

        task = self._create_task(
            workspace_id=self.ws1_id,
            status='not_started',
            end_time=now - timedelta(minutes=30),
            assignee_id=self.user1_id,
        )
        db.session.commit()

        TaskService.mark_overdue_tasks(self.ws1_id)

        refreshed = db.session.get(Task, task.id)
        self.assertEqual(refreshed.status, 'overdue')

        notifications = TaskNotification.query.filter_by(
            workspace_id=self.ws1_id,
            user_id=self.user1_id,
            task_id=task.id,
            notification_type='task_overdue',
        ).all()
        self.assertEqual(len(notifications), 0)


if __name__ == '__main__':
    unittest.main()
