import os
import subprocess
import sys
import time
import requests
import zipfile
import urllib.request

def check_redis():
    """Redis servisini kontrol et ve başlat"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        print("✅ Redis bağlantısı başarılı")
    except:
        print("⚠️ Redis başlatılıyor...")
        try:
            subprocess.Popen(['redis-server'])
            time.sleep(2)
            print("✅ Redis başlatıldı")
        except:
            print("❌ Redis başlatılamadı. Lütfen Redis'in kurulu olduğundan emin olun.")
            sys.exit(1)

def check_vosk_model():
    """Vosk modelini kontrol et ve gerekirse indir"""
    model_path = os.path.join('model')
    if not os.path.exists(model_path) or not os.listdir(model_path):
        print("⚠️ Vosk modeli bulunamadı, indiriliyor...")
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip"
        zip_path = "vosk-model-small-tr-0.3.zip"
        
        # Modeli indir
        urllib.request.urlretrieve(model_url, zip_path)
        
        # Zip dosyasını çıkar
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_path)
        
        # Zip dosyasını sil
        os.remove(zip_path)
        print("✅ Vosk modeli başarıyla indirildi")
    else:
        print("✅ Vosk modeli mevcut")

def check_python_magic():
    """Python-magic kurulumunu kontrol et"""
    try:
        import magic
        magic.Magic()
        print("✅ Python-magic kurulumu başarılı")
    except:
        print("⚠️ Python-magic yeniden kuruluyor...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', '-y', 'python-magic', 'python-magic-bin'])
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-magic-bin==0.4.14'])
        print("✅ Python-magic kurulumu tamamlandı")

def start_celery():
    """Celery worker'ı başlat"""
    print("⚠️ Celery worker başlatılıyor...")
    celery_process = subprocess.Popen([
        sys.executable, '-m', 'celery',
        '-A', 'tasks', 'worker',
        '--pool=solo',
        '--loglevel=INFO'
    ])
    time.sleep(2)
    print("✅ Celery worker başlatıldı")
    return celery_process

def start_fastapi():
    """FastAPI uygulamasını başlat"""
    print("⚠️ FastAPI uygulaması başlatılıyor...")
    fastapi_process = subprocess.Popen([
        sys.executable, '-m', 'uvicorn',
        'main:app',
        '--host', '0.0.0.0',
        '--port', '8000'
    ])
    time.sleep(2)
    print("✅ FastAPI uygulaması başlatıldı")
    return fastapi_process

def main():
    print("🚀 Servisler başlatılıyor...")
    
    # Gerekli kontroller ve kurulumlar
    check_redis()
    check_vosk_model()
    check_python_magic()
    
    # Servisleri başlat
    celery_process = start_celery()
    fastapi_process = start_fastapi()
    
    print("\n✨ Tüm servisler başarıyla başlatıldı!")
    print("📝 Backend API: http://localhost:8000")
    
    try:
        # Servisleri çalışır durumda tut
        celery_process.wait()
        fastapi_process.wait()
    except KeyboardInterrupt:
        print("\n⚠️ Servisler kapatılıyor...")
        celery_process.terminate()
        fastapi_process.terminate()
        print("✅ Servisler kapatıldı")

if __name__ == "__main__":
    main() 