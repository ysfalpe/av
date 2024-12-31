from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks, Query, Depends, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import tempfile
from moviepy.video.io.VideoFileClip import VideoFileClip
from vosk import Model, KaldiRecognizer
import json
import wave
import asyncio
from typing import List, Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import magic
import time
import hashlib
import redis.asyncio as aioredis
from tasks import process_video
from subtitle_utils import create_srt, create_vtt, adjust_timing, merge_nearby_subtitles, create_subtitled_video
from audio_utils import normalize_audio, get_audio_stats
from logger import app_logger, request_logger
from exceptions import (
    ValidationError, FileProcessingError, AudioProcessingError,
    SubtitleError, RateLimitError, NetworkError, format_error_response
)
from fastapi.security import APIKeyCookie, HTTPBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
import secrets
from logger_config import setup_logging
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from .auth import (
    Token, User, fake_users_db, authenticate_user, create_access_token,
    get_current_active_user, generate_csrf_token
)
from .services.video_validator import VideoValidator
from .schemas import VideoUploadRequest, VideoValidationResult
from .middleware.security import SecurityMiddleware, XSSProtection, RateLimitByIP
from .middleware.request_logging import RequestLoggingMiddleware
from .error_handlers import api_exception_handler, unhandled_exception_handler
from .exceptions import BaseAPIException

# Redis bağlantısı
redis = None

async def get_redis():
    global redis
    if redis is None:
        try:
            redis = await aioredis.from_url(
                os.getenv("REDIS_URL"),
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
                max_connections=10
            )
        except Exception as e:
            app_logger.error(f"Redis bağlantı hatası: {str(e)}")
            raise NetworkError("Redis servisine bağlanılamadı")
    return redis

# Rate limiter oluştur
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=json.loads(settings.BACKEND_CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Güvenlik middleware'leri
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    SecurityMiddleware,
    allowed_hosts=json.loads(settings.BACKEND_CORS_ORIGINS),
    enable_xss_protection=True,
    enable_content_security=True,
    enable_frame_protection=True
)
app.add_middleware(XSSProtection)
app.add_middleware(
    RateLimitByIP,
    limit=settings.RATE_LIMIT
)
app.add_middleware(RequestLoggingMiddleware)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Vosk modelini yükle
if not os.path.exists("model"):
    raise RuntimeError("Lütfen Vosk modelini 'model' klasörüne indirin")
model = Model("model")

# Dosya kontrolleri
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.webm'}
MAX_DURATION = 600  # 10 dakika

# MIME type kontrolleri
ALLOWED_MIME_TYPES = {
    'video/mp4',
    'video/x-msvideo',
    'video/quicktime',
    'video/webm'
}

def validate_video_mime(file_path: str) -> tuple[bool, str]:
    """MIME type kontrolü"""
    try:
        mime = magic.Magic(mime=True)
        file_mime = mime.from_file(file_path)
        if file_mime not in ALLOWED_MIME_TYPES:
            return False, f"Desteklenmeyen dosya türü. İzin verilen türler: {', '.join(ALLOWED_MIME_TYPES)}"
        return True, "OK"
    except Exception as e:
        return False, f"MIME type kontrolü hatası: {str(e)}"

def validate_video(file_path: str) -> tuple[bool, str]:
    """Video dosyasını kontrol et"""
    try:
        # MIME type kontrolü
        is_valid_mime, mime_message = validate_video_mime(file_path)
        if not is_valid_mime:
            return False, mime_message

        # Dosya uzantısı kontrolü
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Desteklenmeyen dosya formatı. İzin verilen formatlar: {', '.join(ALLOWED_EXTENSIONS)}"

        # Dosya boyutu kontrolü
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            return False, f"Dosya boyutu çok büyük. Maksimum boyut: {MAX_FILE_SIZE // (1024*1024)}MB"

        # Video süresi kontrolü
        with VideoFileClip(file_path) as video:
            if video.duration > MAX_DURATION:
                return False, f"Video süresi çok uzun. Maksimum süre: {MAX_DURATION // 60} dakika"

        return True, "OK"
    except Exception as e:
        return False, f"Video doğrulama hatası: {str(e)}"

# IP bazlı istek sayacı
request_counts = {}
RATE_LIMIT_DURATION = 3600  # 1 saat
MAX_REQUESTS_PER_HOUR = 10  # Saat başına maksimum istek

def check_rate_limit(ip: str) -> bool:
    """IP bazlı rate limiting kontrolü"""
    current_time = time.time()
    
    # Eski kayıtları temizle
    request_counts.clear()
    
    if ip not in request_counts:
        request_counts[ip] = {"count": 0, "first_request": current_time}
    
    # Süre kontrolü
    if current_time - request_counts[ip]["first_request"] > RATE_LIMIT_DURATION:
        request_counts[ip] = {"count": 0, "first_request": current_time}
    
    # İstek sayısı kontrolü
    if request_counts[ip]["count"] >= MAX_REQUESTS_PER_HOUR:
        return False
    
    request_counts[ip]["count"] += 1
    return True

def calculate_file_hash(file_path: str) -> str:
    """Dosya hash'ini hesapla"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_video_file(file: UploadFile):
    # Dosya uzantısı kontrolü
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı")
    
    # MIME type kontrolü
    content = file.file.read(2048)
    file.file.seek(0)
    mime = magic.from_buffer(content, mime=True)
    if not mime.startswith('video/'):
        raise HTTPException(status_code=400, detail="Geçersiz dosya türü")
    
    # Boyut kontrolü
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dosya boyutu çok büyük (max 100MB)")

# JWT ayarları
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Session cookie
cookie_sec = APIKeyCookie(name="session")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_session(session: str = Depends(cookie_sec)):
    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Geçersiz oturum")

# CSRF token oluşturma
def generate_csrf_token():
    return secrets.token_urlsafe(32)

@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        csrf_token = request.headers.get("X-CSRF-Token")
        session_csrf = request.cookies.get("csrf_token")
        
        if not csrf_token or not session_csrf or csrf_token != session_csrf:
            raise HTTPException(status_code=403, detail="CSRF token geçersiz")
    
    response = await call_next(request)
    return response

@app.post("/login")
async def login(response: Response):
    # Örnek login - gerçek uygulamada kullanıcı doğrulama eklenecek
    access_token = create_access_token(data={"sub": "user"})
    csrf_token = generate_csrf_token()
    
    response.set_cookie(
        key="session",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=1800
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="strict",
        max_age=1800
    )
    return {"csrf_token": csrf_token}

@app.post("/upload-video/")
@limiter.limit("10/hour")
async def upload_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    data: VideoUploadRequest = Depends(),
    current_user: User = Depends(get_current_active_user)
):
    """Video yükle ve işlemeye başla"""
    try:
        app_logger.info(f"Video yükleme isteği alındı: {file.filename}")
        
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_video:
            content = await file.read()
            temp_video.write(content)
            temp_video_path = temp_video.name

        try:
            # Video doğrulama
            validation_result = await VideoValidator.validate_video(temp_video_path, file.filename)
            if not validation_result.is_valid:
                raise ValidationError(validation_result.message)

            # Güvenli yükleme yolu oluştur
            upload_path, safe_filename = await VideoValidator.create_safe_upload_path(
                settings.UPLOAD_DIR,
                file.filename
            )

            # Dosyayı güvenli konuma taşı
            os.rename(temp_video_path, upload_path)

            # Ses normalizasyonu
            if data.normalize_sound:
                app_logger.info("Ses normalizasyonu başlatılıyor...")
                if validation_result.file_info.get('has_audio'):
                    upload_path = normalize_audio(upload_path, data.target_db)
                    app_logger.info("Ses normalizasyonu tamamlandı")
                else:
                    app_logger.warning("Videoda ses bulunamadı")

            # Dosya hash'ini al
            file_hash = validation_result.file_info['hash']
            
            # Redis'ten önbelleklenmiş sonuçları kontrol et
            redis_client = await get_redis()
            cached_result = await redis_client.get(f"video:{file_hash}")
            
            if cached_result:
                os.unlink(upload_path)
                app_logger.info("Önbellekten sonuçlar alındı")
                return JSONResponse(content={"subtitles": json.loads(cached_result)})
            
            # Celery görevi başlat
            task = process_video.delay(
                upload_path,
                user_id=current_user.username,
                metadata=validation_result.file_info
            )
            app_logger.info(f"Video işleme görevi başlatıldı: {task.id}")
            
            return JSONResponse(content={
                "task_id": task.id,
                "status": "processing",
                "metadata": validation_result.file_info
            })

        except Exception as e:
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
            raise e

    except ValidationError as ve:
        app_logger.error(f"Doğrulama hatası: {str(ve)}")
        raise HTTPException(status_code=ve.status_code, detail=format_error_response(ve))
    except Exception as e:
        app_logger.error(f"Beklenmeyen hata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Görev durumunu kontrol et"""
    try:
        app_logger.info(f"Görev durumu kontrolü: {task_id}")
        task = process_video.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'progress': 0,
            }
        elif task.state == 'SUCCESS':
            redis_client = await get_redis()
            await redis_client.setex(
                f"video:{task_id}",
                3600 * 24,
                json.dumps(task.result)
            )
            
            response = {
                'state': task.state,
                'progress': 100,
                'result': task.result
            }
            app_logger.info(f"Görev başarıyla tamamlandı: {task_id}")
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'error': str(task.info),
            }
            app_logger.error(f"Görev başarısız: {task_id}, Hata: {str(task.info)}")
        else:
            response = {
                'state': task.state,
                'progress': task.info.get('progress', 0),
            }
        
        return response
        
    except Exception as e:
        app_logger.error(f"Görev durumu kontrol hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/adjust-timing/{task_id}")
async def adjust_subtitle_timing(
    task_id: str,
    offset: float = Query(..., description="Zaman düzeltme değeri (saniye)"),
    current_user: User = Depends(get_current_active_user)
):
    """Alt yazı zamanlamasını ayarla"""
    try:
        app_logger.info(f"Alt yazı zamanlama ayarı: {task_id}, Offset: {offset}")
        redis_client = await get_redis()
        subtitles_json = await redis_client.get(f"video:{task_id}")
        
        if not subtitles_json:
            raise SubtitleError("Alt yazılar bulunamadı")
            
        subtitles = json.loads(subtitles_json)
        adjusted_subtitles = adjust_timing(subtitles, offset)
        
        # Güncellenmiş alt yazıları önbelleğe al
        await redis_client.setex(
            f"video:{task_id}",
            3600 * 24,
            json.dumps(adjusted_subtitles)
        )
        
        return {"subtitles": adjusted_subtitles}
        
    except SubtitleError as se:
        app_logger.error(f"Alt yazı hatası: {str(se)}")
        raise HTTPException(status_code=se.status_code, detail=format_error_response(se))
    except Exception as e:
        app_logger.error(f"Alt yazı zamanlama ayarı hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export-subtitles/{task_id}")
async def export_subtitles(
    task_id: str,
    format: str = Query(..., description="Alt yazı formatı (srt veya vtt)"),
    color: str = Query("white", description="Alt yazı rengi"),
    current_user: User = Depends(get_current_active_user)
):
    """Alt yazıları dışa aktar"""
    try:
        app_logger.info(f"Alt yazı dışa aktarma: {task_id}, Format: {format}")
        redis_client = await get_redis()
        subtitles_json = await redis_client.get(f"video:{task_id}")
        
        if not subtitles_json:
            raise SubtitleError("Alt yazılar bulunamadı")
            
        subtitles = json.loads(subtitles_json)
        
        # Alt yazılara renk ekle
        for sub in subtitles:
            sub["color"] = color
        
        # Formatı kontrol et ve dönüştür
        if format.lower() == "srt":
            content = create_srt(subtitles)
            filename = f"subtitles_{task_id}.srt"
        elif format.lower() == "vtt":
            content = create_vtt(subtitles)
            filename = f"subtitles_{task_id}.vtt"
        else:
            raise ValidationError("Geçersiz alt yazı formatı")
        
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=f".{format}") as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        return FileResponse(
            temp_path,
            filename=filename,
            media_type="text/plain",
            background=BackgroundTasks(lambda: os.unlink(temp_path))
        )
        
    except (SubtitleError, ValidationError) as e:
        app_logger.error(f"Alt yazı dışa aktarma hatası: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=format_error_response(e))
    except Exception as e:
        app_logger.error(f"Beklenmeyen hata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında Redis bağlantısını oluştur"""
    await get_redis()
    app_logger.info("Uygulama başlatıldı")

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapanırken Redis bağlantısını kapat"""
    if redis is not None:
        await redis.close()
    app_logger.info("Uygulama kapatıldı")

# Logger'ı başlat
logger = setup_logging()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# Auth endpoint'leri
@app.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    csrf_token = generate_csrf_token()
    
    # Secure cookie'leri ayarla
    response.set_cookie(
        key="session",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token
    }

@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    response.delete_cookie("csrf_token")
    return {"message": "Çıkış yapıldı"}

@app.get("/check-auth", response_model=User)
async def check_auth(current_user: User = Depends(get_current_active_user)):
    return current_user

# Exception handler'ları ekle
app.add_exception_handler(BaseAPIException, api_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

@app.get("/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    try:
        # Redis bağlantısını kontrol et
        redis_client = await get_redis()
        await redis_client.ping()
        
        # Celery worker'ı kontrol et
        i = process_video.app.control.inspect()
        workers = i.active()
        
        if not workers:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Celery worker aktif değil"}
            )
        
        # Disk alanını kontrol et
        disk = os.statvfs("/tmp")
        free_space = disk.f_bavail * disk.f_frsize
        
        if free_space < 100 * 1024 * 1024:  # 100MB'dan az boş alan
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Yetersiz disk alanı"}
            )
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "free_space_mb": free_space // (1024 * 1024)
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 