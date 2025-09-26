"""
Storage Service
Handles file storage operations for templates and documents
"""

import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from config import settings


class StorageService:
    """File storage operations service"""

    @staticmethod
    async def store_template_file(file: UploadFile, file_path: str) -> str:
        """Store template file and return the path"""
        try:
            # Ensure the directory exists
            storage_path = Path(settings.STORAGE_PATH) / file_path
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the file
            with open(storage_path, 'wb') as buffer:
                content = await file.read()
                buffer.write(content)

            return str(storage_path)
        except Exception as e:
            raise Exception(f"Failed to store template file: {str(e)}")

    @staticmethod
    async def store_preview_file(file: UploadFile, file_path: str) -> str:
        """Store preview file and return the path"""
        try:
            # Ensure the directory exists
            storage_path = Path(settings.STORAGE_PATH) / file_path
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the file
            with open(storage_path, 'wb') as buffer:
                content = await file.read()
                buffer.write(content)

            return str(storage_path)
        except Exception as e:
            raise Exception(f"Failed to store preview file: {str(e)}")

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file from storage"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return {"error": "File not found"}

            stat = os.stat(file_path)
            return {
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": os.path.isfile(file_path),
                "is_dir": os.path.isdir(file_path)
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def move_file(source_path: str, destination_path: str) -> bool:
        """Move file from source to destination"""
        try:
            # Ensure destination directory exists
            Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source_path, destination_path)
            return True
        except Exception:
            return False

    @staticmethod
    def get_storage_path(relative_path: str = "") -> str:
        """Get absolute storage path"""
        return str(Path(settings.STORAGE_PATH) / relative_path)

    @staticmethod
    def ensure_storage_path(path: str) -> str:
        """Ensure storage directory exists and return path"""
        storage_path = Path(path)
        storage_path.mkdir(parents=True, exist_ok=True)
        return str(storage_path)


# Convenience functions for imports
def get_storage_path(relative_path: str = "") -> str:
    """Get absolute storage path"""
    return StorageService.get_storage_path(relative_path)


def ensure_storage_path(path: str) -> str:
    """Ensure storage directory exists and return path"""
    return StorageService.ensure_storage_path(path)
