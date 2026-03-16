"""
Google Drive Integration Service
Handles file picker, preview, and download from Google Drive
"""
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import io
import logging

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for Google Drive operations"""
    
    @staticmethod
    def get_drive_service(access_token):
        """Create Google Drive API service"""
        credentials = Credentials(token=access_token)
        return build('drive', 'v3', credentials=credentials)
    
    @staticmethod
    def list_files(access_token, page_size=20, page_token=None, query=None):
        """
        List files from Google Drive
        
        Args:
            access_token: Google OAuth access token
            page_size: Number of files per page
            page_token: Token for pagination
            query: Drive API query string (e.g., "mimeType='application/pdf'")
        
        Returns:
            dict with 'files' list and 'nextPageToken'
        """
        try:
            service = GoogleDriveService.get_drive_service(access_token)
            
            # Default query: exclude trashed files
            if not query:
                query = "trashed=false"
            
            results = service.files().list(
                pageSize=page_size,
                pageToken=page_token,
                q=query,
                fields="nextPageToken, files(id, name, mimeType, iconLink, webViewLink, thumbnailLink, size, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            next_page_token = results.get('nextPageToken')
            
            logger.info(f'Listed {len(files)} files from Google Drive')
            
            return {
                'files': files,
                'nextPageToken': next_page_token
            }
            
        except Exception as e:
            logger.error(f'Error listing Drive files: {e}')
            return {'files': [], 'nextPageToken': None, 'error': str(e)}
    
    @staticmethod
    def get_file_metadata(access_token, file_id):
        """
        Get file metadata from Google Drive
        
        Args:
            access_token: Google OAuth access token
            file_id: Google Drive file ID
        
        Returns:
            dict with file metadata
        """
        try:
            service = GoogleDriveService.get_drive_service(access_token)
            
            file = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, iconLink, webViewLink, thumbnailLink, size, modifiedTime, description"
            ).execute()
            
            logger.info(f'Retrieved metadata for file: {file.get("name")}')
            return file
            
        except Exception as e:
            logger.error(f'Error getting file metadata: {e}')
            return {'error': str(e)}
    
    @staticmethod
    def download_file(access_token, file_id):
        """
        Download file content from Google Drive
        
        Args:
            access_token: Google OAuth access token
            file_id: Google Drive file ID
        
        Returns:
            tuple of (file_content_bytes, file_metadata)
        """
        try:
            service = GoogleDriveService.get_drive_service(access_token)
            
            # Get file metadata
            file_metadata = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size"
            ).execute()
            
            # Download file content
            request = service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f'Download progress: {int(status.progress() * 100)}%')
            
            file_content.seek(0)
            logger.info(f'Downloaded file: {file_metadata.get("name")}')
            
            return file_content.getvalue(), file_metadata
            
        except Exception as e:
            logger.error(f'Error downloading file: {e}')
            return None, {'error': str(e)}
    
    @staticmethod
    def get_file_preview_url(file_id):
        """
        Get Google Drive preview URL for a file
        
        Args:
            file_id: Google Drive file ID
        
        Returns:
            str: Preview URL
        """
        return f'https://drive.google.com/file/d/{file_id}/preview'
    
    @staticmethod
    def search_files(access_token, search_term, page_size=20):
        """
        Search files in Google Drive
        
        Args:
            access_token: Google OAuth access token
            search_term: Search query
            page_size: Number of results
        
        Returns:
            list of matching files
        """
        try:
            # Build query: search in name and full text
            query = f"name contains '{search_term}' or fullText contains '{search_term}'"
            query += " and trashed=false"
            
            result = GoogleDriveService.list_files(
                access_token=access_token,
                page_size=page_size,
                query=query
            )
            
            return result.get('files', [])
            
        except Exception as e:
            logger.error(f'Error searching files: {e}')
            return []
