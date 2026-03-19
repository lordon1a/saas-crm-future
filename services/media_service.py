"""
Meta WhatsApp medya indirme ve yerel saklama.
Medya URL'si alınır, dosya indirilir, workspace klasörüne kaydedilir.
"""
import os
import re
import uuid
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

# Meta'nın döndüğü content-type'a göre uzantı
EXT_BY_TYPE = {
    'image': '.jpg',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'audio': '.ogg',
    'audio/ogg': '.ogg',
    'audio/mpeg': '.mp3',
    'video': '.mp4',
    'video/mp4': '.mp4',
    'application/pdf': '.pdf',
    'document': '.bin',
}


def _safe_filename(media_type, suggested_ext):
    ext = suggested_ext or EXT_BY_TYPE.get(media_type, '.bin')
    if not ext.startswith('.'):
        ext = '.' + ext
    return f"{uuid.uuid4().hex}{ext}"


def get_media_url_from_meta(media_id, access_token):
    """
    Meta Graph API ile medya ID'sine karşılık gelen indirme URL'sini al.
    """
    url = f"{Config.META_API_BASE_URL}/{media_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get('url')
    except Exception as e:
        logger.warning('Meta medya URL alınamadı %s: %s', media_id, e)
        return None


def download_and_save_media(media_url, access_token, workspace_id, media_type):
    """
    Meta'dan medyayı indir ve uploads/workspace_{id}/ altına kaydet.
    Returns: relative path (workspace_1/xxx.jpg) veya None
    """
    if not media_url or not workspace_id:
        return None
    base = Config.MEDIA_UPLOAD_FOLDER
    folder = os.path.join(base, f"workspace_{workspace_id}")
    os.makedirs(folder, exist_ok=True)
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        r = requests.get(media_url, headers=headers, timeout=30, stream=True)
        r.raise_for_status()
        content_type = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        ext = EXT_BY_TYPE.get(media_type) or EXT_BY_TYPE.get(content_type)
        filename = _safe_filename(media_type, ext)
        filepath = os.path.join(folder, filename)
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        relative = f"workspace_{workspace_id}/{filename}"
        return relative
    except Exception as e:
        logger.exception('Medya indirilemedi %s: %s', media_url[:50], e)
        return None
