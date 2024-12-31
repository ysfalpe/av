import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from .exceptions import (
    BaseAPIException, ValidationError, FileProcessingError,
    AudioProcessingError, SubtitleError, RateLimitError, NetworkError
)
from .logger import app_logger

async def api_exception_handler(request: Request, exc: BaseAPIException):
    app_logger.error(f"API Hatası: {exc.detail} - Endpoint: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )

async def validation_exception_handler(request: Request, exc: ValidationError):
    app_logger.warning(f"Doğrulama Hatası: {exc.detail} - Endpoint: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": exc.detail,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY
        }
    )

async def file_processing_exception_handler(request: Request, exc: FileProcessingError):
    app_logger.error(f"Dosya İşleme Hatası: {exc.detail} - Endpoint: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "FILE_PROCESSING_ERROR",
            "message": exc.detail,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    app_logger.critical(f"Beklenmeyen Hata: {str(exc)} - Endpoint: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    ) 