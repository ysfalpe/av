import numpy as np
from moviepy.video.io.VideoFileClip import VideoFileClip
import tempfile
import os

def normalize_audio(video_path: str, target_db: float = -20.0) -> str:
    """Video ses seviyesini normalize et"""
    try:
        with VideoFileClip(video_path) as video:
            # Ses klibini al
            audio = video.audio
            
            if audio is None:
                return video_path  # Ses yoksa orijinal videoyu döndür
            
            # Ses verilerini numpy dizisine dönüştür
            samples = np.array(audio.to_soundarray())
            
            # RMS seviyesini hesapla
            rms = np.sqrt(np.mean(samples**2))
            
            # dB cinsinden mevcut seviye
            current_db = 20 * np.log10(rms)
            
            # Normalizasyon faktörünü hesapla
            gain = 10**((target_db - current_db) / 20)
            
            # Sesi normalize et
            normalized_samples = samples * gain
            
            # Clipping'i önle
            if np.max(np.abs(normalized_samples)) > 1:
                normalized_samples = normalized_samples / np.max(np.abs(normalized_samples))
            
            # Geçici dosya oluştur
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_path)[1]) as temp_video:
                # Yeni video oluştur
                new_video = video.set_audio(audio.set_array(normalized_samples))
                new_video.write_videofile(temp_video.name, codec='libx264', audio_codec='aac')
                new_path = temp_video.name
                
            # Orijinal dosyayı sil
            os.unlink(video_path)
            
            return new_path
            
    except Exception as e:
        print(f"Ses normalizasyonu hatası: {str(e)}")
        return video_path  # Hata durumunda orijinal videoyu döndür

def get_audio_stats(video_path: str) -> dict:
    """Video ses istatistiklerini al"""
    try:
        with VideoFileClip(video_path) as video:
            audio = video.audio
            if audio is None:
                return {"has_audio": False}
                
            samples = np.array(audio.to_soundarray())
            rms = np.sqrt(np.mean(samples**2))
            peak = np.max(np.abs(samples))
            db_level = 20 * np.log10(rms)
            
            return {
                "has_audio": True,
                "rms_level": float(rms),
                "peak_level": float(peak),
                "db_level": float(db_level),
                "duration": audio.duration
            }
            
    except Exception as e:
        print(f"Ses istatistikleri alınamadı: {str(e)}")
        return {"has_audio": False, "error": str(e)} 