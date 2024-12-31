from celery import Celery, Task, states
from celery.signals import (
    task_failure, worker_ready, worker_shutting_down,
    task_prerun, task_postrun, task_retry, task_success,
    worker_process_init
)
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
import psutil
import signal
from .config import settings
import os
import platform
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseTask(Task):
    """Temel görev sınıfı"""
    abstract = True
    _process_memory_warning = False
    _process_memory_critical = False
    
    def __init__(self):
        self.start_time = None
        self.task_name = self.__class__.__name__
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Görev başarısız olduğunda"""
        duration = self._get_task_duration()
        logger.error(
            f"Görev başarısız - Task: {self.task_name}, ID: {task_id}, "
            f"Süre: {duration:.2f}s, Hata: {str(exc)}, "
            f"Args: {args}, Kwargs: {kwargs}",
            exc_info=einfo
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Görev yeniden denendiğinde"""
        duration = self._get_task_duration()
        logger.warning(
            f"Görev yeniden deneniyor - Task: {self.task_name}, ID: {task_id}, "
            f"Süre: {duration:.2f}s, Deneme: {self.request.retries + 1}, "
            f"Hata: {str(exc)}"
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Görev başarılı olduğunda"""
        duration = self._get_task_duration()
        logger.info(
            f"Görev başarıyla tamamlandı - Task: {self.task_name}, "
            f"ID: {task_id}, Süre: {duration:.2f}s"
        )
        super().on_success(retval, task_id, args, kwargs)
    
    def _get_task_duration(self) -> float:
        """Görev süresini hesapla"""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0
    
    def _check_memory_usage(self):
        """Bellek kullanımını kontrol et"""
        process = psutil.Process()
        memory_percent = process.memory_percent()
        
        if memory_percent > 90 and not self._process_memory_critical:
            logger.critical(
                f"Kritik bellek kullanımı - Task: {self.task_name}, "
                f"Memory: {memory_percent:.1f}%"
            )
            self._process_memory_critical = True
            # Görevi yeniden başlat
            process.kill()
            
        elif memory_percent > 75 and not self._process_memory_warning:
            logger.warning(
                f"Yüksek bellek kullanımı - Task: {self.task_name}, "
                f"Memory: {memory_percent:.1f}%"
            )
            self._process_memory_warning = True

# Celery sinyalleri
@task_prerun.connect
def task_prerun_handler(task_id=None, task=None, *args, **kwargs):
    """Görev başlamadan önce"""
    if isinstance(task, BaseTask):
        task.start_time = datetime.now()
    logger.info(f"Görev başlatılıyor - Task: {task.name}, ID: {task_id}")

@task_postrun.connect
def task_postrun_handler(task_id=None, task=None, state=None, *args, **kwargs):
    """Görev tamamlandıktan sonra"""
    logger.info(f"Görev tamamlandı - Task: {task.name}, ID: {task_id}, State: {state}")

@task_success.connect
def task_success_handler(sender=None, **kwargs):
    """Görev başarılı olduğunda"""
    logger.info(f"Görev başarılı - Task: {sender.name}")

@task_retry.connect
def task_retry_handler(sender=None, reason=None, **kwargs):
    """Görev yeniden denendiğinde"""
    logger.warning(f"Görev yeniden deneniyor - Task: {sender.name}, Sebep: {reason}")

@worker_process_init.connect
def worker_init_handler(**kwargs):
    """Worker process başlatıldığında"""
    logger.info(f"Worker process başlatıldı - PID: {os.getpid()}")

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Worker hazır olduğunda"""
    logger.info(
        f"Celery worker başlatıldı - "
        f"{'Windows-Solo' if platform.system() == 'Windows' else 'Unix-Prefork'}"
    )

@worker_shutting_down.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Worker kapanırken"""
    logger.info("Celery worker kapatılıyor")

def safe_remove_file(file_path: str) -> None:
    """Dosyayı güvenli şekilde sil"""
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            logger.info(f"Geçici dosya silindi: {file_path}")
    except Exception as e:
        logger.error(f"Dosya silme hatası - {file_path}: {str(e)}")

def handle_timeout(signum, frame):
    """Zaman aşımı sinyalini yakala"""
    raise SoftTimeLimitExceeded("Görev zaman aşımına uğradı")

# Zaman aşımı sinyalini kaydet
signal.signal(signal.SIGALRM, handle_timeout)

# Celery uygulamasını oluştur
app = Celery('video_subtitler')

# Celery yapılandırmasını ayarla
app.conf.update(settings.CELERY_CONFIG)

# Windows'ta eventlet kullan
if platform.system() == "Windows":
    os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

@app.task(
    bind=True,
    base=BaseTask,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='10/m',
    time_limit=3600,
    soft_time_limit=3300,
    acks_late=True,
    reject_on_worker_lost=True,
    task_compression='gzip'
)
def process_video(
    self,
    video_path: str,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Video işleme görevi"""
    start_time = datetime.now()
    
    try:
        # Bellek kullanımını kontrol et
        self._check_memory_usage()
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")
            
        logger.info(
            f"Video işleme başladı - Path: {video_path}, "
            f"User: {user_id}, Size: {os.path.getsize(video_path)}"
        )
        
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 0,
                'start_time': start_time.isoformat(),
                'status': 'Başlatılıyor...'
            }
        )
        
        # Video işleme kodları...
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Video işleme tamamlandı - Path: {video_path}, "
            f"User: {user_id}, Süre: {duration:.2f}s"
        )
        
        return {
            "status": "success",
            "result": "subtitles",
            "metadata": metadata,
            "duration": duration,
            "completed_at": datetime.now().isoformat()
        }
        
    except FileNotFoundError as e:
        logger.error(f"Dosya bulunamadı hatası: {str(e)}")
        raise
        
    except SoftTimeLimitExceeded:
        logger.error(f"Video işleme zaman aşımı - Path: {video_path}")
        raise
        
    except Exception as e:
        logger.error(f"Video işleme hatası: {str(e)}", exc_info=True)
        
        # Yeniden deneme sayısını kontrol et
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=e,
                countdown=self.default_retry_delay * (2 ** self.request.retries)
            )
        raise

    finally:
        # Geçici dosyaları temizle
        safe_remove_file(video_path)

@app.task(
    base=BaseTask,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600
)
def cleanup_temp_files():
    """Geçici dosyaları temizle"""
    from .cleanup import cleanup_temp_files
    try:
        cleanup_temp_files()
    except Exception as e:
        logger.error(f"Geçici dosya temizleme hatası: {str(e)}", exc_info=True)
        raise

@app.task(
    base=BaseTask,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600
)
def cleanup_cache():
    """Önbellek temizleme"""
    from .cleanup import cleanup_cache
    try:
        cleanup_cache()
    except Exception as e:
        logger.error(f"Önbellek temizleme hatası: {str(e)}", exc_info=True)
        raise 