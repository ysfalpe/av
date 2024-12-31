import redis
import platform
import json
import logging
import time
from typing import Any, Optional, Dict
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError
from .config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """Önbellek yönetimi sınıfı"""
    
    def __init__(self):
        self._redis_client = None
        self._retry_count = settings.REDIS_RETRY_COUNT
        self._retry_delay = 1
        self._connection_pool = None
        self._max_connections = settings.REDIS_MAX_CONNECTIONS
        self._socket_timeout = settings.REDIS_SOCKET_TIMEOUT
        self._last_health_check = 0
        self._health_check_interval = 30  # saniye
        
    def _create_connection_pool(self):
        """Bağlantı havuzu oluştur"""
        if not self._connection_pool:
            pool_kwargs = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "max_connections": self._max_connections,
                "socket_timeout": self._socket_timeout,
                "socket_connect_timeout": 2.0,
                "socket_keepalive": True,
                "health_check_interval": self._health_check_interval
            }
            
            if settings.REDIS_PASSWORD:
                pool_kwargs["password"] = settings.REDIS_PASSWORD
                
            self._connection_pool = redis.ConnectionPool(**pool_kwargs)
            logger.info("Redis bağlantı havuzu oluşturuldu")
    
    def _check_connection_health(self) -> bool:
        """Bağlantı sağlığını kontrol et"""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return True
            
        try:
            if self._redis_client and self._redis_client.ping():
                self._last_health_check = current_time
                return True
        except Exception as e:
            logger.warning(f"Sağlık kontrolü başarısız: {str(e)}")
            self._cleanup_connection()
        return False
    
    @property
    def redis_client(self) -> redis.Redis:
        """Redis/Memurai bağlantısı"""
        if not self._check_connection_health():
            try:
                self._create_connection_pool()
                retry = Retry(ExponentialBackoff(), self._retry_count)
                self._redis_client = redis.Redis(
                    connection_pool=self._connection_pool,
                    decode_responses=True,
                    retry=retry,
                    retry_on_timeout=True
                )
                if not self._redis_client.ping():
                    raise ConnectionError("Ping başarısız")
                logger.info(f"{'Memurai' if platform.system() == 'Windows' else 'Redis'} bağlantısı başarılı")
                self._last_health_check = time.time()
            except Exception as e:
                logger.error(f"Önbellek bağlantı hatası: {str(e)}")
                self._cleanup_connection()
                raise
        return self._redis_client
    
    def _cleanup_connection(self):
        """Bağlantı temizleme"""
        if self._redis_client:
            try:
                self._redis_client.close()
            except:
                pass
            self._redis_client = None
        
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
            except:
                pass
            self._connection_pool = None
    
    def _retry_operation(self, operation, key: str = None):
        """Operasyonu yeniden deneme mekanizması"""
        last_error = None
        operation_name = operation.__name__ if hasattr(operation, '__name__') else 'unknown'
        
        for attempt in range(self._retry_count):
            if not self._check_connection_health():
                logger.warning("Bağlantı sağlıksız, yeniden bağlanılıyor...")
                continue
                
            try:
                result = operation()
                if attempt > 0:
                    logger.info(f"Operasyon başarılı (deneme {attempt + 1})")
                return result
            except (ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt == self._retry_count - 1:
                    break
                    
                delay = self._retry_delay * (2 ** attempt)
                logger.warning(
                    f"Önbellek operasyonu başarısız - Op: {operation_name}, "
                    f"Key: {key}, Deneme: {attempt + 1}/{self._retry_count}, "
                    f"Hata: {str(e)}, Bekleme: {delay}s"
                )
                time.sleep(delay)
                self._cleanup_connection()
        
        error_msg = (
            f"Önbellek operasyonu maksimum deneme sayısına ulaştı - "
            f"Op: {operation_name}, Key: {key}, Hata: {str(last_error)}"
        )
        logger.error(error_msg)
        raise last_error
    
    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Önbellekten veri al"""
        try:
            result = self._retry_operation(
                lambda: self.redis_client.get(key),
                key=key
            )
            if not result:
                return default
                
            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"JSON çözümleme hatası ({key}): {str(e)}")
                return default
                
        except Exception as e:
            logger.error(f"Önbellek okuma hatası ({key}): {str(e)}")
            return default
    
    def set(self, key: str, value: Any, expire: int = None) -> bool:
        """Önbelleğe veri kaydet"""
        try:
            try:
                data = json.dumps(value)
            except (TypeError, ValueError) as e:
                logger.error(f"Serileştirme hatası ({key}): {str(e)}")
                return False
                
            return self._retry_operation(
                lambda: bool(
                    self.redis_client.setex(key, expire, data)
                    if expire else self.redis_client.set(key, data)
                ),
                key=key
            )
        except Exception as e:
            logger.error(f"Önbellek yazma hatası ({key}): {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Önbellekten veri sil"""
        try:
            return self._retry_operation(
                lambda: bool(self.redis_client.delete(key)),
                key=key
            )
        except Exception as e:
            logger.error(f"Önbellek silme hatası ({key}): {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """Anahtarın varlığını kontrol et"""
        try:
            return self._retry_operation(
                lambda: bool(self.redis_client.exists(key)),
                key=key
            )
        except Exception as e:
            logger.error(f"Önbellek kontrol hatası ({key}): {str(e)}")
            return False
    
    def set_video_status(self, video_id: str, status: Dict[str, Any], expire: int = 3600) -> bool:
        """Video işleme durumunu kaydet"""
        key = f"video_status:{video_id}"
        if not isinstance(status, dict):
            logger.error(f"Geçersiz durum verisi ({key}): {status}")
            return False
        return self.set(key, status, expire)
    
    def get_video_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Video işleme durumunu al"""
        key = f"video_status:{video_id}"
        status = self.get(key)
        if status and not isinstance(status, dict):
            logger.error(f"Geçersiz durum verisi ({key}): {status}")
            return None
        return status
    
    def clear_video_status(self, video_id: str) -> bool:
        """Video işleme durumunu sil"""
        return self.delete(f"video_status:{video_id}")
    
    def close(self):
        """Bağlantıyı kapat"""
        self._cleanup_connection()
        logger.info("Önbellek bağlantısı kapatıldı")

# Singleton cache manager instance
cache_manager = CacheManager() 