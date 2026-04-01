"""
Segment API Routes

Provides endpoints for:
- Listing, creating, updating, deleting segments
- Managing segment memberships
- Syncing dynamic segments
"""
from functools import wraps
from flask import Blueprint, jsonify, request, session

from services.segment_service import SegmentService


segments_bp = Blueprint('segments', __name__, url_prefix='/api/v1/segments')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def write_access_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        role = (session.get('user_role') or '').lower()
        if role in {'read-only', 'readonly'}:
            return jsonify({'success': False, 'error': 'Write permission required'}), 403
        return f(*args, **kwargs)
    return decorated


@segments_bp.route('', methods=['GET'])
@login_required
def list_segments():
    """GET /api/v1/segments - List all segments"""
    workspace_id = session.get('workspace_id')
    segments = SegmentService.list_segments(workspace_id)
    return jsonify({'success': True, 'segments': segments})


@segments_bp.route('', methods=['POST'])
@write_access_required
def create_segment():
    """POST /api/v1/segments - Create a new segment"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    
    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400
    
    try:
        segment = SegmentService.create_segment(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            description=data.get('description'),
            filter_json=data.get('filter_json'),
            is_dynamic=data.get('is_dynamic', True)
        )
        return jsonify({'success': True, 'segment': segment.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@segments_bp.route('/<int:segment_id>', methods=['GET'])
@login_required
def get_segment(segment_id):
    """GET /api/v1/segments/<id> - Get segment details with members"""
    workspace_id = session.get('workspace_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    include_removed = request.args.get('include_removed', 'false').lower() == 'true'
    
    segment = SegmentService.get_segment(segment_id, workspace_id)
    if not segment:
        return jsonify({'success': False, 'error': 'Segment not found'}), 404
    
    members_data = SegmentService.get_segment_members(
        segment_id, workspace_id, page, per_page, include_removed
    )
    
    return jsonify({
        'success': True,
        'segment': segment.to_dict(),
        'members': members_data
    })


@segments_bp.route('/<int:segment_id>', methods=['PATCH'])
@write_access_required
def update_segment(segment_id):
    """PATCH /api/v1/segments/<id> - Update a segment"""
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    
    # Filter allowed fields
    update_data = {}
    for field in ['name', 'description', 'filter_json', 'is_dynamic']:
        if field in data:
            update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'success': False, 'error': 'No fields to update'}), 400
    
    try:
        segment = SegmentService.update_segment(segment_id, workspace_id, **update_data)
        if not segment:
            return jsonify({'success': False, 'error': 'Segment not found'}), 404
        return jsonify({'success': True, 'segment': segment.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@segments_bp.route('/<int:segment_id>', methods=['DELETE'])
@write_access_required
def delete_segment(segment_id):
    """DELETE /api/v1/segments/<id> - Delete a segment"""
    workspace_id = session.get('workspace_id')
    
    success = SegmentService.delete_segment(segment_id, workspace_id)
    if not success:
        return jsonify({'success': False, 'error': 'Segment not found'}), 404
    
    return jsonify({'success': True, 'message': 'Segment deleted'})


@segments_bp.route('/<int:segment_id>/sync', methods=['POST'])
@write_access_required
def sync_segment(segment_id):
    """POST /api/v1/segments/<id>/sync - Manually sync a dynamic segment"""
    workspace_id = session.get('workspace_id')
    
    segment = SegmentService.get_segment(segment_id, workspace_id)
    if not segment:
        return jsonify({'success': False, 'error': 'Segment not found'}), 404
    
    if not segment.is_dynamic:
        return jsonify({'success': False, 'error': 'Manual segments cannot be synced'}), 400
    
    try:
        SegmentService.sync_segment(segment_id)
        segment = SegmentService.get_segment(segment_id, workspace_id)
        return jsonify({'success': True, 'segment': segment.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@segments_bp.route('/<int:segment_id>/members', methods=['POST'])
@write_access_required
def add_member(segment_id):
    """POST /api/v1/segments/<id>/members - Manually add a contact"""
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    
    contact_id = data.get('contact_id')
    if not contact_id:
        return jsonify({'success': False, 'error': 'contact_id is required'}), 400
    
    try:
        membership = SegmentService.add_contact_manually(segment_id, contact_id, workspace_id)
        if not membership:
            return jsonify({'success': False, 'error': 'Segment not found'}), 404
        return jsonify({'success': True, 'membership': membership.to_dict()})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@segments_bp.route('/<int:segment_id>/members/<int:contact_id>', methods=['DELETE'])
@write_access_required
def remove_member(segment_id, contact_id):
    """DELETE /api/v1/segments/<id>/members/<contact_id> - Remove a contact"""
    workspace_id = session.get('workspace_id')
    
    success = SegmentService.remove_contact_manually(segment_id, contact_id, workspace_id)
    if not success:
        return jsonify({'success': False, 'error': 'Membership not found'}), 404
    
    return jsonify({'success': True, 'message': 'Contact removed from segment'})


@segments_bp.route('/<int:segment_id>/members', methods=['GET'])
@login_required
def list_members(segment_id):
    """GET /api/v1/segments/<id>/members - List segment members"""
    workspace_id = session.get('workspace_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    include_removed = request.args.get('include_removed', 'false').lower() == 'true'
    
    segment = SegmentService.get_segment(segment_id, workspace_id)
    if not segment:
        return jsonify({'success': False, 'error': 'Segment not found'}), 404
    
    members = SegmentService.get_segment_members(segment_id, workspace_id, page, per_page, include_removed)
    return jsonify({'success': True, **members})
