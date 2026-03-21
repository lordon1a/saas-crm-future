"""
Notification Service - Business logic for task notifications
Handles notification sending, status updates, and user preferences
"""
from models import db
from models_crm import TaskNotification, NotificationPreference
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing task notifications"""
    
    @staticmethod
    def send_pending_notifications():
        """
        Gönderilmemiş bildirimleri kontrol et ve gönder.
        Background job tarafından her dakika çağrılır.
        """
        now = datetime.utcnow()
        
        # Gönderilmemiş ve zamanı gelmiş bildirimleri bul
        pending = TaskNotification.query.filter(
            TaskNotification.is_sent == False,
            TaskNotification.notify_at <= now
        ).limit(100).all()  # Performans için limit
        
        for notification in pending:
            try:
                # Socket.IO ile gönder
                NotificationService._emit_notification(notification)
                
                # Durumu güncelle
                notification.mark_as_sent()
                
            except Exception as e:
                logger.error(f"Bildirim gönderilemedi: {notification.id}, Hata: {str(e)}")
        
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Bildirim commit hatası: {str(e)}")
            db.session.rollback()
    
    @staticmethod
    def _emit_notification(notification):
        """
        Socket.IO ile bildirim gönder.
        
        Args:
            notification: TaskNotification instance
        """
        from realtime import socketio
        
        # Kullanıcının room'una gönder
        room = f"user_{notification.user_id}"
        
        socketio.emit('new_notification', {
            'id': notification.id,
            'task_id': notification.task_id,
            'message': notification.message,
            'type': notification.notification_type,
            'created_at': notification.created_at.isoformat(),
        }, room=room)
    
    @staticmethod
    def get_user_notifications(workspace_id, user_id, unread_only=False, limit=50):
        """
        Kullanıcının bildirimlerini getir.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
            unread_only: Sadece okunmamışlar
            limit: Maksimum kayıt sayısı (max 100)
        
        Returns:
            List[TaskNotification]: Bildirimler
        """
        # Limit kontrolü
        if limit > 100:
            limit = 100
        
        query = TaskNotification.query.filter(
            TaskNotification.workspace_id == workspace_id,
            TaskNotification.user_id == user_id,
            TaskNotification.is_sent == True
        )
        
        if unread_only:
            query = query.filter(TaskNotification.is_read == False)
        
        return query.order_by(
            TaskNotification.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_unread_count(workspace_id, user_id):
        """
        Okunmamış bildirim sayısı.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
        
        Returns:
            int: Okunmamış bildirim sayısı
        """
        return TaskNotification.query.filter(
            TaskNotification.workspace_id == workspace_id,
            TaskNotification.user_id == user_id,
            TaskNotification.is_sent == True,
            TaskNotification.is_read == False
        ).count()
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """
        Bildirimi okundu olarak işaretle.
        
        Args:
            notification_id: Bildirim ID
            user_id: Kullanıcı ID (yetki kontrolü için)
        
        Returns:
            bool: Başarılı ise True
        """
        notification = TaskNotification.query.filter_by(
            id=notification_id,
            user_id=user_id
        ).first()
        
        if not notification:
            return False
        
        notification.mark_as_read()
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Bildirim okundu işaretleme hatası: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def mark_all_as_read(workspace_id, user_id):
        """
        Tüm bildirimleri okundu olarak işaretle.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
        
        Returns:
            int: Güncellenen kayıt sayısı
        """
        try:
            count = TaskNotification.query.filter(
                TaskNotification.workspace_id == workspace_id,
                TaskNotification.user_id == user_id,
                TaskNotification.is_read == False
            ).update({
                'is_read': True,
                'read_at': datetime.utcnow()
            })
            
            db.session.commit()
            return count
        except Exception as e:
            logger.error(f"Tüm bildirimleri okundu işaretleme hatası: {str(e)}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def get_or_create_preferences(workspace_id, user_id):
        """
        Kullanıcı bildirim tercihlerini getir veya oluştur.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
        
        Returns:
            NotificationPreference: Tercihler
        """
        pref = NotificationPreference.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id
        ).first()
        
        if not pref:
            pref = NotificationPreference(
                workspace_id=workspace_id,
                user_id=user_id
            )
            db.session.add(pref)
            
            try:
                db.session.commit()
            except Exception as e:
                logger.error(f"Bildirim tercihleri oluşturma hatası: {str(e)}")
                db.session.rollback()
        
        return pref
    
    @staticmethod
    def update_preferences(workspace_id, user_id, data):
        """
        Bildirim tercihlerini güncelle.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
            data: Güncellenecek tercihler
        
        Returns:
            NotificationPreference: Güncellenmiş tercihler
        """
        pref = NotificationService.get_or_create_preferences(workspace_id, user_id)
        
        # Güvenli alan listesi
        allowed_fields = [
            'task_reminder_enabled',
            'task_overdue_enabled',
            'task_assigned_enabled',
            'task_updated_enabled',
            'reminder_minutes_before'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(pref, field, data[field])
        
        pref.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Bildirim tercihleri güncelleme hatası: {str(e)}")
            db.session.rollback()
        
        return pref
