import logging
import time
import uuid
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from ..logger_config import LoggerAdapter

request_logger = logging.getLogger("request")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """İstek loglarını tutan middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # İstek ID'si oluştur
        request_id = str(uuid.uuid4())
        
        # İstek başlangıç zamanı
        start_time = time.time()
        
        # İstek bilgilerini topla
        request_info = await self._get_request_info(request)
        request_info["request_id"] = request_id
        
        # Logger adapter oluştur
        logger = LoggerAdapter(request_logger, {"request_id": request_id})
        
        # İstek başlangıcını logla
        logger.info(
            "İstek alındı",
            extra={"metadata": request_info}
        )
        
        try:
            # İsteği işle
            response = await call_next(request)
            
            # İşlem süresini hesapla
            process_time = time.time() - start_time
            
            # Yanıt bilgilerini topla
            response_info = self._get_response_info(response, process_time)
            response_info["request_id"] = request_id
            
            # Başarılı yanıtı logla
            logger.info(
                "Yanıt gönderildi",
                extra={"metadata": response_info}
            )
            
            return response
            
        except Exception as e:
            # İşlem süresini hesapla
            process_time = time.time() - start_time
            
            # Hata bilgilerini topla
            error_info = {
                "request_id": request_id,
                "error": str(e),
                "error_type": e.__class__.__name__,
                "process_time_ms": round(process_time * 1000, 2)
            }
            
            # Hatayı logla
            logger.error(
                "İstek işlenirken hata oluştu",
                extra={"metadata": error_info},
                exc_info=True
            )
            
            raise
    
    async def _get_request_info(self, request: Request) -> Dict[str, Any]:
        """İstek bilgilerini topla"""
        headers = dict(request.headers)
        # Hassas bilgileri temizle
        if "authorization" in headers:
            headers["authorization"] = "***"
        if "cookie" in headers:
            headers["cookie"] = "***"
            
        info = {
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "client_host": request.client.host if request.client else None,
            "path_params": dict(request.path_params),
            "query_params": dict(request.query_params)
        }
        
        # İstek gövdesini ekle (eğer JSON ise)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                # Hassas alanları temizle
                if isinstance(body, dict):
                    if "password" in body:
                        body["password"] = "***"
                    if "token" in body:
                        body["token"] = "***"
                info["body"] = body
            except:
                pass
                
        return info
    
    def _get_response_info(self, response: Response, process_time: float) -> Dict[str, Any]:
        """Yanıt bilgilerini topla"""
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "process_time_ms": round(process_time * 1000, 2)
        } 