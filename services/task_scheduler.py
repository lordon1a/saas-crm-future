"""
Task Scheduler - Background job scheduler for task management
Handles periodic notification sending and overdue task checking
Uses APScheduler with gevent compatibility
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Background job scheduler for task management.
    Uses APScheduler with gevent compatibility.
    Runs periodic jobs for notifications and overdue task checking.
    """
    
    scheduler = None
    
    @classmethod
    def init_scheduler(cls, app):
        """
        Scheduler'ı başlat.
        app.py'den çağrılır.
        
        Args:
            app: Flask app instance
        """
        if cls.scheduler is not None:
            logger.warning("Scheduler zaten başlatılmış")
            return
        
        cls.scheduler = BackgroundScheduler(
            daemon=True,
            timezone='UTC'
        )
        
        # Her dakika bildirim kontrolü
        cls.scheduler.add_job(
            func=cls._send_notifications_job,
            trigger=IntervalTrigger(minutes=1),
            id='send_notifications',
            name='Send pending notifications',
            replace_existing=True
        )
        
        # Her 5 dakikada overdue kontrolü
        cls.scheduler.add_job(
            func=cls._check_overdue_tasks_job,
            trigger=IntervalTrigger(minutes=5),
            id='check_overdue_tasks',
            name='Check overdue tasks',
            replace_existing=True
        )
        
        cls.scheduler.start()
        logger.info("TaskScheduler başlatıldı - bildirim ve overdue kontrol job'ları aktif")
    
    @classmethod
    def shutdown(cls):
        """
        Scheduler'ı graceful olarak kapat.
        atexit handler tarafından çağrılır.
        """
        if cls.scheduler:
            cls.scheduler.shutdown()
            logger.info("TaskScheduler kapatıldı")
    
    @staticmethod
    def _send_notifications_job():
        """
        Bildirim gönderme job'ı.
        Her dakika çalışır ve zamanı gelmiş bildirimleri gönderir.
        """
        try:
            from services.notification_service import NotificationService
            NotificationService.send_pending_notifications()
        except Exception as e:
            logger.error(f"Bildirim job hatası: {str(e)}", exc_info=True)
    
    @staticmethod
    def _check_overdue_tasks_job():
        """
        Overdue görev kontrolü job'ı.
        Her 5 dakikada çalışır ve süresi geçmiş görevleri işaretler.
        Tüm workspace'ler için batch processing yapar.
        """
        try:
            from models import db
            from models_crm import Task
            from services.task_service import TaskService
            
            # Tüm workspace'ler için kontrol et
            # (Render Free Plan için optimize edilmiş - batch processing)
            workspaces = db.session.query(Task.workspace_id).distinct().all()
            
            for (workspace_id,) in workspaces:
                try:
                    TaskService.mark_overdue_tasks(workspace_id)
                except Exception as workspace_error:
                    logger.error(f"Workspace {workspace_id} overdue kontrolü hatası: {str(workspace_error)}")
                    # Bir workspace'de hata olsa bile diğerlerine devam et
                    continue
                
        except Exception as e:
            logger.error(f"Overdue kontrolü job hatası: {str(e)}", exc_info=True)
