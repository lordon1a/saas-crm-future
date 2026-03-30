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
    app = None  # Flask app instance for context
    
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
        
        cls.app = app  # Store app instance for context
        
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
        
        # Her dakika: workflow delayed action queue processor
        cls.scheduler.add_job(
            func=cls._process_workflow_queue_job,
            trigger=IntervalTrigger(minutes=1),
            id='workflow_queue_processor',
            name='Process workflow action queue',
            replace_existing=True
        )
        
        # Her gün 00:05: zaman bazlı workflow trigger kontrolü
        from apscheduler.triggers.cron import CronTrigger
        cls.scheduler.add_job(
            func=cls._check_workflow_time_triggers_job,
            trigger=CronTrigger(hour=0, minute=5),
            id='workflow_time_triggers',
            name='Check time-based workflow triggers',
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
    
    @classmethod
    def _send_notifications_job(cls):
        """
        Bildirim gönderme job'ı.
        Her dakika çalışır ve zamanı gelmiş bildirimleri gönderir.
        """
        if not cls.app:
            logger.error("Flask app instance not available for notifications job")
            return
            
        try:
            with cls.app.app_context():
                from services.notification_service import NotificationService
                NotificationService.send_pending_notifications()
        except Exception as e:
            logger.error(f"Bildirim job hatası: {str(e)}", exc_info=True)
    
    @classmethod
    def _check_overdue_tasks_job(cls):
        """
        Overdue görev kontrolü job'ı.
        Her 5 dakikada çalışır ve süresi geçmiş görevleri işaretler.
        Tüm workspace'ler için batch processing yapar.
        """
        if not cls.app:
            logger.error("Flask app instance not available for overdue tasks job")
            return
            
        try:
            with cls.app.app_context():
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
    
    @classmethod
    def _process_workflow_queue_job(cls):
        """
        Workflow delayed action queue processor.
        Her dakika çalışır ve zamanı gelmiş delayed aksiyonları işler.
        """
        if not cls.app:
            logger.error("Flask app instance not available for workflow queue job")
            return
        
        try:
            with cls.app.app_context():
                from services.workflow_service import WorkflowService
                processed = WorkflowService.process_queue()
                if processed > 0:
                    logger.info(f"Workflow queue: processed {processed} delayed actions")
        except Exception as e:
            logger.error(f"Workflow queue job hatası: {str(e)}", exc_info=True)
    
    @classmethod
    def _check_workflow_time_triggers_job(cls):
        """
        Zaman bazlı workflow trigger kontrolü.
        Her gün 00:05'te çalışır ve scheduled triggerları kontrol eder.
        contact_no_activity, deal_close_date_approaching gibi triggerları tetikler.
        """
        if not cls.app:
            logger.error("Flask app instance not available for workflow time triggers job")
            return
        
        try:
            with cls.app.app_context():
                from services.workflow_service import WorkflowService
                WorkflowService.check_time_based_triggers()
                logger.info("Workflow time triggers check completed")
        except Exception as e:
            logger.error(f"Workflow time triggers job hatası: {str(e)}", exc_info=True)
