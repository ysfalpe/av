import os
import tempfile
from celery import Celery
from moviepy.video.io.VideoFileClip import VideoFileClip
from vosk import Model, KaldiRecognizer
import json
import wave
from memory_profiler import profile
from logger import task_logger
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np

# Celery uygulaması oluştur
celery_app = Celery('tasks')

# Celery yapılandırması
celery_app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Istanbul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 saat
    worker_max_memory_per_child=200000,  # 200MB
    worker_prefetch_multiplier=1,  # Her worker'a bir görev
    worker_concurrency=2,  # Aynı anda çalışacak worker sayısı
    task_routes={
        'tasks.process_video': {'queue': 'video_processing'}
    },
    task_annotations={
        'tasks.process_video': {'rate_limit': '10/h'}
    }
)

# Vosk modelini yükle
if not os.path.exists("model"):
    os.makedirs("model", exist_ok=True)
    
try:
    model = Model("model")
    task_logger.info("Vosk modeli başarıyla yüklendi")
except Exception as e:
    task_logger.error(f"Model yüklenirken hata oluştu: {str(e)}")
    model = None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def process_audio_chunk(audio_data: bytes, recognizer: KaldiRecognizer) -> list:
    """Ses verisini işle - Yeniden deneme mekanizması ile"""
    if recognizer.AcceptWaveform(audio_data):
        result = json.loads(recognizer.Result())
        return result.get("result", [])
    return []

@profile
def process_video_chunk(chunk_path: str, chunk_size: int = 10 * 1024 * 1024):
    """Video parçasını işle - Memory kullanımını optimize et"""
    if model is None:
        task_logger.error("Vosk modeli yüklenemedi")
        raise RuntimeError("Vosk modeli yüklenemedi")
        
    results = []
    
    try:
        with VideoFileClip(chunk_path) as video:
            task_logger.info(f"Video yüklendi: {chunk_path}")
            
            # Ses dosyasını geçici olarak kaydet
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                video.audio.write_audiofile(temp_audio.name, logger=None)
                audio_path = temp_audio.name
                task_logger.info("Ses dosyası oluşturuldu")

            # Sesi parçalar halinde işle
            wf = wave.open(audio_path, "rb")
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)

            total_frames = wf.getnframes()
            processed_frames = 0
            
            while True:
                data = wf.readframes(chunk_size)
                if len(data) == 0:
                    break
                    
                try:
                    chunk_results = process_audio_chunk(data, rec)
                    results.extend(chunk_results)
                    
                    # İlerleme durumunu güncelle
                    processed_frames += chunk_size
                    progress = min(100, int((processed_frames / total_frames) * 100))
                    task_logger.info(f"İşleme durumu: %{progress}")
                    
                except Exception as e:
                    task_logger.error(f"Ses parçası işlenirken hata: {str(e)}")
                    raise e

            # Son sonuçları da al
            final_result = json.loads(rec.FinalResult())
            if final_result.get("result"):
                results.extend(final_result["result"])

            # Geçici dosyayı temizle
            os.unlink(audio_path)
            task_logger.info("Ses dosyası temizlendi")
            
    except Exception as e:
        task_logger.error(f"Video işleme hatası: {str(e)}")
        raise e

    return results

@celery_app.task(bind=True)
def process_video(self, video_path: str):
    """Video işleme görevi"""
    try:
        task_logger.info(f"Video işleme başladı: {video_path}")
        self.update_state(state='PROGRESS', meta={'progress': 0})
        
        # Video işleme
        results = process_video_chunk(video_path)
        task_logger.info("Video işleme tamamlandı")
        
        # Geçici dosyayı temizle
        if os.path.exists(video_path):
            os.unlink(video_path)
            task_logger.info("Geçici video dosyası temizlendi")
        
        # Sonuçları formatlama
        formatted_subtitles = []
        for r in results:
            formatted_subtitles.append({
                "start": r["start"],
                "end": r["end"],
                "text": r["word"],
                "confidence": r.get("conf", 1.0)
            })
        
        self.update_state(state='SUCCESS', meta={'progress': 100})
        task_logger.info("Alt yazı oluşturma tamamlandı")
        
        return formatted_subtitles
        
    except Exception as e:
        # Hata durumunda temizlik
        if os.path.exists(video_path):
            os.unlink(video_path)
        task_logger.error(f"Video işleme hatası: {str(e)}")
        raise e 