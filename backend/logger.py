import logging
import logging.handlers
import os
from datetime import datetime

class CustomLogger:
    def __init__(self, name: str, log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Log dizini oluştur
        os.makedirs(log_dir, exist_ok=True)
        
        # Dosya handler'ı (günlük rotasyon)
        log_file = os.path.join(log_dir, f"{name}.log")
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Handler'ları ekle
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def critical(self, message: str):
        self.logger.critical(message)

class RequestLogger:
    def __init__(self, logger: CustomLogger):
        self.logger = logger
    
    def log_request(self, request, response=None, error=None):
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host,
            "headers": dict(request.headers)
        }
        
        if response:
            log_data["status_code"] = response.status_code
            log_data["response_time"] = getattr(response, "response_time", None)
        
        if error:
            log_data["error"] = str(error)
            self.logger.error(f"Request failed: {log_data}")
        else:
            self.logger.info(f"Request completed: {log_data}")

# Logger örnekleri oluştur
app_logger = CustomLogger("app")
request_logger = RequestLogger(CustomLogger("requests"))
task_logger = CustomLogger("tasks") 