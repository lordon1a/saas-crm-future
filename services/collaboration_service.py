import logging
import re
from datetime import datetime

from models import Note, User, db
from models_crm import Activity, Follow, Mention, Notification

logger = logging.getLogger(__name__)


class CollaborationService:
    MENTION_PATTERN = re.compile(r'@([a-zA-Z0-9_.-]+)')
    ALLOWED_FOLLOW_ENTITY_TYPES = {'contact', 'company', 'deal'}

    @staticmethod
    def _extract_mention_tokens(text):
        if not text:
            return []
        return sorted(set(CollaborationService.MENTION_PATTERN.findall(text)))

    @staticmethod
    def _find_users_for_mention_tokens(workspace_id, tokens):
        if not tokens:
            return []

        normalized = {t.strip().lower() for t in tokens if t and t.strip()}
        if not normalized:
            return []

        users = User.query.filter_by(workspace_id=workspace_id).all()
        matched = []
        for user in users:
            candidates = set()
            if user.name:
                candidates.add(user.name.strip().lower().replace(' ', ''))
            if user.email:
                email = user.email.strip().lower()
                candidates.add(email)
                candidates.add(email.split('@')[0])
            if candidates.intersection(normalized):
                matched.append(user)
        return matched

    @staticmethod
    def create_notification(workspace_id, user_id, notification_type, message, entity_type=None, entity_id=None):
        try:
            row = Notification(
                workspace_id=workspace_id,
                user_id=user_id,
                notification_type=notification_type,
                entity_type=entity_type,
                entity_id=entity_id,
                message=(message or '')[:500],
                is_read=False,
            )
            db.session.add(row)
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to create notification: %s', exc)
            return None

    @staticmethod
    def process_note_mentions(workspace_id, note_id, actor_user_id):
        note = Note.query.get(note_id)
        if not note:
            return 0

        tokens = CollaborationService._extract_mention_tokens(note.content)
        users = CollaborationService._find_users_for_mention_tokens(workspace_id, tokens)
        if not users:
            return 0

        created_count = 0
        try:
            activity = Activity(
                workspace_id=workspace_id,
                activity_type='note',
                user_id=actor_user_id,
                subject='Note mention',
                body=(note.content or '')[:1000],
            )
            db.session.add(activity)
            db.session.flush()

            for user in users:
                if user.id == actor_user_id:
                    continue

                existing = Mention.query.filter_by(note_id=note.id, mentioned_user_id=user.id).first()
                if existing:
                    continue

                mention = Mention(
                    workspace_id=workspace_id,
                    activity_id=activity.id,
                    note_id=note.id,
                    mentioned_user_id=user.id,
                    created_by=actor_user_id,
                )
                db.session.add(mention)

                db.session.add(Notification(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    notification_type='mention',
                    entity_type='note',
                    entity_id=note.id,
                    message=f'@mention aldiniz: "{(note.content or "")[:120]}"',
                    is_read=False,
                ))
                created_count += 1

            db.session.commit()
            return created_count
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to process note mentions: %s', exc)
            return 0

    @staticmethod
    def create_task_assignment_notification(workspace_id, task_id, assignee_id, actor_user_id=None):
        if not assignee_id:
            return None
        message = f'Yeni gorev atandi (Task #{task_id}).'
        return CollaborationService.create_notification(
            workspace_id=workspace_id,
            user_id=assignee_id,
            notification_type='task_assigned',
            entity_type='task',
            entity_id=task_id,
            message=message,
        )

    @staticmethod
    def follow_entity(workspace_id, user_id, entity_type, entity_id):
        et = (entity_type or '').strip().lower()
        if et not in CollaborationService.ALLOWED_FOLLOW_ENTITY_TYPES:
            raise ValueError('Invalid entity_type')

        existing = Follow.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=et,
            entity_id=entity_id,
        ).first()
        if existing:
            return existing

        try:
            row = Follow(
                workspace_id=workspace_id,
                user_id=user_id,
                entity_type=et,
                entity_id=entity_id,
            )
            db.session.add(row)
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to follow entity: %s', exc)
            raise

    @staticmethod
    def unfollow_entity(workspace_id, user_id, entity_type, entity_id):
        et = (entity_type or '').strip().lower()
        row = Follow.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=et,
            entity_id=entity_id,
        ).first()
        if not row:
            return False

        try:
            db.session.delete(row)
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to unfollow entity: %s', exc)
            return False

    @staticmethod
    def is_following(workspace_id, user_id, entity_type, entity_id):
        et = (entity_type or '').strip().lower()
        return Follow.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=et,
            entity_id=entity_id,
        ).first() is not None

    @staticmethod
    def list_follows(workspace_id, user_id):
        rows = Follow.query.filter_by(workspace_id=workspace_id, user_id=user_id).order_by(Follow.created_at.desc()).all()
        return [
            {
                'id': row.id,
                'entity_type': row.entity_type,
                'entity_id': row.entity_id,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def notify_followers_on_entity_change(workspace_id, entity_type, entity_id, message):
        et = (entity_type or '').strip().lower()
        followers = Follow.query.filter_by(
            workspace_id=workspace_id,
            entity_type=et,
            entity_id=entity_id,
        ).all()

        created = 0
        try:
            for follower in followers:
                db.session.add(Notification(
                    workspace_id=workspace_id,
                    user_id=follower.user_id,
                    notification_type='entity_updated',
                    entity_type=et,
                    entity_id=entity_id,
                    message=(message or f'Takip ettiginiz {et} kaydi guncellendi.')[:500],
                    is_read=False,
                ))
                created += 1
            db.session.commit()
            return created
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to notify followers: %s', exc)
            return 0

    @staticmethod
    def list_notifications(workspace_id, user_id, limit=30):
        rows = Notification.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
        ).order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [
            {
                'id': row.id,
                'notification_type': row.notification_type,
                'entity_type': row.entity_type,
                'entity_id': row.entity_id,
                'message': row.message,
                'is_read': bool(row.is_read),
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'read_at': row.read_at.isoformat() if row.read_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def unread_count(workspace_id, user_id):
        return Notification.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_read=False,
        ).count()

    @staticmethod
    def mark_notification_read(workspace_id, user_id, notification_id):
        row = Notification.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            id=notification_id,
        ).first()
        if not row:
            return False
        try:
            row.is_read = True
            row.read_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to mark notification read: %s', exc)
            return False

    @staticmethod
    def mark_all_notifications_read(workspace_id, user_id):
        try:
            Notification.query.filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                is_read=False,
            ).update({
                'is_read': True,
                'read_at': datetime.utcnow(),
            })
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to mark all notifications read: %s', exc)
            return False

    @staticmethod
    def list_activity_feed(workspace_id, limit=50):
        rows = Activity.query.filter_by(workspace_id=workspace_id, is_deleted=False).order_by(Activity.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [
            {
                'id': row.id,
                'activity_type': row.activity_type,
                'contact_id': row.contact_id,
                'company_id': row.company_id,
                'deal_id': row.deal_id,
                'user_id': row.user_id,
                'subject': row.subject,
                'body': row.body,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def list_notes_for_conversation(conversation_id, include_internal):
        try:
            query = Note.query.filter_by(conversation_id=conversation_id)
            if not include_internal:
                query = query.filter_by(is_internal=False)
            return query.order_by(Note.created_at.desc()).all()
        except Exception as exc:
            # Backward-compatibility fallback for environments where note schema is behind.
            db.session.rollback()
            logger.warning('Falling back to legacy note query for conversation %s: %s', conversation_id, exc)
            try:
                return Note.query.filter_by(conversation_id=conversation_id).order_by(Note.created_at.desc()).all()
            except Exception as fallback_exc:
                db.session.rollback()
                logger.error('Failed to load notes for conversation %s: %s', conversation_id, fallback_exc)
                return []
