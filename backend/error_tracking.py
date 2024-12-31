import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from config import settings
import logging

logger = logging.getLogger(__name__)

def init_sentry():
    """Sentry'yi başlat ve konfigüre et"""
    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.2,
            profiles_sample_rate=0.2,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration()
            ],
            before_send=before_send,
            before_breadcrumb=before_breadcrumb
        )
        logger.info("Sentry initialized successfully")
    except Exception as e:
        logger.error(f"Sentry initialization failed: {str(e)}")

def before_send(event, hint):
    """Event gönderilmeden önce filtrele ve düzenle"""
    
    # Hassas bilgileri temizle
    if 'request' in event and 'headers' in event['request']:
        headers = event['request']['headers']
        if 'Authorization' in headers:
            headers['Authorization'] = '[FILTERED]'
        if 'Cookie' in headers:
            headers['Cookie'] = '[FILTERED]'
    
    # Hata mesajlarını düzenle
    if 'exception' in event:
        exc_info = hint.get('exc_info')
        if exc_info:
            event['exception']['values'][0]['value'] = sanitize_error_message(
                str(exc_info[1])
            )
    
    # Error level'ı kontrol et
    if event.get('level') == 'error':
        # Kritik hataları slack'e bildir
        notify_slack(event)
    
    return event

def before_breadcrumb(breadcrumb, hint):
    """Breadcrumb'ları filtrele ve düzenle"""
    
    # SQL sorgularını temizle
    if breadcrumb.get('category') == 'query':
        breadcrumb['data']['query'] = sanitize_sql_query(
            breadcrumb['data']['query']
        )
    
    # HTTP isteklerini temizle
    if breadcrumb.get('category') == 'http':
        if 'Authorization' in breadcrumb.get('data', {}):
            breadcrumb['data']['Authorization'] = '[FILTERED]'
    
    return breadcrumb

def sanitize_error_message(message: str) -> str:
    """Hata mesajlarından hassas bilgileri temizle"""
    # Örnek: API key'leri gizle
    import re
    message = re.sub(
        r'api[_-]?key[=:]\s*["\']?\w+["\']?',
        'api_key=[FILTERED]',
        message,
        flags=re.IGNORECASE
    )
    return message

def sanitize_sql_query(query: str) -> str:
    """SQL sorgularından hassas bilgileri temizle"""
    # Örnek: Parola alanlarını gizle
    import re
    query = re.sub(
        r'password\s*=\s*["\']?\w+["\']?',
        'password=[FILTERED]',
        query,
        flags=re.IGNORECASE
    )
    return query

def notify_slack(event):
    """Kritik hataları Slack'e bildir"""
    if settings.SLACK_WEBHOOK_URL:
        try:
            import requests
            message = {
                'text': f"🚨 Error in {settings.ENVIRONMENT}: {event['exception']['values'][0]['value']}"
            }
            requests.post(settings.SLACK_WEBHOOK_URL, json=message)
        except Exception as e:
            logger.error(f"Slack notification failed: {str(e)}")

# Sentry'yi başlat
if settings.SENTRY_DSN:
    init_sentry() 