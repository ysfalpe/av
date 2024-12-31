import os
import magic
from moviepy.editor import VideoFileClip
from typing import Tuple, Dict, Optional
from ..schemas import VideoValidationResult, VideoMetadata
import hashlib
import asyncio
import aiofiles
import mimetypes
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class VideoValidator:
    ALLOWED_MIME_TYPES = {
        'video/mp4',
        'video/x-msvideo',
        'video/quicktime',
        'video/webm'
    }
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_DURATION = 600  # 10 dakika
    CHUNK_SIZE = 8192  # 8KB chunks for streaming

    @staticmethod
    async def get_file_hash(file_path: str) -> str:
        """Dosyanın SHA-256 hash'ini hesapla"""
        sha256_hash = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(VideoValidator.CHUNK_SIZE):
                sha256_hash.update(chunk)
                
        return sha256_hash.hexdigest()

    @staticmethod
    async def get_mime_type(file_path: str) -> str:
        """Dosyanın MIME type'ını belirle"""
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)

    @staticmethod
    async def get_video_metadata(file_path: str) -> Optional[Dict]:
        """Video metadata'sını çıkar"""
        try:
            with VideoFileClip(file_path) as video:
                return {
                    'duration': video.duration,
                    'width': int(video.size[0]),
                    'height': int(video.size[1]),
                    'has_audio': video.audio is not None,
                    'fps': video.fps
                }
        except Exception as e:
            logger.error(f"Video metadata çıkarma hatası: {str(e)}")
            return None

    @staticmethod
    def is_valid_extension(filename: str) -> bool:
        """Dosya uzantısının geçerli olup olmadığını kontrol et"""
        ext = Path(filename).suffix.lower()
        return mimetypes.guess_type(filename)[0] in VideoValidator.ALLOWED_MIME_TYPES

    @classmethod
    async def validate_video(cls, file_path: str, filename: str) -> VideoValidationResult:
        """Video dosyasını doğrula"""
        try:
            # Dosya boyutu kontrolü
            file_size = os.path.getsize(file_path)
            if file_size > cls.MAX_FILE_SIZE:
                return VideoValidationResult(
                    is_valid=False,
                    message=f"Dosya boyutu çok büyük (max: {cls.MAX_FILE_SIZE // (1024*1024)}MB)",
                    file_info={'size': file_size}
                )

            # Dosya uzantısı kontrolü
            if not cls.is_valid_extension(filename):
                return VideoValidationResult(
                    is_valid=False,
                    message="Geçersiz dosya uzantısı",
                    file_info={'filename': filename}
                )

            # MIME type kontrolü
            mime_type = await cls.get_mime_type(file_path)
            if mime_type not in cls.ALLOWED_MIME_TYPES:
                return VideoValidationResult(
                    is_valid=False,
                    message=f"Desteklenmeyen dosya türü: {mime_type}",
                    file_info={'mime_type': mime_type}
                )

            # Video metadata kontrolü
            metadata = await cls.get_video_metadata(file_path)
            if not metadata:
                return VideoValidationResult(
                    is_valid=False,
                    message="Video metadata'sı okunamadı",
                    file_info=None
                )

            if metadata['duration'] > cls.MAX_DURATION:
                return VideoValidationResult(
                    is_valid=False,
                    message=f"Video süresi çok uzun (max: {cls.MAX_DURATION // 60} dakika)",
                    file_info={'duration': metadata['duration']}
                )

            # Dosya hash'i
            file_hash = await cls.get_file_hash(file_path)

            # Tüm kontroller başarılı
            return VideoValidationResult(
                is_valid=True,
                message="Video doğrulama başarılı",
                file_info={
                    'filename': filename,
                    'size': file_size,
                    'mime_type': mime_type,
                    'hash': file_hash,
                    **metadata
                }
            )

        except Exception as e:
            logger.error(f"Video doğrulama hatası: {str(e)}")
            return VideoValidationResult(
                is_valid=False,
                message=f"Doğrulama hatası: {str(e)}",
                file_info=None
            )

    @staticmethod
    async def sanitize_filename(filename: str) -> str:
        """Dosya adını güvenli hale getir"""
        # Sadece alfanumerik karakterler, tire ve alt çizgi kullan
        base_name = ''.join(c if c.isalnum() or c in '-_' else '_' 
                          for c in Path(filename).stem)
        extension = Path(filename).suffix.lower()
        
        # Maksimum uzunluk kontrolü
        if len(base_name) > 100:
            base_name = base_name[:100]
            
        return f"{base_name}{extension}"

    @staticmethod
    async def create_safe_upload_path(upload_dir: str, filename: str) -> Tuple[str, str]:
        """Güvenli yükleme yolu oluştur"""
        safe_filename = await VideoValidator.sanitize_filename(filename)
        
        # Dizin yoksa oluştur
        os.makedirs(upload_dir, exist_ok=True)
        
        # Benzersiz dosya adı oluştur
        timestamp = int(asyncio.get_event_loop().time() * 1000)
        unique_filename = f"{timestamp}_{safe_filename}"
        
        upload_path = os.path.join(upload_dir, unique_filename)
        return upload_path, unique_filename 