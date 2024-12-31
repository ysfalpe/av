import pytest
from fastapi.testclient import TestClient
import redis
import os
import tempfile
import time
from ..main import app
from ..tasks import celery_app
from ..config import settings

client = TestClient(app)
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)

@pytest.fixture(scope="session")
def test_video():
    """Test için örnek video dosyası oluştur"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        f.write(b'fake video content')
        yield f.name
    os.unlink(f.name)

@pytest.fixture(scope="session")
def celery_worker():
    """Test için Celery worker başlat"""
    worker = celery_app.Worker(
        pool='solo',
        concurrency=1,
        loglevel='INFO'
    )
    worker.start()
    yield worker
    worker.stop()

@pytest.mark.integration
def test_full_video_processing_flow(test_video, celery_worker):
    """Tam video işleme akışı testi"""
    
    # 1. Video yükle
    with open(test_video, 'rb') as f:
        response = client.post(
            "/upload-video/",
            files={"file": ("test.mp4", f, "video/mp4")}
        )
    assert response.status_code == 200
    video_id = response.json()["video_id"]
    
    # 2. İşleme durumunu kontrol et
    max_retries = 30
    for _ in range(max_retries):
        response = client.get(f"/status/{video_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        if status == "completed":
            break
        elif status == "failed":
            pytest.fail("Video processing failed")
        
        time.sleep(1)
    else:
        pytest.fail("Video processing timeout")
    
    # 3. Altyazıları kontrol et
    response = client.get(f"/subtitles/{video_id}/srt")
    assert response.status_code == 200
    assert len(response.text) > 0
    
    response = client.get(f"/subtitles/{video_id}/vtt")
    assert response.status_code == 200
    assert "WEBVTT" in response.text

@pytest.mark.integration
def test_redis_integration():
    """Redis entegrasyon testi"""
    
    # Redis bağlantısını kontrol et
    assert redis_client.ping()
    
    # Veri yazma/okuma testi
    test_key = "test:integration"
    test_value = "test_data"
    
    redis_client.set(test_key, test_value)
    assert redis_client.get(test_key).decode() == test_value
    
    redis_client.delete(test_key)
    assert redis_client.get(test_key) is None

@pytest.mark.integration
def test_celery_task_retry(celery_worker):
    """Celery task retry mekanizması testi"""
    
    @celery_app.task(bind=True, max_retries=3)
    def test_task(self):
        if self.request.retries < 2:
            raise Exception("Temporary failure")
        return "Success"
    
    result = test_task.delay()
    
    # Task tamamlanana kadar bekle
    try:
        result.get(timeout=10)
    except Exception as e:
        pytest.fail(f"Task failed: {str(e)}")

@pytest.mark.integration
def test_concurrent_video_uploads(test_video, celery_worker):
    """Eşzamanlı video yükleme testi"""
    import concurrent.futures
    
    def upload_video():
        with open(test_video, 'rb') as f:
            response = client.post(
                "/upload-video/",
                files={"file": ("test.mp4", f, "video/mp4")}
            )
        return response.status_code
    
    # 5 eşzamanlı yükleme
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: upload_video(), range(5)))
    
    # Tüm isteklerin başarılı olduğunu kontrol et
    assert all(status == 200 for status in results)

@pytest.mark.integration
def test_error_handling():
    """Hata işleme testi"""
    
    # 1. Geçersiz video formatı
    with tempfile.NamedTemporaryFile(suffix='.txt') as f:
        f.write(b'not a video')
        f.seek(0)
        response = client.post(
            "/upload-video/",
            files={"file": ("test.txt", f, "text/plain")}
        )
    assert response.status_code == 400
    
    # 2. Geçersiz video ID
    response = client.get("/status/invalid_id")
    assert response.status_code == 404
    
    # 3. Rate limiting
    for _ in range(20):
        response = client.get("/status/test")
    assert response.status_code == 429

@pytest.mark.integration
def test_cleanup():
    """Test verilerini temizle"""
    
    # Redis'teki test verilerini temizle
    for key in redis_client.keys("test:*"):
        redis_client.delete(key)
    
    # Geçici dosyaları temizle
    temp_dir = tempfile.gettempdir()
    for file in os.listdir(temp_dir):
        if file.endswith('.mp4'):
            os.remove(os.path.join(temp_dir, file)) 