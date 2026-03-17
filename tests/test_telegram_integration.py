import unittest

from flask import Flask

from models import Conversation, Customer, Message, Workspace, db
from models_crm import Contact
from routes.telegram import telegram_bp


class TestTelegramIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(cls.app)
        cls.app.register_blueprint(telegram_bp)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws = Workspace(company_name='Telegram WS', telegram_bot_token='dummy-token')
        db.session.add(ws)
        db.session.commit()
        self.workspace_id = ws.id

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_webhook_creates_customer_contact_and_message(self):
        payload = {
            'update_id': 12345,
            'message': {
                'message_id': 77,
                'chat': {'id': 99887766, 'first_name': 'Ahmet'},
                'from': {'id': 99887766, 'first_name': 'Ahmet'},
                'text': 'Merhaba telegram',
            },
        }

        res = self.client.post(f'/api/v1/webhooks/telegram?workspace_id={self.workspace_id}', json=payload)
        self.assertEqual(res.status_code, 200)

        customer = Customer.query.filter_by(workspace_id=self.workspace_id, telegram_chat_id='99887766').first()
        self.assertIsNotNone(customer)

        conversation = Conversation.query.filter_by(workspace_id=self.workspace_id, customer_id=customer.id).first()
        self.assertIsNotNone(conversation)

        message = Message.query.filter_by(conversation_id=conversation.id).first()
        self.assertIsNotNone(message)
        self.assertEqual(message.channel, 'telegram')

        contact = Contact.query.filter_by(workspace_id=self.workspace_id, customer_id=customer.id).first()
        self.assertIsNotNone(contact)
        self.assertEqual(contact.telegram_chat_id, '99887766')

    def test_webhook_duplicate_update_is_ignored(self):
        payload = {
            'update_id': 9876,
            'message': {
                'message_id': 12,
                'chat': {'id': 5550001, 'first_name': 'User'},
                'text': 'Ping',
            },
        }

        first = self.client.post(f'/api/v1/webhooks/telegram?workspace_id={self.workspace_id}', json=payload)
        second = self.client.post(f'/api/v1/webhooks/telegram?workspace_id={self.workspace_id}', json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Message.query.count(), 1)


if __name__ == '__main__':
    unittest.main()
