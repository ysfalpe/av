from moviepy.editor import VideoFileClip
import os
import tempfile
from PIL import Image
import io

class VideoOptimizer:
    def __init__(self, target_size_mb=50):
        self.target_size_mb = target_size_mb
        self.target_size_bytes = target_size_mb * 1024 * 1024
    
    def optimize_video(self, input_path: str, output_path: str = None) -> str:
        """Video dosyasını optimize et"""
        if output_path is None:
            output_path = self._get_optimized_path(input_path)
        
        # Video boyutunu kontrol et
        if os.path.getsize(input_path) <= self.target_size_bytes:
            return input_path
        
        video = VideoFileClip(input_path)
        
        # Video özelliklerini al
        duration = video.duration
        original_size = os.path.getsize(input_path)
        
        # Hedef bitrate hesapla
        target_bitrate = self._calculate_target_bitrate(
            original_size,
            duration,
            self.target_size_bytes
        )
        
        # Video çözünürlüğünü ayarla
        width, height = self._calculate_dimensions(video.size)
        
        # Optimize edilmiş videoyu kaydet
        video.resize((width, height)).write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            bitrate=f"{target_bitrate}k",
            preset='medium',
            threads=2
        )
        
        video.close()
        return output_path
    
    def create_thumbnail(self, video_path: str, time_s: float = 0) -> bytes:
        """Video için thumbnail oluştur"""
        with VideoFileClip(video_path) as video:
            # Video ortasından frame al
            if time_s == 0:
                time_s = video.duration / 2
            
            frame = video.get_frame(time_s)
            
            # PIL Image'e dönüştür
            image = Image.fromarray(frame)
            
            # Thumbnail boyutunu ayarla
            image.thumbnail((320, 180))
            
            # Bytes olarak kaydet
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=85)
            return img_byte_arr.getvalue()
    
    def _calculate_target_bitrate(self, original_size: int, duration: float, target_size: int) -> int:
        """Hedef bitrate hesapla"""
        # Bitrate = (target size in bits) / (duration in seconds)
        return int((target_size * 8) / duration / 1024)  # kbps
    
    def _calculate_dimensions(self, original_dimensions: tuple) -> tuple:
        """Video boyutlarını hesapla"""
        width, height = original_dimensions
        
        # 1080p'den büyükse küçült
        max_dimension = 1080
        if height > max_dimension:
            ratio = max_dimension / height
            width = int(width * ratio)
            height = max_dimension
        
        # Çift sayılara yuvarla
        width = (width // 2) * 2
        height = (height // 2) * 2
        
        return width, height
    
    def _get_optimized_path(self, input_path: str) -> str:
        """Optimize edilmiş dosya için path oluştur"""
        directory = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        return os.path.join(directory, f"{name}_optimized{ext}")

# Singleton instance
video_optimizer = VideoOptimizer() 