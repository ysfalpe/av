from fastapi import Request, Response
from typing import Callable
import re
import html
import json
from ..config import settings

class SecurityMiddleware:
    def __init__(
        self,
        app,
        allowed_hosts: list = None,
        enable_xss_protection: bool = True,
        enable_content_security: bool = True,
        enable_frame_protection: bool = True
    ):
        self.app = app
        self.allowed_hosts = allowed_hosts or ["*"]
        self.enable_xss_protection = enable_xss_protection
        self.enable_content_security = enable_content_security
        self.enable_frame_protection = enable_frame_protection

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        
        # Host kontrolü
        if not self._is_valid_host(request.headers.get("host", "")):
            return await self._send_error_response(send, "Geçersiz host")

        # Response header'larını ayarla
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                if self.enable_xss_protection:
                    headers.extend([
                        (b"X-XSS-Protection", b"1; mode=block"),
                        (b"X-Content-Type-Options", b"nosniff"),
                    ])

                if self.enable_content_security:
                    headers.append((
                        b"Content-Security-Policy",
                        b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                        b"style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                        b"font-src 'self' data:; connect-src 'self'"
                    ))

                if self.enable_frame_protection:
                    headers.append((b"X-Frame-Options", b"DENY"))

                message["headers"] = headers

            await send(message)

        return await self.app(scope, receive, send_wrapper)

    def _is_valid_host(self, host: str) -> bool:
        if not host:
            return False
        
        # Port numarasını kaldır
        host = host.split(":")[0]
        
        return "*" in self.allowed_hosts or host in self.allowed_hosts

    async def _send_error_response(self, send: Callable, message: str):
        response = Response(
            content=json.dumps({"detail": message}),
            status_code=400,
            media_type="application/json"
        )
        
        await response(scope, receive, send)

class XSSProtection:
    """XSS saldırılarına karşı koruma sağlayan middleware"""
    
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        receive_wrapper = self._create_receive_wrapper(receive)
        send_wrapper = self._create_send_wrapper(send)

        return await self.app(scope, receive_wrapper, send_wrapper)

    async def _create_receive_wrapper(self, receive):
        async def receive_wrapper():
            message = await receive()
            
            if message["type"] == "http.request":
                # Request body'sini temizle
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body)
                        cleaned_data = self._clean_data(data)
                        message["body"] = json.dumps(cleaned_data).encode()
                    except json.JSONDecodeError:
                        # JSON değilse string olarak temizle
                        message["body"] = self._clean_string(body.decode()).encode()

            return message

        return receive_wrapper

    async def _create_send_wrapper(self, send):
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Content-Security-Policy", b"default-src 'self'")
                ])
                message["headers"] = headers

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body)
                        cleaned_data = self._clean_data(data)
                        message["body"] = json.dumps(cleaned_data).encode()
                    except json.JSONDecodeError:
                        message["body"] = self._clean_string(body.decode()).encode()

            await send(message)

        return send_wrapper

    def _clean_data(self, data):
        """Recursive olarak tüm string değerleri temizle"""
        if isinstance(data, dict):
            return {k: self._clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_data(item) for item in data]
        elif isinstance(data, str):
            return self._clean_string(data)
        return data

    def _clean_string(self, text: str) -> str:
        """String'i XSS saldırılarına karşı temizle"""
        # HTML karakterlerini escape et
        text = html.escape(text)
        
        # Tehlikeli karakterleri temizle
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'data:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'vbscript:', '', text, flags=re.IGNORECASE)
        
        return text

class RateLimitByIP:
    """IP bazlı rate limiting middleware"""
    
    def __init__(self, app, limit: str = "100/minute"):
        self.app = app
        self.limit = limit
        self.requests = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        client = scope.get("client", [None, None])[0]
        if not client:
            return await self.app(scope, receive, send)

        # Rate limit kontrolü
        if not self._check_rate_limit(client):
            return await self._send_rate_limit_response(send)

        return await self.app(scope, receive, send)

    def _check_rate_limit(self, ip: str) -> bool:
        """IP bazlı rate limit kontrolü"""
        import time
        current_time = time.time()
        
        # Eski kayıtları temizle
        self._cleanup_old_requests(current_time)
        
        # İstek sayısını kontrol et
        requests = self.requests.get(ip, {"count": 0, "reset_time": current_time})
        
        if requests["count"] >= self._get_limit_count():
            return False
        
        # İstek sayısını artır
        requests["count"] += 1
        self.requests[ip] = requests
        
        return True

    def _cleanup_old_requests(self, current_time: float):
        """Süresi dolmuş kayıtları temizle"""
        window = self._get_limit_window()
        self.requests = {
            ip: data
            for ip, data in self.requests.items()
            if current_time - data["reset_time"] < window
        }

    def _get_limit_count(self) -> int:
        """Limit sayısını al"""
        return int(self.limit.split("/")[0])

    def _get_limit_window(self) -> int:
        """Limit penceresini saniye cinsinden al"""
        unit = self.limit.split("/")[1]
        if unit == "second":
            return 1
        elif unit == "minute":
            return 60
        elif unit == "hour":
            return 3600
        elif unit == "day":
            return 86400
        return 60  # Varsayılan: 1 dakika

    async def _send_rate_limit_response(self, send: Callable):
        """Rate limit aşıldığında hata mesajı gönder"""
        response = Response(
            content=json.dumps({
                "detail": "Çok fazla istek gönderildi. Lütfen daha sonra tekrar deneyin."
            }),
            status_code=429,
            media_type="application/json"
        )
        
        await response(scope, receive, send) 