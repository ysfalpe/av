import os
import time
import platform
import logging
import tempfile
from pathlib import Path
from typing import Optional
from .cache_config import cache_manager
from .config import settings

logger = logging.getLogger(__name__)

def get_temp_dir() -> str:
    """İşletim sistemine uygun geçici dizin yolu"""
    if platform.system() == "Windows":
        base_dir = os.path.join(tempfile.gettempdir(), "video_subtitler")
        os.makedirs(base_dir, exist_ok=True)
        return base_dir
    return settings.UPLOAD_DIR

def safe_delete_file(file_path: Path) -> Optional[str]:
    """Güvenli dosya silme"""
    try:
        if not file_path.exists():
            return None
        if not file_path.is_file():
            return "Dosya değil"
        file_path.unlink()
        return None
    except PermissionError:
        return "Erişim engellendi"
    except OSError as e:
        return f"Sistem hatası: {str(e)}"

def cleanup_temp_files(temp_dir: Optional[str] = None, max_age: int = 3600):
    """Geçici dosyaları temizle"""
    temp_dir = temp_dir or get_temp_dir()
    
    try:
        if not os.path.exists(temp_dir):
            logger.info(f"Temizlenecek dizin bulunamadı: {temp_dir}")
            return
            
        current_time = time.time()
        count = 0
        errors = []
        
        for file_path in Path(temp_dir).glob("*"):
            try:
                # Dosya yaşını kontrol et
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age:
                    error = safe_delete_file(file_path)
                    if error:
                        errors.append(f"{file_path}: {error}")
                    else:
                        count += 1
                        
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
                    
        if count > 0:
            logger.info(f"{count} geçici dosya temizlendi")
        if errors:
            logger.error("Dosya temizleme hataları:\n" + "\n".join(errors))
            
    except Exception as e:
        logger.error(f"Temizleme hatası: {e}")

def cleanup_cache(max_age: int = 86400):
    """Önbelleği temizle"""
    try:
        # Video durumlarını temizle
        pattern = "video_status:*"
        count = 0
        errors = []
        
        for key in cache_manager.redis_client.scan_iter(pattern):
            try:
                # TTL kontrolü
                ttl = cache_manager.redis_client.ttl(key)
                if ttl > max_age or ttl == -1:  # -1 means no expiry
                    if not cache_manager.delete(key):
                        errors.append(f"{key}: Silme başarısız")
                    else:
                        count += 1
            except Exception as e:
                errors.append(f"{key}: {str(e)}")
                
        if count > 0:
            logger.info(f"{count} önbellek anahtarı temizlendi")
        if errors:
            logger.error("Önbellek temizleme hataları:\n" + "\n".join(errors))
            
    except Exception as e:
        logger.error(f"Önbellek temizleme hatası: {e}")
    finally:
        try:
            cache_manager.close()
        except Exception as e:
            logger.error(f"Önbellek bağlantısı kapatılırken hata: {e}")

def cleanup(max_file_age: int = 3600, max_cache_age: int = 86400):
    """Tüm temizleme işlemlerini yap"""
    logger.info(f"Temizlik başlatıldı - {'Windows' if platform.system() == 'Windows' else 'Linux/Unix'}")
    
    # Geçici dosyaları temizle
    cleanup_temp_files(max_age=max_file_age)
    
    # Önbelleği temizle
    cleanup_cache(max_age=max_cache_age)
    
    logger.info("Temizlik tamamlandı")

if __name__ == "__main__":
    cleanup() 