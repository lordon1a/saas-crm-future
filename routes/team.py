"""
Team Management Routes
Handles team member invitations, role management, and team operations
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
import logging
from models import db, User, TeamInvitation
from services.team_service import TeamService

logger = logging.getLogger(__name__)

bp = Blueprint('team', __name__, url_prefix='/api/team')


def login_required(f):
    """Decorator to require authentication for endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def owner_or_admin_required(f):
    """Decorator to require owner or admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_role = session.get('user_role')
        if user_role not in ['owner', 'admin']:
            return jsonify({'error': 'Forbidden: Owner or Admin role required'}), 403
        return f(*args, **kwargs)
    return decorated


def owner_required(f):
    """Decorator to require owner role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_role = session.get('user_role')
        if user_role != 'owner':
            return jsonify({'error': 'Forbidden: Owner role required'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# GET /api/team/members - List team members and invitations
# ============================================================================

@bp.route('/members', methods=['GET'])
@login_required
@owner_or_admin_required
def list_members():
    """
    List all team members and pending invitations
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
    """
    try:
        workspace_id = session.get('workspace_id')
        
        # Get team members
        members = TeamService.list_team_members(workspace_id, include_inactive=False)
        
        # Get pending invitations
        invitations = TeamService.list_pending_invitations(workspace_id)
        
        # Serialize members
        members_data = []
        for member in members:
            members_data.append({
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'role': member.role,
                'is_active': member.is_active,
                'last_login': member.last_login.isoformat() if member.last_login else None,
                'created_at': member.created_at.isoformat() if member.created_at else None
            })
        
        # Serialize invitations
        invitations_data = []
        for invitation in invitations:
            invitations_data.append({
                'id': invitation.id,
                'invitee_email': invitation.invitee_email,
                'role': invitation.role,
                'status': invitation.status,
                'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None,
                'created_at': invitation.created_at.isoformat() if invitation.created_at else None,
                'inviter': {
                    'id': invitation.inviter.id,
                    'name': invitation.inviter.name
                } if invitation.inviter else None
            })
        
        return jsonify({
            'members': members_data,
            'invitations': invitations_data
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to list team members: {str(e)}")
        return jsonify({'error': 'Failed to retrieve team members'}), 500


# ============================================================================
# POST /api/team/invite - Send team member invitation
# ============================================================================

@bp.route('/invite', methods=['POST'])
@login_required
@owner_or_admin_required
def invite_member():
    """
    Send a team member invitation
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
    """
    try:
        workspace_id = session.get('workspace_id')
        inviter_id = session.get('user_id')
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        invitee_email = data.get('email', '').strip().lower()
        role = data.get('role', '').strip().lower()
        
        if not invitee_email:
            return jsonify({'error': 'Email is required'}), 400
        
        if not role:
            return jsonify({'error': 'Role is required'}), 400
        
        # Validate role
        if role not in ['admin', 'member', 'viewer']:
            return jsonify({'error': 'Invalid role. Must be admin, member, or viewer'}), 400
        
        # Create invitation
        invitation = TeamService.invite_member(
            workspace_id=workspace_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            role=role
        )
        
        return jsonify({
            'status': 'ok',
            'invitation': {
                'id': invitation.id,
                'invitee_email': invitation.invitee_email,
                'role': invitation.role,
                'status': invitation.status,
                'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None
            }
        }), 201
        
    except ValueError as e:
        logger.warning(f"Invitation validation failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create invitation: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to send invitation'}), 500


# ============================================================================
# POST /api/team/invitations/<id>/cancel - Cancel invitation
# ============================================================================

@bp.route('/invitations/<int:invitation_id>/cancel', methods=['POST'])
@login_required
@owner_or_admin_required
def cancel_invitation(invitation_id):
    """
    Cancel a pending invitation
    
    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        # Cancel invitation
        invitation = TeamService.cancel_invitation(
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            user_id=user_id
        )
        
        return jsonify({
            'status': 'ok',
            'invitation': {
                'id': invitation.id,
                'status': invitation.status
            }
        }), 200
        
    except ValueError as e:
        logger.warning(f"Cancel invitation failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to cancel invitation: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel invitation'}), 500


# ============================================================================
# PUT /api/team/members/<id>/role - Update member role
# ============================================================================

@bp.route('/members/<int:member_id>/role', methods=['PUT'])
@login_required
@owner_required
def update_member_role(member_id):
    """
    Update a team member's role (owner only)
    
    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
    """
    try:
        workspace_id = session.get('workspace_id')
        updated_by = session.get('user_id')
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        new_role = data.get('role', '').strip().lower()
        
        if not new_role:
            return jsonify({'error': 'Role is required'}), 400
        
        # Validate role
        if new_role not in ['admin', 'member', 'viewer']:
            return jsonify({'error': 'Invalid role. Must be admin, member, or viewer'}), 400
        
        # Update role
        user = TeamService.update_member_role(
            workspace_id=workspace_id,
            user_id=member_id,
            new_role=new_role,
            updated_by=updated_by
        )
        
        return jsonify({
            'status': 'ok',
            'member': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        }), 200
        
    except ValueError as e:
        logger.warning(f"Update role failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update member role: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update member role'}), 500


# ============================================================================
# DELETE /api/team/members/<id> - Remove team member
# ============================================================================

@bp.route('/members/<int:member_id>', methods=['DELETE'])
@login_required
@owner_or_admin_required
def remove_member(member_id):
    """
    Remove a team member (soft delete)
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
    """
    try:
        workspace_id = session.get('workspace_id')
        removed_by = session.get('user_id')
        user_role = session.get('user_role')
        
        # Get the member to check their role
        member = User.query.filter_by(
            id=member_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not member:
            return jsonify({'error': 'Member not found'}), 404
        
        # Admin can only remove member and viewer roles
        if user_role == 'admin' and member.role not in ['member', 'viewer']:
            return jsonify({'error': 'Admins can only remove members and viewers'}), 403
        
        # Remove member
        user = TeamService.remove_member(
            workspace_id=workspace_id,
            user_id=member_id,
            removed_by=removed_by
        )
        
        return jsonify({
            'status': 'ok',
            'member': {
                'id': user.id,
                'is_active': user.is_active
            }
        }), 200
        
    except ValueError as e:
        logger.warning(f"Remove member failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to remove member: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to remove member'}), 500


# ============================================================================
# POST /api/team/transfer-ownership - Transfer workspace ownership
# ============================================================================

@bp.route('/transfer-ownership', methods=['POST'])
@login_required
@owner_required
def transfer_ownership():
    """
    Transfer workspace ownership to another admin
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7
    """
    try:
        workspace_id = session.get('workspace_id')
        current_owner_id = session.get('user_id')
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        new_owner_id = data.get('new_owner_id')
        
        if not new_owner_id:
            return jsonify({'error': 'new_owner_id is required'}), 400
        
        # Transfer ownership
        result = TeamService.transfer_ownership(
            workspace_id=workspace_id,
            current_owner_id=current_owner_id,
            new_owner_id=new_owner_id
        )
        
        # Update session with new role
        session['user_role'] = 'admin'
        
        return jsonify({
            'status': 'ok',
            'old_owner': {
                'id': result['old_owner'].id,
                'name': result['old_owner'].name,
                'role': result['old_owner'].role
            },
            'new_owner': {
                'id': result['new_owner'].id,
                'name': result['new_owner'].name,
                'role': result['new_owner'].role
            }
        }), 200
        
    except ValueError as e:
        logger.warning(f"Transfer ownership failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to transfer ownership: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to transfer ownership'}), 500
