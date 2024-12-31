import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test konfigürasyonu
export const options = {
    stages: [
        { duration: '2m', target: 100 },  // Ramp-up
        { duration: '5m', target: 100 },  // Steady state
        { duration: '2m', target: 0 },    // Ramp-down
    ],
    thresholds: {
        'http_req_duration': ['p(95)<500'],  // 95% istekleri 500ms'den hızlı olmalı
        'http_req_failed': ['rate<0.01'],    // %1'den az hata
        'errors': ['rate<0.05'],             // %5'den az özel hata
    },
};

// Test videosu
const testVideo = open('./data/test_video.mp4', 'b');

// API endpoint'leri
const API_BASE_URL = 'http://localhost:8000';
const ENDPOINTS = {
    upload: `${API_BASE_URL}/upload-video/`,
    status: (id) => `${API_BASE_URL}/status/${id}`,
    subtitles: (id, format) => `${API_BASE_URL}/subtitles/${id}/${format}`,
};

export default function () {
    // 1. Video yükleme
    const uploadResponse = http.post(ENDPOINTS.upload, {
        file: http.file(testVideo, 'test.mp4', 'video/mp4'),
    });
    
    check(uploadResponse, {
        'upload başarılı': (r) => r.status === 200,
        'video_id alındı': (r) => r.json('video_id') !== undefined,
    }) || errorRate.add(1);
    
    if (uploadResponse.status !== 200) {
        console.error(`Upload hatası: ${uploadResponse.status}`);
        return;
    }
    
    const videoId = uploadResponse.json('video_id');
    
    // 2. İşleme durumunu kontrol et
    let processingComplete = false;
    let attempts = 0;
    const maxAttempts = 30;
    
    while (!processingComplete && attempts < maxAttempts) {
        const statusResponse = http.get(ENDPOINTS.status(videoId));
        
        check(statusResponse, {
            'status kontrolü başarılı': (r) => r.status === 200,
        }) || errorRate.add(1);
        
        if (statusResponse.status === 200) {
            const status = statusResponse.json('status');
            if (status === 'completed') {
                processingComplete = true;
            } else if (status === 'failed') {
                console.error('Video işleme hatası');
                errorRate.add(1);
                return;
            }
        }
        
        attempts++;
        sleep(1);
    }
    
    if (!processingComplete) {
        console.error('Video işleme zaman aşımı');
        errorRate.add(1);
        return;
    }
    
    // 3. Altyazıları indir
    for (const format of ['srt', 'vtt']) {
        const subtitleResponse = http.get(ENDPOINTS.subtitles(videoId, format));
        
        check(subtitleResponse, {
            [`${format} indirme başarılı`]: (r) => r.status === 200,
            [`${format} içerik var`]: (r) => r.body.length > 0,
        }) || errorRate.add(1);
    }
    
    // İstekler arası bekleme
    sleep(1);
}

// Test sonrası temizlik
export function teardown() {
    // Test verilerini temizle
    console.log('Test tamamlandı, veriler temizleniyor...');
} 