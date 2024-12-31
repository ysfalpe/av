#!/bin/bash

# Gerekli dizinleri oluştur
mkdir -p /tmp/uploads
mkdir -p logs

# İşletim sistemini kontrol et
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows - Memurai kullan
    echo "Windows sisteminde Memurai kontrol ediliyor..."
    NET START Memurai || echo "Memurai servisi zaten çalışıyor olabilir"
else
    # Linux/Unix - Redis kullan
    echo "Linux/Unix sisteminde Redis kuruluyor ve başlatılıyor..."
    apt-get update
    apt-get install -y ffmpeg redis-server python3-dev build-essential
    redis-server --daemonize yes
fi

# Python paketlerini yükle
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows için özel paketleri ekle
    pip install --no-cache-dir -r backend/requirements.txt python-magic-bin==0.4.14
else
    # Linux için normal kurulum
    pip install --no-cache-dir -r backend/requirements.txt
fi

# Vosk modelini indir (eğer yoksa)
cd backend
if [ ! -d "model" ]; then
    echo "Vosk modeli indiriliyor..."
    python download_model.py
fi

# Temizleme scriptini başlat
python cleanup.py &

# Keep-alive scriptini başlat
python keep_alive.py &

# Celery worker'ı başlat
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows'ta --pool=solo kullan
    python -m celery -A tasks worker --pool=solo --loglevel=info &
else
    # Linux'ta normal worker kullan
    python -m celery -A tasks worker --loglevel=info &
fi

# FastAPI uygulamasını başlat
if [[ -z "${PORT}" ]]; then
    # Lokal geliştirme için varsayılan port
    PORT=8000
fi
python -m uvicorn main:app --host 0.0.0.0 --port $PORT 