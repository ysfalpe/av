import subprocess
import sys
import os
import time
import signal
import psutil
import shutil

def is_windows():
    return sys.platform.startswith('win')

def find_executable(name):
    """Çalıştırılabilir dosyayı bul"""
    if is_windows():
        name = f"{name}.exe"
    return shutil.which(name)

def run_command(command, **kwargs):
    if is_windows():
        return subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE, **kwargs)
    return subprocess.Popen(command, **kwargs)

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        print("\nKapatılıyor...")
        self.stop_all()
        self.running = False

    def check_redis(self):
        """Redis'in çalışıp çalışmadığını kontrol et"""
        redis_cli = find_executable("redis-cli")
        if not redis_cli:
            print("Redis bulunamadı. Lütfen Redis'i yükleyin.")
            return False
        
        try:
            result = subprocess.run([redis_cli, "ping"], capture_output=True, text=True)
            return result.stdout.strip() == "PONG"
        except:
            return False

    def start_redis(self):
        print("Redis başlatılıyor...")
        redis_server = find_executable("redis-server")
        if not redis_server:
            print("Redis bulunamadı. Lütfen Redis'i yükleyin.")
            sys.exit(1)
            
        if not self.check_redis():
            process = run_command([redis_server])
            self.processes.append(process)
            time.sleep(2)  # Redis'in başlaması için bekle
        else:
            print("Redis zaten çalışıyor.")

    def start_celery(self):
        print("Celery worker başlatılıyor...")
        env = os.environ.copy()
        if is_windows():
            celery_cmd = ["celery", "-A", "tasks", "worker", "--loglevel=info", "--pool=solo"]
        else:
            celery_cmd = ["celery", "-A", "tasks", "worker", "--loglevel=info"]
        
        process = run_command(celery_cmd, cwd="backend", env=env)
        self.processes.append(process)

    def start_flower(self):
        print("Celery Flower başlatılıyor...")
        flower_cmd = ["celery", "-A", "tasks", "flower"]
        process = run_command(flower_cmd, cwd="backend")
        self.processes.append(process)

    def start_backend(self):
        print("Backend başlatılıyor...")
        backend_cmd = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
        process = run_command(backend_cmd, cwd="backend")
        self.processes.append(process)

    def start_frontend(self):
        print("Frontend başlatılıyor...")
        if is_windows():
            npm_cmd = ["npm.cmd", "run", "dev"]
        else:
            npm_cmd = ["npm", "run", "dev"]
        
        process = run_command(npm_cmd, cwd="frontend")
        self.processes.append(process)

    def stop_all(self):
        print("Tüm servisler durduruluyor...")
        for process in self.processes:
            kill_process_tree(process.pid)
        self.processes = []

    def check_requirements(self):
        """Gerekli paketleri kontrol et"""
        required_packages = {
            "redis": "redis-server",
            "celery": "celery",
            "fastapi": "uvicorn",
            "vosk": "vosk",
            "moviepy": "moviepy",
            "python-magic": "python-magic",
            "aioredis": "aioredis",
            "psutil": "psutil"
        }
        
        missing_packages = []
        for package, name in required_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(name)
        
        if missing_packages:
            print("Eksik paketler:", ", ".join(missing_packages))
            print("Lütfen şu komutu çalıştırın:")
            print("pip install " + " ".join(missing_packages))
            return False
        return True

    def start_all(self):
        try:
            if not self.check_requirements():
                return

            # Redis'i başlat
            self.start_redis()
            time.sleep(2)  # Redis'in tamamen başlaması için bekle

            # Celery worker'ı başlat
            self.start_celery()
            time.sleep(2)

            # Flower'ı başlat
            self.start_flower()
            time.sleep(1)

            # Backend'i başlat
            self.start_backend()
            time.sleep(1)

            # Frontend'i başlat
            self.start_frontend()

            print("\nTüm servisler başlatıldı!")
            print("Frontend: http://localhost:5173")
            print("Backend: http://localhost:8000")
            print("Flower: http://localhost:5555")
            
            # Servisleri çalışır durumda tut
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            self.stop_all()

if __name__ == "__main__":
    print("Video Alt Yazı Oluşturucu - Servis Başlatıcı")
    print("============================================")
    
    manager = ServiceManager()
    manager.start_all() 