import os
import requests
from zipfile import ZipFile
from tqdm import tqdm

def download_file(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            progress_bar.update(size)

def main():
    model_dir = "model"
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    
    # Model URL'si
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip"
    zip_path = os.path.join(model_dir, "model.zip")
    
    print("Vosk Türkçe modelini indiriyorum...")
    download_file(model_url, zip_path)
    
    print("Modeli çıkartıyorum...")
    with ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(model_dir)
    
    # Zip dosyasını sil
    os.remove(zip_path)
    print("Model başarıyla indirildi ve kuruldu!")

if __name__ == "__main__":
    main() 