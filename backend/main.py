from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks, Query
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
import aioredis
from tasks import process_video
from subtitle_utils import create_srt, create_vtt, adjust_timing, merge_nearby_subtitles
from audio_utils import normalize_audio, get_audio_stats
from logger import app_logger, request_logger
from exceptions import (
    ValidationError, FileProcessingError, AudioProcessingError,
    SubtitleError, RateLimitError, NetworkError, format_error_response
)

# Redis bağlantısı
redis = None

async def get_redis():
    global redis
    if redis is None:
        redis = await aioredis.from_url('redis://localhost:6379', encoding='utf-8', decode_responses=True)
    return redis

# Rate limiter oluştur
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS ayarları
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://your-production-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600
)

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

@app.post("/upload-video/")
@limiter.limit("10/hour")
async def upload_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    normalize_sound: bool = Query(False, description="Ses seviyesini normalize et"),
    target_db: float = Query(-20.0, description="Hedef ses seviyesi (dB)")
):
    try:
        app_logger.info(f"Video yükleme isteği alındı: {file.filename}")
        client_ip = request.client.host
        
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_video:
            content = await file.read()
            temp_video.write(content)
            temp_video_path = temp_video.name

        try:
            # Video doğrulama
            is_valid, message = validate_video(temp_video_path)
            if not is_valid:
                raise ValidationError(message)

            # Ses normalizasyonu
            if normalize_sound:
                app_logger.info("Ses normalizasyonu başlatılıyor...")
                audio_stats = get_audio_stats(temp_video_path)
                if audio_stats["has_audio"]:
                    temp_video_path = normalize_audio(temp_video_path, target_db)
                    app_logger.info("Ses normalizasyonu tamamlandı")
                else:
                    app_logger.warning("Videoda ses bulunamadı")

            # Dosya hash'ini hesapla
            file_hash = calculate_file_hash(temp_video_path)
            
            # Redis'ten önbelleklenmiş sonuçları kontrol et
            redis_client = await get_redis()
            cached_result = await redis_client.get(f"video:{file_hash}")
            
            if cached_result:
                os.unlink(temp_video_path)
                app_logger.info("Önbellekten sonuçlar alındı")
                return JSONResponse(content={"subtitles": json.loads(cached_result)})
            
            # Celery görevi başlat
            task = process_video.delay(temp_video_path)
            app_logger.info(f"Video işleme görevi başlatıldı: {task.id}")
            
            return JSONResponse(content={
                "task_id": task.id,
                "status": "processing"
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
async def get_task_status(task_id: str):
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
    offset: float = Query(..., description="Zaman düzeltme değeri (saniye)")
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
    color: str = Query("white", description="Alt yazı rengi")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 