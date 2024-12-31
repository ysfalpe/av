import logging
import logging.handlers
import json
import os
from datetime import datetime
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id

def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_dir = 'logs'
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Ana logger yapılandırması
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # JSON formatı
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(module)s %(function)s %(line)d %(message)s'
    )
    
    # Dosya handler'ı
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Hata logları için ayrı handler
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Üçüncü parti kütüphanelerin log seviyelerini ayarla
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.ERROR)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    
    return logger 