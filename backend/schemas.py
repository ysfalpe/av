from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import magic
import os

class VideoUploadRequest(BaseModel):
    normalize_sound: bool = Field(False, description="Ses seviyesini normalize et")
    target_db: float = Field(-20.0, ge=-30.0, le=-10.0, description="Hedef ses seviyesi (dB)")

    class Config:
        json_schema_extra = {
            "example": {
                "normalize_sound": True,
                "target_db": -20.0
            }
        }

class SubtitleAdjustRequest(BaseModel):
    offset: float = Field(..., ge=-3600, le=3600, description="Zaman düzeltme değeri (saniye)")

    class Config:
        json_schema_extra = {
            "example": {
                "offset": 2.5
            }
        }

class SubtitleExportRequest(BaseModel):
    format: str = Field(..., regex="^(srt|vtt)$", description="Alt yazı formatı")
    color: str = Field("white", regex="^(white|yellow|green|cyan|red)$", description="Alt yazı rengi")

    class Config:
        json_schema_extra = {
            "example": {
                "format": "srt",
                "color": "white"
            }
        }

class Subtitle(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    text: str = Field(..., min_length=1, max_length=1000)
    color: Optional[str] = Field("white", regex="^(white|yellow|green|cyan|red)$")

    @validator('end')
    def end_must_be_after_start(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('Bitiş zamanı başlangıç zamanından sonra olmalıdır')
        return v

class VideoValidationResult(BaseModel):
    is_valid: bool
    message: str
    file_info: Optional[dict] = None

class VideoMetadata(BaseModel):
    filename: str
    size: int
    mime_type: str
    duration: Optional[float]
    width: Optional[int]
    height: Optional[int]
    has_audio: bool
    format: str

    @validator('size')
    def validate_size(cls, v):
        max_size = 100 * 1024 * 1024  # 100MB
        if v > max_size:
            raise ValueError(f'Dosya boyutu çok büyük (max: {max_size // (1024*1024)}MB)')
        return v

    @validator('mime_type')
    def validate_mime_type(cls, v):
        allowed_types = {'video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/webm'}
        if v not in allowed_types:
            raise ValueError(f'Desteklenmeyen dosya türü. İzin verilenler: {", ".join(allowed_types)}')
        return v

    @validator('duration')
    def validate_duration(cls, v):
        if v and v > 600:  # 10 dakika
            raise ValueError('Video süresi çok uzun (max: 10 dakika)')
        return v

class ProcessingTask(BaseModel):
    task_id: str
    status: str
    progress: float = Field(0, ge=0, le=100)
    result: Optional[List[Subtitle]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "processing",
                "progress": 45.5,
                "created_at": "2024-01-01T12:00:00",
                "updated_at": "2024-01-01T12:01:00"
            }
        } 