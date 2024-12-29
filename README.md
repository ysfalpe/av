# Video Alt Yazı Oluşturucu

Bu proje, yüklenen videolara otomatik olarak alt yazı ekleyen bir web uygulamasıdır. Kullanıcılar alt yazıların fontunu, boyutunu ve konumunu özelleştirebilir.

## Özellikler

- Video yükleme
- Otomatik konuşma tanıma
- Alt yazı font özelleştirme
- Alt yazı boyut ayarlama
- Alt yazı konum seçme

## Gereksinimler

### Backend
- Python 3.8+
- FastAPI
- Vosk
- MoviePy
- SQLAlchemy

### Frontend
- Node.js
- Vue.js
- Vite

## Kurulum

1. Vosk modelini indirin:
   - https://alphacephei.com/vosk/models adresinden "vosk-model-small-tr" modelini indirin
   - İndirilen dosyayı `backend/model` klasörüne çıkartın

2. Backend kurulumu:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Frontend kurulumu:
```bash
cd frontend
npm install
```

## Çalıştırma

1. Backend'i başlatın:
```bash
cd backend
uvicorn main:app --reload
```

2. Frontend'i başlatın:
```bash
cd frontend
npm run dev
```

3. Tarayıcınızda http://localhost:5173 adresine gidin

## Kullanım

1. "Video Yükle" butonuna tıklayın ve bir video dosyası seçin
2. Video yüklendikten sonra otomatik olarak alt yazılar oluşturulacaktır
3. Alt yazı ayarlarını kontrol panelinden özelleştirin:
   - Font seçimi
   - Boyut ayarı
   - Konum seçimi

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. 