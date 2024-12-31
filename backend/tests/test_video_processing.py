import pytest
from unittest.mock import Mock, patch
import os
import tempfile
import json
from fastapi.testclient import TestClient
from ..main import app
from ..tasks import process_video
from ..subtitle_utils import create_srt, create_vtt, adjust_timing, merge_nearby_subtitles
from ..video_utils import VideoOptimizer

client = TestClient(app)

@pytest.fixture
def sample_video():
    """Test için örnek video dosyası oluştur"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        # Örnek video içeriği yaz
        f.write(b'fake video content')
        return f.name

@pytest.fixture
def sample_subtitles():
    """Test için örnek altyazılar"""
    return [
        {"start": 0, "end": 2000, "text": "Merhaba"},
        {"start": 2500, "end": 4000, "text": "Dünya"}
    ]

def test_create_srt(sample_subtitles):
    """SRT formatı oluşturma testi"""
    srt_content = create_srt(sample_subtitles)
    assert "00:00:00,000" in srt_content
    assert "Merhaba" in srt_content
    assert "Dünya" in srt_content

def test_create_vtt(sample_subtitles):
    """VTT formatı oluşturma testi"""
    vtt_content = create_vtt(sample_subtitles)
    assert "WEBVTT" in vtt_content
    assert "00:00:00.000" in vtt_content
    assert "Merhaba" in vtt_content

def test_adjust_timing(sample_subtitles):
    """Zamanlama ayarlama testi"""
    offset = 1000  # 1 saniye
    adjusted = adjust_timing(sample_subtitles, offset)
    assert adjusted[0]["start"] == 1000
    assert adjusted[0]["end"] == 3000

def test_merge_nearby_subtitles(sample_subtitles):
    """Yakın altyazıları birleştirme testi"""
    merged = merge_nearby_subtitles(sample_subtitles, threshold=1.0)
    assert len(merged) == 1
    assert merged[0]["text"] == "Merhaba Dünya"

@pytest.mark.asyncio
async def test_video_upload(sample_video):
    """Video yükleme endpoint testi"""
    with open(sample_video, 'rb') as f:
        response = client.post(
            "/upload-video/",
            files={"file": ("test.mp4", f, "video/mp4")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "video_id" in data

@patch('tasks.process_video.delay')
def test_video_processing(mock_process):
    """Video işleme task testi"""
    # Mock Celery task
    mock_process.return_value.id = "test_task_id"
    
    result = process_video("test_video.mp4")
    assert result is not None

def test_video_optimizer(sample_video):
    """Video optimizasyon testi"""
    optimizer = VideoOptimizer(target_size_mb=1)
    output_path = optimizer.optimize_video(sample_video)
    
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) <= 1024 * 1024  # 1MB

@pytest.mark.asyncio
async def test_subtitle_download():
    """Altyazı indirme endpoint testi"""
    video_id = "test_video_id"
    
    # Mock subtitle data
    with patch('redis.Redis.get') as mock_get:
        mock_get.return_value = json.dumps(sample_subtitles)
        
        response = client.get(f"/subtitles/{video_id}/srt")
        assert response.status_code == 200
        assert "Merhaba" in response.text

def test_invalid_video_format():
    """Geçersiz video formatı testi"""
    with tempfile.NamedTemporaryFile(suffix='.txt') as f:
        f.write(b'not a video')
        f.seek(0)
        
        response = client.post(
            "/upload-video/",
            files={"file": ("test.txt", f, "text/plain")}
        )
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_video_status():
    """Video işleme durumu endpoint testi"""
    video_id = "test_video_id"
    
    # Mock status data
    with patch('redis.Redis.get') as mock_get:
        mock_get.return_value = json.dumps({
            "status": "processing",
            "progress": 50
        })
        
        response = client.get(f"/status/{video_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"] == 50

def test_cleanup():
    """Test dosyalarını temizle"""
    # Geçici dosyaları temizle
    for file in os.listdir(tempfile.gettempdir()):
        if file.endswith('.mp4'):
            os.remove(os.path.join(tempfile.gettempdir(), file)) 