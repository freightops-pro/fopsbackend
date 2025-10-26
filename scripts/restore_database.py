#!/usr/bin/env python3
"""
FreightOps Pro - Database Restore Script

Restores database from encrypted backup stored in S3/R2
"""

import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import logging
from cryptography.fernet import Fernet
import json
import argparse

# Add the parent directory to the path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseRestore:
    def __init__(self):
        self.restore_dir = Path("/tmp/freightops_restore")
        self.restore_dir.mkdir(exist_ok=True)
        
        # Encryption key (should match the backup encryption key)
        self.encryption_key = os.getenv('BACKUP_ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher = Fernet(self.encryption_key)
        
        # Storage configuration
        self.storage_type = os.getenv('BACKUP_STORAGE_TYPE', 's3')
        self.bucket_name = os.getenv('AWS_S3_BUCKET_NAME', 'freightops-backups')
        
    def extract_database_url(self) -> dict:
        """Extract database connection details from DATABASE_URL"""
        import re
        
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
    
    def download_from_s3(self, s3_key: str, local_path: Path):
        """Download backup from S3"""
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            )
            
            logger.info(f"Downloading from S3: s3://{self.bucket_name}/{s3_key}")
            
            s3_client.download_file(self.bucket_name, s3_key, str(local_path))
            
            logger.info(f"Download successful: {local_path}")
            
        except ClientError as e:
            logger.error(f"S3 download failed: {e}")
            raise
    
    def download_from_r2(self, r2_key: str, local_path: Path):
        """Download backup from Cloudflare R2"""
        try:
            r2_client = boto3.client(
                's3',
                endpoint_url=os.getenv('CLOUDFLARE_R2_ENDPOINT_URL'),
                aws_access_key_id=os.getenv('CLOUDFLARE_R2_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('CLOUDFLARE_R2_SECRET_ACCESS_KEY'),
                region_name='auto'
            )
            
            logger.info(f"Downloading from R2: {self.bucket_name}/{r2_key}")
            
            r2_client.download_file(self.bucket_name, r2_key, str(local_path))
            
            logger.info(f"R2 download successful: {local_path}")
            
        except ClientError as e:
            logger.error(f"R2 download failed: {e}")
            raise
    
    def decrypt_backup(self, encrypted_path: Path) -> Path:
        """Decrypt backup file"""
        decrypted_path = encrypted_path.with_suffix('')  # Remove .enc extension
        
        logger.info(f"Decrypting backup: {decrypted_path}")
        
        with open(encrypted_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.cipher.decrypt(encrypted_data)
        
        with open(decrypted_path, 'wb') as f:
            f.write(decrypted_data)
        
        logger.info(f"Backup decrypted: {decrypted_path}")
        return decrypted_path
    
    def decompress_backup(self, compressed_path: Path) -> Path:
        """Decompress backup file"""
        decompressed_path = compressed_path.with_suffix('')  # Remove .gz extension
        
        logger.info(f"Decompressing backup: {decompressed_path}")
        
        with gzip.open(compressed_path, 'rb') as f_in:
            with open(decompressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"Backup decompressed: {decompressed_path}")
        return decompressed_path
    
    def restore_database(self, sql_file_path: Path):
        """Restore database from SQL file"""
        try:
            db_config = self.extract_database_url()
            
            # Set environment variables for psql
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            # Build psql command
            cmd = [
                'psql',
                '-h', db_config['host'],
                '-p', db_config['port'],
                '-U', db_config['username'],
                '-d', db_config['database'],
                '-f', str(sql_file_path),
                '--quiet'
            ]
            
            logger.info(f"Restoring database from: {sql_file_path}")
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"psql restore failed: {result.stderr}")
            
            logger.info("Database restored successfully")
            
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            raise
    
    def list_available_backups(self) -> list:
        """List available backups in storage"""
        backups = []
        
        try:
            if self.storage_type == 'r2':
                r2_client = boto3.client(
                    's3',
                    endpoint_url=os.getenv('CLOUDFLARE_R2_ENDPOINT_URL'),
                    aws_access_key_id=os.getenv('CLOUDFLARE_R2_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('CLOUDFLARE_R2_SECRET_ACCESS_KEY'),
                    region_name='auto'
                )
                
                response = r2_client.list_objects_v2(Bucket=self.bucket_name)
            else:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
                )
                
                response = s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('.sql.gz.enc'):
                        backups.append({
                            'key': key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'type': key.split('/')[0] if '/' in key else 'unknown'
                        })
            
            # Sort by last modified (newest first)
            backups.sort(key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        
        return backups
    
    def restore_from_backup(self, backup_key: str) -> dict:
        """Main restore process"""
        try:
            logger.info(f"Starting restore from backup: {backup_key}")
            
            # Download backup
            encrypted_path = self.restore_dir / Path(backup_key).name
            
            if self.storage_type == 'r2':
                self.download_from_r2(backup_key, encrypted_path)
            else:
                self.download_from_s3(backup_key, encrypted_path)
            
            # Decrypt backup
            decrypted_path = self.decrypt_backup(encrypted_path)
            
            # Decompress backup
            sql_path = self.decompress_backup(decrypted_path)
            
            # Restore database
            self.restore_database(sql_path)
            
            # Cleanup local files
            for file_path in [encrypted_path, decrypted_path, sql_path]:
                if file_path.exists():
                    file_path.unlink()
            
            logger.info("Restore completed successfully")
            
            return {
                'status': 'success',
                'backup_key': backup_key,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'backup_key': backup_key,
                'timestamp': datetime.utcnow().isoformat()
            }

def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(description='FreightOps Database Restore')
    parser.add_argument('--backup-key', help='S3/R2 key of backup to restore')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--latest', action='store_true', help='Restore latest backup')
    
    args = parser.parse_args()
    
    restore = DatabaseRestore()
    
    if args.list:
        backups = restore.list_available_backups()
        print(json.dumps(backups, indent=2))
        return
    
    if args.latest:
        backups = restore.list_available_backups()
        if not backups:
            print("No backups found")
            sys.exit(1)
        
        backup_key = backups[0]['key']
        print(f"Restoring latest backup: {backup_key}")
    elif args.backup_key:
        backup_key = args.backup_key
    else:
        print("Error: Must specify --backup-key, --latest, or --list")
        sys.exit(1)
    
    result = restore.restore_from_backup(backup_key)
    
    # Print result as JSON
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result['status'] == 'success' else 1)

if __name__ == '__main__':
    main()

