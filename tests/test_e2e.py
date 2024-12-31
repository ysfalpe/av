import pytest
from playwright.sync_api import Page, expect
import os
import time

def test_homepage(page: Page):
    """Ana sayfa testi"""
    # Ana sayfaya git
    page.goto("http://localhost:5173")
    
    # Başlığı kontrol et
    expect(page.get_by_text("Video Altyazı Oluşturucu")).to_be_visible()
    
    # Upload alanını kontrol et
    expect(page.get_by_text("Video yüklemek için tıklayın veya sürükleyin")).to_be_visible()

def test_video_upload_and_processing(page: Page):
    """Video yükleme ve işleme testi"""
    # Ana sayfaya git
    page.goto("http://localhost:5173")
    
    # Test video dosyasını yükle
    with page.expect_file_chooser() as fc_info:
        page.click('text=Video yüklemek için tıklayın')
    file_chooser = fc_info.value
    file_chooser.set_files("tests/data/test_video.mp4")
    
    # Progress bar'ın görünmesini bekle
    expect(page.get_by_role("progressbar")).to_be_visible()
    
    # İşleme durumunu kontrol et
    expect(page.get_by_text("Video işleniyor...")).to_be_visible()
    
    # İşleme tamamlanana kadar bekle (max 5 dakika)
    page.wait_for_selector("text=İşlem tamamlandı!", timeout=300000)
    
    # Altyazıların görüntülenmesini kontrol et
    expect(page.get_by_text("Altyazılar")).to_be_visible()

def test_subtitle_download(page: Page):
    """Altyazı indirme testi"""
    # Ana sayfaya git ve video yükle
    test_video_upload_and_processing(page)
    
    # SRT indirme butonunu kontrol et
    srt_button = page.get_by_role("button", name="SRT İndir")
    expect(srt_button).to_be_visible()
    
    # VTT indirme butonunu kontrol et
    vtt_button = page.get_by_role("button", name="VTT İndir")
    expect(vtt_button).to_be_visible()
    
    # Dosyaları indir ve kontrol et
    with page.expect_download() as download_info:
        srt_button.click()
    download = download_info.value
    
    # İndirilen dosyayı kontrol et
    assert download.path().endswith('.srt')
    with open(download.path(), 'r', encoding='utf-8') as f:
        content = f.read()
        assert "00:" in content  # Zaman damgası kontrolü

def test_error_handling(page: Page):
    """Hata işleme testi"""
    # Ana sayfaya git
    page.goto("http://localhost:5173")
    
    # Geçersiz dosya yüklemeyi dene
    with page.expect_file_chooser() as fc_info:
        page.click('text=Video yüklemek için tıklayın')
    file_chooser = fc_info.value
    file_chooser.set_files("tests/data/invalid.txt")
    
    # Hata mesajını kontrol et
    expect(page.get_by_text("Desteklenmeyen dosya formatı")).to_be_visible()

def test_responsive_design(page: Page):
    """Responsive tasarım testi"""
    page.goto("http://localhost:5173")
    
    # Mobil görünüm
    page.set_viewport_size({"width": 375, "height": 667})
    expect(page.get_by_text("Video Altyazı Oluşturucu")).to_be_visible()
    
    # Tablet görünüm
    page.set_viewport_size({"width": 768, "height": 1024})
    expect(page.get_by_text("Video Altyazı Oluşturucu")).to_be_visible()
    
    # Desktop görünüm
    page.set_viewport_size({"width": 1920, "height": 1080})
    expect(page.get_by_text("Video Altyazı Oluşturucu")).to_be_visible()

def test_performance(page: Page):
    """Performans testi"""
    # Performance metrics'i başlat
    client = page.context.new_cdp_session(page)
    client.send("Performance.enable")
    
    # Sayfayı yükle
    page.goto("http://localhost:5173")
    
    # Metrics'i al
    metrics = client.send("Performance.getMetrics")
    
    # Önemli metrikleri kontrol et
    for metric in metrics["metrics"]:
        if metric["name"] == "FirstContentfulPaint":
            assert metric["value"] < 3000  # 3 saniyeden az olmalı
        elif metric["name"] == "DomContentLoaded":
            assert metric["value"] < 5000  # 5 saniyeden az olmalı

def test_concurrent_uploads(page: Page):
    """Eşzamanlı yükleme testi"""
    # İki browser penceresi aç
    context = page.context
    page1 = context.new_page()
    page2 = context.new_page()
    
    # Her iki pencerede de video yüklemeyi başlat
    for test_page in [page1, page2]:
        test_page.goto("http://localhost:5173")
        with test_page.expect_file_chooser() as fc_info:
            test_page.click('text=Video yüklemek için tıklayın')
        file_chooser = fc_info.value
        file_chooser.set_files("tests/data/test_video.mp4")
    
    # Her iki işlemin de tamamlanmasını bekle
    for test_page in [page1, page2]:
        test_page.wait_for_selector("text=İşlem tamamlandı!", timeout=300000)
        expect(test_page.get_by_text("Altyazılar")).to_be_visible()

def test_cleanup():
    """Test dosyalarını temizle"""
    # İndirilen dosyaları temizle
    downloads_dir = "tests/downloads"
    if os.path.exists(downloads_dir):
        for file in os.listdir(downloads_dir):
            os.remove(os.path.join(downloads_dir, file)) 