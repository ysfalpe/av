from pydantic_settings import BaseSettings
from pydantic import validator, Field, SecretStr
from typing import List, Union, Optional, Dict, Any
import json
import os
import platform
import tempfile
from pathlib import Path
from datetime import timedelta

class Settings(BaseSettings):
    # Temel ayarlar
    PROJECT_NAME: str = "Video Altyazı Oluşturucu"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # CORS ayarları
    BACKEND_CORS_ORIGINS: List[str] = []
    ALLOWED_HOSTS: List[str] = Field(default=["*"], env="ALLOWED_HOSTS")
    
    # Redis/Memurai ayarları
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[SecretStr] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    REDIS_SOCKET_TIMEOUT: float = Field(default=5.0, env="REDIS_SOCKET_TIMEOUT")
    REDIS_RETRY_COUNT: int = Field(default=3, env="REDIS_RETRY_COUNT")
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30, env="REDIS_HEALTH_CHECK_INTERVAL")
    
    @property
    def REDIS_CONNECTION_URL(self) -> str:
        """İşletim sistemine göre Redis bağlantı URL'i"""
        auth = f":{self.REDIS_PASSWORD.get_secret_value()}@" if self.REDIS_PASSWORD else ""
        base_url = f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        
        if platform.system() == "Windows":
            return base_url  # Windows'ta Memurai kullan
        return self.REDIS_URL or base_url
    
    # Celery ayarları
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    CELERY_TASK_ALWAYS_EAGER: bool = Field(default=False, env="CELERY_TASK_ALWAYS_EAGER")
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(default=50, env="CELERY_WORKER_MAX_TASKS_PER_CHILD")
    CELERY_WORKER_MAX_MEMORY_PER_CHILD: int = Field(default=200000, env="CELERY_WORKER_MAX_MEMORY_PER_CHILD")  # 200MB
    CELERY_TASK_TIME_LIMIT: int = Field(default=3600, env="CELERY_TASK_TIME_LIMIT")  # 1 saat
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=3300, env="CELERY_TASK_SOFT_TIME_LIMIT")  # 55 dakika
    CELERY_TASK_COMPRESSION: str = Field(default="gzip", env="CELERY_TASK_COMPRESSION")
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(default=1, env="CELERY_WORKER_PREFETCH_MULTIPLIER")
    CELERY_BROKER_CONNECTION_MAX_RETRIES: int = Field(default=5, env="CELERY_BROKER_CONNECTION_MAX_RETRIES")
    
    @property
    def CELERY_CONFIG(self) -> Dict[str, Any]:
        """İşletim sistemine göre Celery yapılandırması"""
        base_config = {
            "task_serializer": "json",
            "accept_content": ["json"],
            "result_serializer": "json",
            "timezone": "Europe/Istanbul",
            "enable_utc": True,
            "task_track_started": True,
            "task_time_limit": self.CELERY_TASK_TIME_LIMIT,
            "task_soft_time_limit": self.CELERY_TASK_SOFT_TIME_LIMIT,
            "worker_max_tasks_per_child": self.CELERY_WORKER_MAX_TASKS_PER_CHILD,
            "worker_max_memory_per_child": self.CELERY_WORKER_MAX_MEMORY_PER_CHILD,
            "worker_prefetch_multiplier": self.CELERY_WORKER_PREFETCH_MULTIPLIER,
            "task_always_eager": self.CELERY_TASK_ALWAYS_EAGER,
            "broker_connection_retry_on_startup": True,
            "broker_connection_max_retries": self.CELERY_BROKER_CONNECTION_MAX_RETRIES,
            "task_compression": self.CELERY_TASK_COMPRESSION,
            "task_acks_late": True,
            "task_reject_on_worker_lost": True,
            "task_default_queue": "default",
            "task_queues": {
                "default": {
                    "exchange": "default",
                    "routing_key": "default"
                },
                "high_priority": {
                    "exchange": "high_priority",
                    "routing_key": "high_priority"
                }
            }
        }
        
        if platform.system() == "Windows":
            base_config.update({
                "broker_url": self.REDIS_CONNECTION_URL,
                "result_backend": self.REDIS_CONNECTION_URL,
                "worker_pool": "solo",
                "broker_connection_retry": True
            })
        else:
            base_config.update({
                "broker_url": self.CELERY_BROKER_URL,
                "result_backend": self.CELERY_RESULT_BACKEND,
                "worker_pool": "prefork",
                "broker_connection_retry": True
            })
            
        return base_config
    
    # Dosya işleme ayarları
    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, env="MAX_FILE_SIZE")  # 100MB
    MAX_VIDEO_DURATION: int = Field(default=600, env="MAX_VIDEO_DURATION")  # 10 dakika
    ALLOWED_VIDEO_FORMATS: List[str] = ["video/mp4", "video/x-msvideo", "video/quicktime", "video/webm"]
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".avi", ".mov", ".webm"]
    UPLOAD_DIR: str = Field(default="/tmp/uploads", env="UPLOAD_DIR")
    TEMP_DIR: str = Field(default=tempfile.gettempdir(), env="TEMP_DIR")
    CHUNK_SIZE: int = Field(default=8192, env="CHUNK_SIZE")  # 8KB
    
    @validator("UPLOAD_DIR")
    def validate_upload_dir(cls, v: str) -> str:
        """Upload dizinini doğrula ve oluştur"""
        path = Path(v)
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Dizin izinlerini kontrol et
            if not os.access(path, os.W_OK):
                raise ValueError(f"Dizine yazma izni yok: {v}")
        except Exception as e:
            raise ValueError(f"Dizin oluşturma hatası: {str(e)}")
        return str(path)
    
    # Güvenlik ayarları
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    SECURE_HEADERS: bool = Field(default=True, env="SECURE_HEADERS")
    MIN_PASSWORD_LENGTH: int = Field(default=8, env="MIN_PASSWORD_LENGTH")
    PASSWORD_REGEX: str = Field(
        default=r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$",
        env="PASSWORD_REGEX"
    )
    
    @property
    def ACCESS_TOKEN_EXPIRE_DELTA(self) -> timedelta:
        """Token geçerlilik süresi"""
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Rate limiting
    RATE_LIMIT: str = Field(default="10/hour", env="RATE_LIMIT")
    RATE_LIMIT_STORAGE_URL: Optional[str] = Field(default=None, env="RATE_LIMIT_STORAGE_URL")
    
    # Storage
    STORAGE_TYPE: str = Field(default="local", env="STORAGE_TYPE")
    S3_BUCKET: Optional[str] = Field(default=None, env="S3_BUCKET")
    S3_ACCESS_KEY: Optional[SecretStr] = Field(default=None, env="S3_ACCESS_KEY")
    S3_SECRET_KEY: Optional[SecretStr] = Field(default=None, env="S3_SECRET_KEY")
    S3_REGION: Optional[str] = Field(default=None, env="S3_REGION")
    S3_ENDPOINT_URL: Optional[str] = Field(default=None, env="S3_ENDPOINT_URL")
    
    # Log ayarları
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    LOG_DIR: str = Field(default="logs", env="LOG_DIR")
    LOG_FILE_MAX_BYTES: int = Field(default=10485760, env="LOG_FILE_MAX_BYTES")  # 10MB
    LOG_FILE_BACKUP_COUNT: int = Field(default=5, env="LOG_FILE_BACKUP_COUNT")
    
    @validator("LOG_DIR")
    def validate_log_dir(cls, v: str) -> str:
        """Log dizinini doğrula ve oluştur"""
        path = Path(v)
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Dizin izinlerini kontrol et
            if not os.access(path, os.W_OK):
                raise ValueError(f"Dizine yazma izni yok: {v}")
        except Exception as e:
            raise ValueError(f"Dizin oluşturma hatası: {str(e)}")
        return str(path)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name == "BACKEND_CORS_ORIGINS":
                try:
                    return json.loads(raw_val)
                except Exception:
                    return [i.strip() for i in raw_val.split(",")]
            elif field_name == "ALLOWED_HOSTS":
                try:
                    return json.loads(raw_val)
                except Exception:
                    return [i.strip() for i in raw_val.split(",")]
            return raw_val

settings = Settings()