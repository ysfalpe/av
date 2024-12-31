import os
import boto3
from botocore.exceptions import ClientError
from abc import ABC, abstractmethod
from config import settings
import shutil
from typing import BinaryIO, Optional

class StorageBackend(ABC):
    """Abstract storage backend class"""
    
    @abstractmethod
    def save_file(self, file_obj: BinaryIO, file_path: str) -> str:
        """Dosyayı kaydet ve public URL döndür"""
        pass
    
    @abstractmethod
    def get_file(self, file_path: str) -> BinaryIO:
        """Dosyayı oku"""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Dosyayı sil"""
        pass
    
    @abstractmethod
    def get_public_url(self, file_path: str) -> str:
        """Dosyanın public URL'ini döndür"""
        pass

class LocalStorage(StorageBackend):
    """Local filesystem storage backend"""
    
    def __init__(self):
        self.base_path = settings.LOCAL_STORAGE_PATH
        os.makedirs(self.base_path, exist_ok=True)
    
    def save_file(self, file_obj: BinaryIO, file_path: str) -> str:
        """Dosyayı local filesystem'e kaydet"""
        full_path = os.path.join(self.base_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            shutil.copyfileobj(file_obj, f)
        
        return full_path
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Dosyayı local filesystem'den oku"""
        full_path = os.path.join(self.base_path, file_path)
        return open(full_path, 'rb')
    
    def delete_file(self, file_path: str) -> bool:
        """Dosyayı local filesystem'den sil"""
        full_path = os.path.join(self.base_path, file_path)
        try:
            os.remove(full_path)
            return True
        except OSError:
            return False
    
    def get_public_url(self, file_path: str) -> str:
        """Local dosya path'ini döndür"""
        return os.path.join(self.base_path, file_path)

class S3Storage(StorageBackend):
    """Amazon S3 storage backend"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION
        )
        self.bucket_name = settings.S3_BUCKET_NAME
    
    def save_file(self, file_obj: BinaryIO, file_path: str) -> str:
        """Dosyayı S3'e yükle"""
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                file_path,
                ExtraArgs={'ACL': 'public-read'}
            )
            return self.get_public_url(file_path)
        except ClientError as e:
            raise Exception(f"S3 upload error: {str(e)}")
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Dosyayı S3'ten indir"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return response['Body']
        except ClientError as e:
            raise Exception(f"S3 download error: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """Dosyayı S3'ten sil"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return True
        except ClientError:
            return False
    
    def get_public_url(self, file_path: str) -> str:
        """S3 public URL oluştur"""
        return f"https://{self.bucket_name}.s3.{settings.S3_REGION}.amazonaws.com/{file_path}"

def get_storage_backend() -> StorageBackend:
    """Storage backend factory"""
    if settings.STORAGE_TYPE == "s3":
        return S3Storage()
    return LocalStorage()

# Singleton instance
storage = get_storage_backend() 