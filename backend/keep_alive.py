import os
import time
import requests
import logging
from datetime import datetime

logger = logging.getLogger("keep_alive")

def keep_alive():
    """Glitch projesini canlı tut"""
    project_url = f"https://{os.getenv('PROJECT_DOMAIN')}.glitch.me"
    
    while True:
        try:
            # Her 4 dakikada bir ping at
            response = requests.get(f"{project_url}/health")
            status = response.status_code
            
            logger.info(f"Keep-alive ping: {status} - {datetime.now().isoformat()}")
            
            # 4 dakika bekle
            time.sleep(240)
            
        except Exception as e:
            logger.error(f"Keep-alive hatası: {e}")
            time.sleep(60)  # Hata durumunda 1 dakika bekle

if __name__ == "__main__":
    keep_alive() 