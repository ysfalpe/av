from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    """Temel API exception sınıfı"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = None,
        error_type: str = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or f"ERR_{status_code}"
        self.error_type = error_type or self.__class__.__name__
        self.metadata = metadata or {}

class ValidationError(BaseAPIException):
    """Doğrulama hatası"""
    def __init__(self, detail: str, metadata: Dict[str, Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="VALIDATION_ERROR",
            error_type="ValidationError",
            metadata=metadata
        )

class AuthenticationError(BaseAPIException):
    """Kimlik doğrulama hatası"""
    def __init__(self, detail: str = "Kimlik doğrulama başarısız"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTH_ERROR",
            error_type="AuthenticationError"
        )

class AuthorizationError(BaseAPIException):
    """Yetkilendirme hatası"""
    def __init__(self, detail: str = "Bu işlem için yetkiniz yok"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN",
            error_type="AuthorizationError"
        )

class ResourceNotFoundError(BaseAPIException):
    """Kaynak bulunamadı hatası"""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type} bulunamadı: {resource_id}",
            error_code="NOT_FOUND",
            error_type="ResourceNotFoundError",
            metadata={"resource_type": resource_type, "resource_id": resource_id}
        )

class FileProcessingError(BaseAPIException):
    """Dosya işleme hatası"""
    def __init__(self, detail: str, metadata: Dict[str, Any] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="FILE_PROCESSING_ERROR",
            error_type="FileProcessingError",
            metadata=metadata
        )

class AudioProcessingError(BaseAPIException):
    """Ses işleme hatası"""
    def __init__(self, detail: str, metadata: Dict[str, Any] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="AUDIO_PROCESSING_ERROR",
            error_type="AudioProcessingError",
            metadata=metadata
        )

class SubtitleError(BaseAPIException):
    """Alt yazı işleme hatası"""
    def __init__(self, detail: str, metadata: Dict[str, Any] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="SUBTITLE_ERROR",
            error_type="SubtitleError",
            metadata=metadata
        )

class RateLimitError(BaseAPIException):
    """Rate limit hatası"""
    def __init__(self, detail: str = "Çok fazla istek gönderildi"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code="RATE_LIMIT_EXCEEDED",
            error_type="RateLimitError"
        )

class NetworkError(BaseAPIException):
    """Ağ hatası"""
    def __init__(self, detail: str, service: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="NETWORK_ERROR",
            error_type="NetworkError",
            metadata={"service": service} if service else None
        )

class DatabaseError(BaseAPIException):
    """Veritabanı hatası"""
    def __init__(self, detail: str, operation: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="DATABASE_ERROR",
            error_type="DatabaseError",
            metadata={"operation": operation} if operation else None
        )

class CacheError(BaseAPIException):
    """Önbellek hatası"""
    def __init__(self, detail: str, operation: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="CACHE_ERROR",
            error_type="CacheError",
            metadata={"operation": operation} if operation else None
        )

def format_error_response(error: BaseAPIException) -> Dict[str, Any]:
    """Hata yanıtını formatla"""
    response = {
        "error": {
            "code": error.error_code,
            "type": error.error_type,
            "message": error.detail,
            "status_code": error.status_code
        }
    }
    
    if error.metadata:
        response["error"]["metadata"] = error.metadata
        
    return response 