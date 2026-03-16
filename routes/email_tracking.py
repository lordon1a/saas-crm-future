"""
Email Tracking Routes - Track email opens and clicks
"""
from flask import Blueprint, request, redirect, send_file
from io import BytesIO
import logging

from services.email_tracking_service import EmailTrackingService

logger = logging.getLogger(__name__)
bp = Blueprint('email_tracking', __name__)


# 1x1 transparent GIF pixel
TRACKING_PIXEL = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00,
    0x01, 0x00, 0x80, 0x00, 0x00, 0xFF, 0xFF, 0xFF,
    0x00, 0x00, 0x00, 0x21, 0xF9, 0x04, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x01, 0x00, 0x00, 0x02, 0x02, 0x44,
    0x01, 0x00, 0x3B
])


@bp.route('/track/open/<tracking_id>', methods=['GET'])
def track_open(tracking_id):
    """
    Track email open via tracking pixel.
    Returns a 1x1 transparent GIF.
    """
    try:
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        EmailTrackingService.record_open(tracking_id, user_agent, ip_address)
        
    except Exception as e:
        logger.error(f'Error tracking email open: {e}')
    
    # Always return pixel, even if tracking fails
    return send_file(
        BytesIO(TRACKING_PIXEL),
        mimetype='image/gif',
        as_attachment=False,
        download_name='pixel.gif'
    )


@bp.route('/track/click/<tracking_id>', methods=['GET'])
def track_click(tracking_id):
    """
    Track link click and redirect to original URL.
    """
    original_url = request.args.get('url', '/')
    
    try:
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        EmailTrackingService.record_click(tracking_id, original_url, user_agent, ip_address)
        
    except Exception as e:
        logger.error(f'Error tracking link click: {e}')
    
    # Redirect to original URL
    return redirect(original_url, code=302)
