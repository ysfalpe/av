import os
import requests
from tqdm import tqdm
import zipfile

def download_model():
    """Vosk modelini indir ve kur"""
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip"
    zip_path = "model.zip"
    model_dir = "model"
    
    # Model zaten varsa indirme
    if os.path.exists(model_dir):
        print("Model zaten mevcut.")
        return
    
    print(f"Model indiriliyor: {model_url}")
    
    # Modeli indir
    response = requests.get(model_url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(zip_path, 'wb') as f, tqdm(
        desc="İndiriliyor",
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            pbar.update(size)
    
    print("Model ZIP dosyası indirme tamamlandı.")
    
    # ZIP dosyasını aç
    print("Model çıkartılıyor...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(".")
    
    # ZIP dosyasını sil
    os.remove(zip_path)
    
    # Model klasörünü yeniden adlandır
    os.rename("vosk-model-small-tr-0.3", model_dir)
    
    print("Model kurulumu tamamlandı.")

if __name__ == "__main__":
    download_model() 