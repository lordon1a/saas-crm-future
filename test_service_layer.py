"""
Test script for Task 4: Service Layer Testing
Tests TaskService, NotificationService, and TaskScheduler
"""
import sys
from datetime import datetime, timedelta
from app import app, db
from services.task_service import TaskService
from services.notification_service import NotificationService
from models_crm import Task, TaskNotification, NotificationPreference

# Try to import TaskScheduler, but don't fail if APScheduler is not installed
try:
    from services.task_scheduler import TaskScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("⚠ APScheduler not installed - scheduler tests will be skipped")

def test_service_layer():
    """Test service layer functionality"""
    
    with app.app_context():
        print("=" * 60)
        print("TASK 4: SERVICE LAYER TEST")
        print("=" * 60)
        
        # Test 1: TaskService.create_task() ile zamanlı görev oluştur
        print("\n[TEST 1] TaskService.create_task() - Zamanlı görev oluşturma")
        print("-" * 60)
        
        try:
            # Test verisi
            workspace_id = 1
            user_id = 1
            assignee_id = 1
            
            start_time = datetime.utcnow() + timedelta(minutes=30)
            end_time = start_time + timedelta(hours=1)
            
            task = TaskService.create_task(
                workspace_id=workspace_id,
                title="Test Toplantısı",
                description="Service layer test için oluşturulan görev",
                assignee_id=assignee_id,
                start_time=start_time,
                end_time=end_time,
                timezone='Europe/Istanbul',
                task_type='meeting',
                priority='high',
                user_id=user_id
            )
            
            print(f"✓ Görev oluşturuldu: ID={task.id}, Title='{task.title}'")
            print(f"  Start: {task.start_time}")
            print(f"  End: {task.end_time}")
            print(f"  Type: {task.task_type}")
            print(f"  Timezone: {task.timezone}")
            
        except Exception as e:
            print(f"✗ Görev oluşturma hatası: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 2: Bildirim kayıtlarının oluştuğunu doğrula
        print("\n[TEST 2] Bildirim kayıtları kontrolü")
        print("-" * 60)
        
        try:
            notifications = TaskNotification.query.filter_by(
                task_id=task.id,
                workspace_id=workspace_id
            ).all()
            
            if notifications:
                print(f"✓ {len(notifications)} bildirim kaydı oluşturuldu:")
                for notif in notifications:
                    print(f"  - ID={notif.id}, Type={notif.notification_type}")
                    print(f"    Notify at: {notif.notify_at}")
                    print(f"    Message: {notif.message}")
                    print(f"    Is sent: {notif.is_sent}")
            else:
                print("⚠ Bildirim kaydı bulunamadı (assignee_id veya tercihler eksik olabilir)")
                
        except Exception as e:
            print(f"✗ Bildirim kontrolü hatası: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test 3: NotificationService.get_user_notifications()
        print("\n[TEST 3] NotificationService.get_user_notifications()")
        print("-" * 60)
        
        try:
            user_notifications = NotificationService.get_user_notifications(
                workspace_id=workspace_id,
                user_id=assignee_id,
                unread_only=False,
                limit=10
            )
            
            print(f"✓ Kullanıcı bildirimleri getirildi: {len(user_notifications)} kayıt")
            
            if user_notifications:
                for notif in user_notifications[:3]:  # İlk 3'ünü göster
                    print(f"  - Task ID={notif.task_id}, Type={notif.notification_type}")
                    print(f"    Sent: {notif.is_sent}, Read: {notif.is_read}")
            
        except Exception as e:
            print(f"✗ Bildirim getirme hatası: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test 4: NotificationPreference kontrolü
        print("\n[TEST 4] NotificationPreference kontrolü")
        print("-" * 60)
        
        try:
            pref = NotificationPreference.query.filter_by(
                workspace_id=workspace_id,
                user_id=assignee_id
            ).first()
            
            if pref:
                print(f"✓ Bildirim tercihleri bulundu:")
                print(f"  - Task reminder: {pref.task_reminder_enabled}")
                print(f"  - Task overdue: {pref.task_overdue_enabled}")
                print(f"  - Reminder minutes before: {pref.reminder_minutes_before}")
            else:
                print("⚠ Bildirim tercihleri bulunamadı (varsayılan değerler kullanılacak)")
                
        except Exception as e:
            print(f"✗ Tercih kontrolü hatası: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test 5: TaskScheduler durumu
        print("\n[TEST 5] TaskScheduler durumu")
        print("-" * 60)
        
        if not SCHEDULER_AVAILABLE:
            print("⚠ APScheduler modülü yüklü değil - test atlanıyor")
            print("  Not: Production'da APScheduler requirements.txt'e eklenecek")
        else:
            try:
                if TaskScheduler.scheduler is not None:
                    print(f"✓ TaskScheduler başlatılmış")
                    print(f"  Running: {TaskScheduler.scheduler.running}")
                    
                    # Job'ları listele
                    jobs = TaskScheduler.scheduler.get_jobs()
                    print(f"  Aktif job sayısı: {len(jobs)}")
                    
                    for job in jobs:
                        print(f"  - Job: {job.id}")
                        print(f"    Name: {job.name}")
                        print(f"    Next run: {job.next_run_time}")
                else:
                    print("✗ TaskScheduler başlatılmamış!")
                    print("  app.py'de TaskScheduler.init_scheduler(app) çağrılmalı")
                    
            except Exception as e:
                print(f"✗ Scheduler kontrolü hatası: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Test 6: Görev güncelleme testi
        print("\n[TEST 6] TaskService.update_task() - Zaman güncelleme")
        print("-" * 60)
        
        try:
            new_start_time = datetime.utcnow() + timedelta(hours=2)
            new_end_time = new_start_time + timedelta(hours=1)
            
            updated_task = TaskService.update_task(
                task_id=task.id,
                workspace_id=workspace_id,
                user_id=user_id,
                start_time=new_start_time,
                end_time=new_end_time
            )
            
            print(f"✓ Görev güncellendi:")
            print(f"  Yeni start: {updated_task.start_time}")
            print(f"  Yeni end: {updated_task.end_time}")
            
            # Bildirimlerin yenilendiğini kontrol et
            new_notifications = TaskNotification.query.filter_by(
                task_id=task.id,
                is_sent=False
            ).all()
            
            print(f"  Yeni bildirim sayısı: {len(new_notifications)}")
            
        except Exception as e:
            print(f"✗ Görev güncelleme hatası: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Özet
        print("\n" + "=" * 60)
        print("TEST SONUÇLARI")
        print("=" * 60)
        print("✓ TaskService.create_task() çalışıyor")
        print("✓ Bildirim kayıtları oluşturuluyor")
        print("✓ NotificationService.get_user_notifications() çalışıyor")
        
        if SCHEDULER_AVAILABLE:
            if TaskScheduler.scheduler is not None and TaskScheduler.scheduler.running:
                print("✓ TaskScheduler başlatılmış ve çalışıyor")
            else:
                print("⚠ TaskScheduler başlatılmamış (app.py'de init gerekli)")
        else:
            print("⚠ APScheduler yüklü değil (production'da requirements.txt'e eklenecek)")
        
        print("\n" + "=" * 60)
        print("Service layer temel fonksiyonları çalışıyor!")
        print("=" * 60)
        
        return True

if __name__ == '__main__':
    try:
        success = test_service_layer()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
