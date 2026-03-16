from datetime import datetime, timedelta
from flask import Flask

from config import Config
from models import db, Workspace, User, Customer, Conversation, Message

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def _get_target_workspace_id():
    admin_user = User.query.filter_by(email='admin@example.com').first()
    if admin_user:
        return admin_user.workspace_id

    workspace = Workspace.query.order_by(Workspace.id.asc()).first()
    if workspace:
        return workspace.id

    workspace = Workspace(company_name='Demo Workspace')
    db.session.add(workspace)
    db.session.flush()
    return workspace.id


def seed_mocks():
    with app.app_context():
        workspace_id = _get_target_workspace_id()
        now = datetime.utcnow()

        mock_rows = [
            {
                'phone': '+90 555 123 4567',
                'name': 'Ahmet Yılmaz',
                'email': 'ahmet@example.com',
                'status': 'open',
                'tag': 'yeni_siparis',
                'message': 'Merhaba, siparişim ne zaman kargoya verilir?',
                'minutes_ago': 15,
                'is_read': False
            },
            {
                'phone': '+90 555 987 6543',
                'name': 'Ayşe Demir',
                'email': 'ayse@example.com',
                'status': 'pending',
                'tag': 'odeme_bekliyor',
                'message': 'Ödeme adımında hata alıyorum, yardımcı olur musunuz?',
                'minutes_ago': 120,
                'is_read': True
            },
            {
                'phone': '+90 555 333 4444',
                'name': 'Fatma Kaya',
                'email': 'fatma@example.com',
                'status': 'open',
                'tag': 'kargo_sorunu',
                'message': 'Kargo takipte takıldı görünüyor.',
                'minutes_ago': 55,
                'is_read': False
            }
        ]

        inserted = 0
        for row in mock_rows:
            customer = Customer.query.filter_by(
                workspace_id=workspace_id,
                phone_number=row['phone']
            ).first()

            if not customer:
                customer = Customer(
                    workspace_id=workspace_id,
                    phone_number=row['phone'],
                    profile_name=row['name'],
                    email=row['email'],
                    created_at=now - timedelta(days=2)
                )
                db.session.add(customer)
                db.session.flush()

            conversation = Conversation.query.filter_by(
                workspace_id=workspace_id,
                customer_id=customer.id
            ).first()

            if conversation:
                continue

            created_at = now - timedelta(minutes=row['minutes_ago'])
            conversation = Conversation(
                workspace_id=workspace_id,
                customer_id=customer.id,
                status=row['status'],
                tags=row['tag'],
                last_message_at=created_at
            )
            db.session.add(conversation)
            db.session.flush()

            message = Message(
                conversation_id=conversation.id,
                sender_type='customer',
                message_body=row['message'],
                meta_message_id=f'mock-{conversation.id}',
                is_read=row['is_read'],
                created_at=created_at
            )
            db.session.add(message)
            inserted += 1

        db.session.commit()
        print(f'✅ Mock conversations ready for workspace {workspace_id}. Added: {inserted}')


if __name__ == '__main__':
    seed_mocks()
