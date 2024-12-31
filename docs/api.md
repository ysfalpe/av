# Video Subtitler API Dokümantasyonu

## Genel Bilgiler

- Base URL: `http://localhost:8000`
- Tüm istekler JSON formatında yanıt döner
- Hata durumunda `error` field'ı ile hata mesajı döner
- Rate limiting: 10 istek/dakika
- Maksimum video boyutu: 100MB
- Desteklenen video formatları: MP4, AVI, MOV, MKV

## Endpoints

### Video Yükleme

```http
POST /upload-video/
Content-Type: multipart/form-data
```

Video dosyasını yükler ve işleme alır.

**Request Body:**
- `file`: Video dosyası (multipart/form-data)

**Response:**
```json
{
    "video_id": "string",
    "message": "Video başarıyla yüklendi ve işleme alındı"
}
```

**Hata Kodları:**
- `400`: Geçersiz dosya formatı
- `413`: Dosya boyutu çok büyük
- `429`: Rate limit aşıldı

### İşleme Durumu

```http
GET /status/{video_id}
```

Video işleme durumunu kontrol eder.

**Response:**
```json
{
    "status": "processing|completed|failed",
    "progress": 0-100,
    "error": "string (optional)"
}
```

**Hata Kodları:**
- `404`: Video bulunamadı

### Altyazı İndirme

```http
GET /subtitles/{video_id}/{format}
```

İşlenmiş altyazıları indirir.

**Path Parameters:**
- `video_id`: Video ID
- `format`: `srt` veya `vtt`

**Response:**
- Content-Type: `text/plain`
- Body: Altyazı içeriği

**Hata Kodları:**
- `404`: Video veya altyazı bulunamadı
- `422`: Altyazı henüz hazır değil

### Altyazılı Video İndirme

```http
GET /download/{video_id}
```

Altyazıları gömülmüş videoyu indirir.

**Response:**
- Content-Type: `video/mp4`
- Body: Video dosyası

**Hata Kodları:**
- `404`: Video bulunamadı
- `422`: Video henüz hazır değil

## Hata Yapısı

Tüm hata yanıtları aşağıdaki formatta döner:

```json
{
    "error": {
        "code": "string",
        "message": "string",
        "details": {} (optional)
    }
}
```

## Rate Limiting

- Her IP için dakikada 10 istek
- Her endpoint için ayrı limit
- `X-RateLimit-Limit` ve `X-RateLimit-Remaining` header'ları ile limit bilgisi

## Örnek Kullanım

### cURL

```bash
# Video yükleme
curl -X POST http://localhost:8000/upload-video/ \
  -F "file=@video.mp4"

# Durum kontrolü
curl http://localhost:8000/status/video_id

# Altyazı indirme
curl http://localhost:8000/subtitles/video_id/srt > subtitles.srt
```

### Python

```python
import requests

# Video yükleme
with open('video.mp4', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/upload-video/',
        files={'file': f}
    )
video_id = response.json()['video_id']

# Durum kontrolü
status = requests.get(
    f'http://localhost:8000/status/{video_id}'
).json()

# Altyazı indirme
subtitles = requests.get(
    f'http://localhost:8000/subtitles/{video_id}/srt'
).text
```

## WebSocket API

Real-time işleme durumu için WebSocket API de mevcuttur:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/status/{video_id}')

ws.onmessage = (event) => {
    const status = JSON.parse(event.data)
    console.log(status.progress)
}
``` 