#!/usr/bin/env python3
"""
FreightOps Pro - Database Backup Script

Creates encrypted database backup and uploads to S3/R2
Retention: 30 daily, 12 monthly, 7 yearly
"""

import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import logging
from cryptography.fernet import Fernet
import json

# Add the parent directory to the path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseBackup:
    def __init__(self):
        self.backup_dir = Path("/tmp/freightops_backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Encryption key (should be stored securely in production)
        self.encryption_key = os.getenv('BACKUP_ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher = Fernet(self.encryption_key)
        
        # Storage configuration
        self.storage_type = os.getenv('BACKUP_STORAGE_TYPE', 's3')  # 's3' or 'r2'
        self.bucket_name = os.getenv('AWS_S3_BUCKET_NAME', 'freightops-backups')
        
    def create_backup_filename(self, backup_type: str = 'daily') -> str:
        """Create standardized backup filename"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"freightops_{backup_type}_backup_{timestamp}.sql"
    
    def extract_database_url(self) -> dict:
        """Extract database connection details from DATABASE_URL"""
        import re
        
        # Parse PostgreSQL URL
        pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)'
        match = re.match(pattern, settings.DATABASE_URL)
        
        if not match:
            raise ValueError("Invalid DATABASE_URL format")
        
        username, password, host, port, database = match.groups()
        
        return {
            'host': host,
            'port': port,
            'database': database,
            'username': username,
            'password': password
        }
    
    def create_database_dump(self, backup_filename: str) -> Path:
        """Create database dump using pg_dump"""
        try:
            db_config = self.extract_database_url()
            
            # Set environment variables for pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '-h', db_config['host'],
                '-p', db_config['port'],
                '-U', db_config['username'],
                '-d', db_config['database'],
                '--verbose',
                '--no-password',
                '--format=plain',
                '--no-owner',
                '--no-privileges'
            ]
            
            backup_path = self.backup_dir / backup_filename
            
            logger.info(f"Creating database dump: {backup_path}")
            
            with open(backup_path, 'w') as f:
                result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                raise Exception(f"pg_dump failed: {result.stderr}")
            
            logger.info(f"Database dump created successfully: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create database dump: {e}")
            raise
    
    def compress_backup(self, backup_path: Path) -> Path:
        """Compress backup file using gzip"""
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
        
        logger.info(f"Compressing backup: {compressed_path}")
        
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove original uncompressed file
        backup_path.unlink()
        
        logger.info(f"Backup compressed: {compressed_path}")
        return compressed_path
    
    def encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file"""
        encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
        
        logger.info(f"Encrypting backup: {encrypted_path}")
        
        with open(backup_path, 'rb') as f:
            data = f.read()
        
        encrypted_data = self.cipher.encrypt(data)
        
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Remove unencrypted file
        backup_path.unlink()
        
        logger.info(f"Backup encrypted: {encrypted_path}")
        return encrypted_path
    
    def upload_to_s3(self, backup_path: Path, s3_key: str):
        """Upload backup to S3"""
        try:
            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            )
            
            logger.info(f"Uploading to S3: s3://{self.bucket_name}/{s3_key}")
            
            s3_client.upload_file(
                str(backup_path),
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'  # Cheaper storage for backups
                }
            )
            
            logger.info(f"Upload successful: s3://{self.bucket_name}/{s3_key}")
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise
    
    def upload_to_r2(self, backup_path: Path, r2_key: str):
        """Upload backup to Cloudflare R2"""
        try:
            # Initialize S3 client for R2
            r2_client = boto3.client(
                's3',
                endpoint_url=os.getenv('CLOUDFLARE_R2_ENDPOINT_URL'),
                aws_access_key_id=os.getenv('CLOUDFLARE_R2_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('CLOUDFLARE_R2_SECRET_ACCESS_KEY'),
                region_name='auto'
            )
            
            logger.info(f"Uploading to R2: {self.bucket_name}/{r2_key}")
            
            r2_client.upload_file(
                str(backup_path),
                self.bucket_name,
                r2_key,
                ExtraArgs={
                    'StorageClass': 'STANDARD'
                }
            )
            
            logger.info(f"R2 upload successful: {self.bucket_name}/{r2_key}")
            
        except ClientError as e:
            logger.error(f"R2 upload failed: {e}")
            raise
    
    def cleanup_old_backups(self):
        """Clean up old backup files from local storage"""
        try:
            for backup_file in self.backup_dir.glob('*'):
                if backup_file.is_file():
                    # Remove files older than 7 days
                    if datetime.fromtimestamp(backup_file.stat().st_mtime) < datetime.now() - timedelta(days=7):
                        backup_file.unlink()
                        logger.info(f"Cleaned up old backup: {backup_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def get_backup_metadata(self, backup_path: Path) -> dict:
        """Get metadata about the backup file"""
        stat = backup_path.stat()
        return {
            'filename': backup_path.name,
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'checksum': self.calculate_checksum(backup_path)
        }
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        import hashlib
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def create_backup(self, backup_type: str = 'daily') -> dict:
        """Main backup creation process"""
        try:
            logger.info(f"Starting {backup_type} backup process")
            
            # Create backup filename
            backup_filename = self.create_backup_filename(backup_type)
            
            # Create database dump
            backup_path = self.create_database_dump(backup_filename)
            
            # Compress backup
            compressed_path = self.compress_backup(backup_path)
            
            # Encrypt backup
            encrypted_path = self.encrypt_backup(compressed_path)
            
            # Get backup metadata
            metadata = self.get_backup_metadata(encrypted_path)
            
            # Upload to storage
            s3_key = f"{backup_type}/{encrypted_path.name}"
            
            if self.storage_type == 'r2':
                self.upload_to_r2(encrypted_path, s3_key)
            else:
                self.upload_to_s3(encrypted_path, s3_key)
            
            # Cleanup local files
            encrypted_path.unlink()
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            logger.info(f"{backup_type.capitalize()} backup completed successfully")
            
            return {
                'status': 'success',
                'backup_type': backup_type,
                'metadata': metadata,
                'storage_location': f"{self.storage_type}://{self.bucket_name}/{s3_key}",
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'backup_type': backup_type,
                'timestamp': datetime.utcnow().isoformat()
            }

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FreightOps Database Backup')
    parser.add_argument('--type', choices=['daily', 'weekly', 'monthly'], default='daily',
                       help='Type of backup to create')
    
    args = parser.parse_args()
    
    backup = DatabaseBackup()
    result = backup.create_backup(args.type)
    
    # Print result as JSON
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result['status'] == 'success' else 1)

if __name__ == '__main__':
    main()

