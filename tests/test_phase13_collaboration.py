import unittest
from datetime import datetime, timedelta

from flask import Flask

from models import Conversation, Customer, Note, User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Activity, Notification
from services.collaboration_service import CollaborationService


class TestPhase13Collaboration(unittest.TestCase):
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

        ws = Workspace(company_name='Collaboration Workspace')
        db.session.add(ws)
        db.session.flush()

        actor = User(
            workspace_id=ws.id,
            name='Actor User',
            email='actor@example.com',
            password_hash='hash',
            role='admin',
        )
        mentioned = User(
            workspace_id=ws.id,
            name='Ali Veli',
            email='ali@example.com',
            password_hash='hash',
            role='agent',
        )
        db.session.add(actor)
        db.session.add(mentioned)
        db.session.flush()

        customer = Customer(
            workspace_id=ws.id,
            phone_number='+905001110000',
            profile_name='Customer',
        )
        db.session.add(customer)
        db.session.flush()

        conv = Conversation(
            workspace_id=ws.id,
            customer_id=customer.id,
            status='open',
            last_message_at=datetime.utcnow(),
        )
        db.session.add(conv)
        db.session.commit()

        self.workspace_id = ws.id
        self.actor_user_id = actor.id
        self.mentioned_user_id = mentioned.id
        self.conversation_id = conv.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_property_66_mention_notification_creation(self):
        note = Note(
            conversation_id=self.conversation_id,
            user_id=self.actor_user_id,
            content='@ali bu kayda bakabilir misin?',
            is_internal=False,
        )
        db.session.add(note)
        db.session.commit()

        created = CollaborationService.process_note_mentions(
            workspace_id=self.workspace_id,
            note_id=note.id,
            actor_user_id=self.actor_user_id,
        )
        self.assertEqual(created, 1)

        notifications = Notification.query.filter_by(
            workspace_id=self.workspace_id,
            user_id=self.mentioned_user_id,
            notification_type='mention',
            entity_type='note',
            entity_id=note.id,
        ).all()
        self.assertEqual(len(notifications), 1)

    def test_property_67_internal_note_visibility(self):
        public_note = Note(
            conversation_id=self.conversation_id,
            user_id=self.actor_user_id,
            content='public note',
            is_internal=False,
        )
        internal_note = Note(
            conversation_id=self.conversation_id,
            user_id=self.actor_user_id,
            content='internal note',
            is_internal=True,
        )
        db.session.add(public_note)
        db.session.add(internal_note)
        db.session.commit()

        visible_for_external = CollaborationService.list_notes_for_conversation(self.conversation_id, include_internal=False)
        visible_for_agent = CollaborationService.list_notes_for_conversation(self.conversation_id, include_internal=True)

        self.assertEqual(len(visible_for_external), 1)
        self.assertFalse(visible_for_external[0].is_internal)
        self.assertEqual(len(visible_for_agent), 2)

    def test_property_68_activity_feed_recency(self):
        older = Activity(
            workspace_id=self.workspace_id,
            activity_type='system',
            subject='older',
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        newer = Activity(
            workspace_id=self.workspace_id,
            activity_type='system',
            subject='newer',
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add(older)
        db.session.add(newer)
        db.session.commit()

        feed = CollaborationService.list_activity_feed(self.workspace_id, limit=10)
        self.assertGreaterEqual(len(feed), 2)
        self.assertEqual(feed[0]['subject'], 'newer')

    def test_property_69_follow_notification_creation(self):
        follow = CollaborationService.follow_entity(
            workspace_id=self.workspace_id,
            user_id=self.mentioned_user_id,
            entity_type='deal',
            entity_id=99,
        )
        self.assertIsNotNone(follow.id)

        created = CollaborationService.notify_followers_on_entity_change(
            workspace_id=self.workspace_id,
            entity_type='deal',
            entity_id=99,
            message='Deal guncellendi',
        )
        self.assertEqual(created, 1)

        notifs = Notification.query.filter_by(
            workspace_id=self.workspace_id,
            user_id=self.mentioned_user_id,
            notification_type='entity_updated',
            entity_type='deal',
            entity_id=99,
        ).all()
        self.assertEqual(len(notifs), 1)

    def test_property_70_unread_notification_count(self):
        CollaborationService.create_notification(
            workspace_id=self.workspace_id,
            user_id=self.mentioned_user_id,
            notification_type='mention',
            message='Unread one',
            entity_type='note',
            entity_id=1,
        )
        row = CollaborationService.create_notification(
            workspace_id=self.workspace_id,
            user_id=self.mentioned_user_id,
            notification_type='mention',
            message='Will be read',
            entity_type='note',
            entity_id=2,
        )
        CollaborationService.mark_notification_read(self.workspace_id, self.mentioned_user_id, row.id)

        unread = CollaborationService.unread_count(self.workspace_id, self.mentioned_user_id)
        self.assertEqual(unread, 1)


if __name__ == '__main__':
    unittest.main()
