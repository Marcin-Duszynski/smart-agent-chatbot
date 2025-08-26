import os
import boto3
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class StorageInterface(ABC):
    """Abstract storage interface"""
    
    @abstractmethod
    def upload_file(self, file_data: BinaryIO, file_path: str) -> str:
        """Upload file and return public URL"""
        pass
    
    @abstractmethod
    def download_file(self, file_path: str) -> bytes:
        """Download file content"""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        pass
    
    @abstractmethod
    def get_file_url(self, file_path: str) -> str:
        """Get public URL for file"""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        pass

class LocalStorage(StorageInterface):
    """Local file system storage"""
    
    def __init__(self, base_path: str = ".", base_url: str = "http://localhost:8000"):
        self.base_path = base_path
        self.base_url = base_url
        os.makedirs(base_path, exist_ok=True)
    
    def upload_file(self, file_data: BinaryIO, file_path: str) -> str:
        full_path = os.path.join(self.base_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(file_data.read())
        
        return self.get_file_url(file_path)
    
    def download_file(self, file_path: str) -> bytes:
        full_path = os.path.join(self.base_path, file_path)
        with open(full_path, 'rb') as f:
            return f.read()
    
    def delete_file(self, file_path: str) -> bool:
        try:
            full_path = os.path.join(self.base_path, file_path)
            os.remove(full_path)
            return True
        except FileNotFoundError:
            return False
    
    def get_file_url(self, file_path: str) -> str:
        return f"{self.base_url}/{file_path}"
    
    def file_exists(self, file_path: str) -> bool:
        full_path = os.path.join(self.base_path, file_path)
        return os.path.exists(full_path)

class S3Storage(StorageInterface):
    """AWS S3 storage"""
    
    def __init__(self, bucket_name: str, region: str = "us-east-1", 
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 cloudfront_domain: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region = region
        self.cloudfront_domain = cloudfront_domain
        
        # Initialize S3 client
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region
        )
        self.s3_client = session.client('s3')
        
        # Create bucket if it doesn't exist
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                try:
                    if self.region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    logger.info(f"Created S3 bucket: {self.bucket_name}")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
    
    def upload_file(self, file_data: BinaryIO, file_path: str) -> str:
        try:
            self.s3_client.upload_fileobj(
                file_data, 
                self.bucket_name, 
                file_path,
                ExtraArgs={'ACL': 'public-read'}
            )
            return self.get_file_url(file_path)
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise
    
    def download_file(self, file_path: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise
    
    def delete_file(self, file_path: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def get_file_url(self, file_path: str) -> str:
        if self.cloudfront_domain:
            return f"https://{self.cloudfront_domain}/{file_path}"
        else:
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_path}"
    
    def file_exists(self, file_path: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError:
            return False

class StorageManager:
    """Storage manager factory"""
    
    def __init__(self, storage_type: str = "local", **kwargs):
        self.storage_type = storage_type
        self.storage = self._create_storage(**kwargs)
    
    def _create_storage(self, **kwargs) -> StorageInterface:
        if self.storage_type.lower() == "s3":
            return S3Storage(**kwargs)
        elif self.storage_type.lower() == "local":
            return LocalStorage(**kwargs)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def upload_file(self, file_data: BinaryIO, file_path: str) -> str:
        return self.storage.upload_file(file_data, file_path)
    
    def download_file(self, file_path: str) -> bytes:
        return self.storage.download_file(file_path)
    
    def delete_file(self, file_path: str) -> bool:
        return self.storage.delete_file(file_path)
    
    def get_file_url(self, file_path: str) -> str:
        return self.storage.get_file_url(file_path)
    
    def file_exists(self, file_path: str) -> bool:
        return self.storage.file_exists(file_path)
