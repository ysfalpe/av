from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import create_engine, text
from celery.app.control import Control
import psutil
import os
from config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def check_redis():
    """Redis bağlantısını kontrol et"""
    try:
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD
        )
        return redis.ping()
    except Exception as e:
        logger.error(f"Redis check failed: {str(e)}")
        return False

def check_database():
    """Database bağlantısını kontrol et"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        return False

def check_celery():
    """Celery worker'ları kontrol et"""
    try:
        control = Control(app=settings.CELERY_APP)
        active_workers = control.ping()
        return len(active_workers) > 0
    except Exception as e:
        logger.error(f"Celery check failed: {str(e)}")
        return False

def check_disk_space():
    """Disk alanını kontrol et"""
    try:
        disk = psutil.disk_usage('/')
        # %90'dan fazla dolu ise uyar
        return disk.percent < 90
    except Exception as e:
        logger.error(f"Disk space check failed: {str(e)}")
        return False

def check_memory():
    """Memory kullanımını kontrol et"""
    try:
        memory = psutil.virtual_memory()
        # %90'dan fazla kullanılıyorsa uyar
        return memory.percent < 90
    except Exception as e:
        logger.error(f"Memory check failed: {str(e)}")
        return False

@router.get("/health")
async def health_check():
    """Basit health check"""
    return {"status": "healthy"}

@router.get("/health/detailed")
async def detailed_health_check():
    """Detaylı health check"""
    checks = {
        "redis": check_redis(),
        "database": check_database(),
        "celery": check_celery(),
        "disk_space": check_disk_space(),
        "memory": check_memory()
    }
    
    # Tüm kontroller başarılı mı?
    all_healthy = all(checks.values())
    
    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks
    }
    
    if not all_healthy:
        # Başarısız kontrolleri logla
        failed_checks = [k for k, v in checks.items() if not v]
        logger.warning(f"Health check failed for: {', '.join(failed_checks)}")
        raise HTTPException(status_code=503, detail=response)
    
    return response

@router.get("/health/liveness")
async def liveness_probe():
    """Kubernetes liveness probe"""
    return {"status": "alive"}

@router.get("/health/readiness")
async def readiness_probe():
    """Kubernetes readiness probe"""
    # Tüm bağımlılıklar hazır mı?
    checks = {
        "redis": check_redis(),
        "database": check_database(),
        "celery": check_celery()
    }
    
    if all(checks.values()):
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Service not ready") 