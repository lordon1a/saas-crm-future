"""
Team Service
Business logic for team member management, invitations, and role-based access control
"""
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import and_, or_
from models import db, User, TeamInvitation, Workspace
from services.email_hub_service import EmailHubService

logger = logging.getLogger(__name__)


class TeamService:
    """Service for managing team members and invitations"""
    
    # Valid roles for team members
    VALID_ROLES = ['owner', 'admin', 'member', 'viewer']
    INVITATION_EXPIRY_DAYS = 7
    
    # ============================================================================
    # INVITATION OPERATIONS
    # ============================================================================
    
    @staticmethod
    def invite_member(workspace_id: int, inviter_id: int, invitee_email: str, 
                     role: str) -> TeamInvitation:
        """
        Create and send a team member invitation.
        
        Args:
            workspace_id: Workspace ID
            inviter_id: User ID of the person sending the invitation
            invitee_email: Email address of the invitee
            role: Role to assign (admin, member, viewer)
        
        Returns:
            TeamInvitation: Created invitation instance
        
        Raises:
            ValueError: If validation fails
        """
        # Validate email format
        if not TeamService._validate_email(invitee_email):
            raise ValueError("Invalid email format")
        
        invitee_email = invitee_email.strip().lower()
        
        # Validate role (owner cannot be invited, must be created)
        if role not in ['admin', 'member', 'viewer']:
            raise ValueError(f"Invalid role: {role}. Must be admin, member, or viewer")
        
        # Check if user already exists in workspace
        existing_user = User.query.filter_by(
            workspace_id=workspace_id,
            email=invitee_email,
            is_active=True
        ).first()
        
        if existing_user:
            raise ValueError("User already exists in this workspace")
        
        # Check for existing pending invitation
        existing_invitation = TeamInvitation.query.filter_by(
            workspace_id=workspace_id,
            invitee_email=invitee_email,
            status='pending'
        ).first()
        
        if existing_invitation:
            raise ValueError("Pending invitation already exists for this email")
        
        # Generate unique token and expiration
        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=TeamService.INVITATION_EXPIRY_DAYS)
        
        # Create invitation
        invitation = TeamInvitation(
            workspace_id=workspace_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            role=role,
            token=token,
            status='pending',
            expires_at=expires_at
        )
        
        db.session.add(invitation)
        
        try:
            db.session.flush()
            
            # Send invitation email
            TeamService._send_invitation_email(invitation)
            
            db.session.commit()
            logger.info(f"Created invitation {invitation.id} for {invitee_email} to workspace {workspace_id}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create invitation: {str(e)}")
            raise e
        
        return invitation
    
    @staticmethod
    def accept_invitation(token: str, name: str, password_hash: str) -> User:
        """
        Accept a team member invitation and create user account.
        
        Args:
            token: Invitation token
            name: User's full name
            password_hash: Hashed password
        
        Returns:
            User: Created user instance
        
        Raises:
            ValueError: If invitation is invalid or expired
        """
        # Find invitation by token
        invitation = TeamInvitation.query.filter_by(token=token).first()
        
        if not invitation:
            raise ValueError("Invalid invitation token")
        
        # Check invitation status
        if invitation.status != 'pending':
            raise ValueError(f"Invitation is {invitation.status}, cannot accept")
        
        # Check expiration
        if invitation.expires_at < datetime.utcnow():
            invitation.status = 'expired'
            db.session.commit()
            raise ValueError("Invitation has expired")
        
        # Create user
        user = User(
            workspace_id=invitation.workspace_id,
            name=name,
            email=invitation.invitee_email,
            password_hash=password_hash,
            role=invitation.role,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        
        # Update invitation status
        invitation.status = 'accepted'
        invitation.accepted_at = datetime.utcnow()
        
        try:
            db.session.commit()
            logger.info(f"User {user.id} accepted invitation {invitation.id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to accept invitation: {str(e)}")
            raise e
        
        return user
    
    @staticmethod
    def cancel_invitation(workspace_id: int, invitation_id: int, user_id: int) -> TeamInvitation:
        """
        Cancel a pending invitation.
        
        Args:
            workspace_id: Workspace ID
            invitation_id: Invitation ID to cancel
            user_id: User ID performing the cancellation
        
        Returns:
            TeamInvitation: Updated invitation
        
        Raises:
            ValueError: If invitation cannot be cancelled
        """
        invitation = TeamInvitation.query.filter_by(
            id=invitation_id,
            workspace_id=workspace_id
        ).first()
        
        if not invitation:
            raise ValueError("Invitation not found")
        
        if invitation.status != 'pending':
            raise ValueError(f"Cannot cancel invitation with status: {invitation.status}")
        
        invitation.status = 'cancelled'
        
        try:
            db.session.commit()
            logger.info(f"Cancelled invitation {invitation_id} by user {user_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cancel invitation: {str(e)}")
            raise e
        
        return invitation
    
    @staticmethod
    def list_pending_invitations(workspace_id: int) -> List[TeamInvitation]:
        """
        Get all pending invitations for a workspace.
        
        Args:
            workspace_id: Workspace ID
        
        Returns:
            List[TeamInvitation]: List of pending invitations
        """
        invitations = TeamInvitation.query.filter_by(
            workspace_id=workspace_id,
            status='pending'
        ).order_by(TeamInvitation.created_at.desc()).all()
        
        return invitations
    
    # ============================================================================
    # TEAM MEMBER OPERATIONS
    # ============================================================================
    
    @staticmethod
    def list_team_members(workspace_id: int, include_inactive: bool = False) -> List[User]:
        """
        Get all team members in a workspace.
        
        Args:
            workspace_id: Workspace ID
            include_inactive: Whether to include deactivated members
        
        Returns:
            List[User]: List of team members sorted by role then name
        """
        query = User.query.filter_by(workspace_id=workspace_id)
        
        if not include_inactive:
            query = query.filter_by(is_active=True)
        
        # Custom sort: owner first, then admin, member, viewer, then by name
        members = query.all()
        
        role_order = {'owner': 0, 'admin': 1, 'member': 2, 'viewer': 3}
        members.sort(key=lambda u: (role_order.get(u.role, 99), u.name.lower()))
        
        return members
    
    @staticmethod
    def update_member_role(workspace_id: int, user_id: int, new_role: str, 
                          updated_by: int) -> User:
        """
        Update a team member's role.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID to update
            new_role: New role (admin, member, viewer)
            updated_by: User ID performing the update
        
        Returns:
            User: Updated user instance
        
        Raises:
            ValueError: If role update is invalid
        """
        # Validate new role
        if new_role not in ['admin', 'member', 'viewer']:
            raise ValueError(f"Invalid role: {new_role}")
        
        # Get user to update
        user = User.query.filter_by(
            id=user_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not user:
            raise ValueError("User not found in workspace")
        
        # Cannot change owner role
        if user.role == 'owner':
            raise ValueError("Cannot change the role of workspace owner")
        
        old_role = user.role
        user.role = new_role
        
        try:
            db.session.commit()
            logger.info(f"Updated user {user_id} role from {old_role} to {new_role} by user {updated_by}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update member role: {str(e)}")
            raise e
        
        return user
    
    @staticmethod
    def remove_member(workspace_id: int, user_id: int, removed_by: int) -> User:
        """
        Remove (soft delete) a team member from workspace.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID to remove
            removed_by: User ID performing the removal
        
        Returns:
            User: Updated user instance
        
        Raises:
            ValueError: If removal is invalid
        """
        user = User.query.filter_by(
            id=user_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not user:
            raise ValueError("User not found in workspace")
        
        # Cannot remove owner
        if user.role == 'owner':
            raise ValueError("Cannot remove workspace owner")
        
        user.is_active = False
        user.deleted_at = datetime.utcnow()
        
        try:
            db.session.commit()
            logger.info(f"Removed user {user_id} from workspace {workspace_id} by user {removed_by}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to remove member: {str(e)}")
            raise e
        
        return user
    
    @staticmethod
    def transfer_ownership(workspace_id: int, current_owner_id: int, 
                          new_owner_id: int) -> Dict[str, User]:
        """
        Transfer workspace ownership to another admin.
        
        Args:
            workspace_id: Workspace ID
            current_owner_id: Current owner's user ID
            new_owner_id: New owner's user ID (must be admin)
        
        Returns:
            Dict with 'old_owner' and 'new_owner' User instances
        
        Raises:
            ValueError: If transfer is invalid
        """
        # Get current owner
        current_owner = User.query.filter_by(
            id=current_owner_id,
            workspace_id=workspace_id,
            role='owner',
            is_active=True
        ).first()
        
        if not current_owner:
            raise ValueError("Current owner not found or invalid")
        
        # Get new owner (must be admin)
        new_owner = User.query.filter_by(
            id=new_owner_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not new_owner:
            raise ValueError("New owner not found in workspace")
        
        if new_owner.role != 'admin':
            raise ValueError("New owner must have admin role")
        
        # Swap roles
        current_owner.role = 'admin'
        new_owner.role = 'owner'
        
        try:
            db.session.commit()
            logger.info(f"Transferred ownership from user {current_owner_id} to {new_owner_id} in workspace {workspace_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to transfer ownership: {str(e)}")
            raise e
        
        return {
            'old_owner': current_owner,
            'new_owner': new_owner
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email format using regex."""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None
    
    @staticmethod
    def _send_invitation_email(invitation: TeamInvitation) -> None:
        """
        Send invitation email to invitee.
        
        Args:
            invitation: TeamInvitation instance
        """
        try:
            # Get workspace and inviter details
            workspace = Workspace.query.get(invitation.workspace_id)
            inviter = User.query.get(invitation.inviter_id)
            
            if not workspace or not inviter:
                logger.error(f"Cannot send invitation email: workspace or inviter not found")
                return
            
            # Build invitation URL (assuming app is deployed)
            # TODO: Get base URL from config
            invitation_url = f"https://your-app-url.com/accept-invitation?token={invitation.token}"
            
            # Email subject
            subject = f"You're invited to join {workspace.company_name} on WhatsApp CRM"
            
            # Plain text body
            body_text = f"""
Hello,

{inviter.name} has invited you to join {workspace.company_name} as a {invitation.role}.

Click the link below to accept the invitation:
{invitation_url}

This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %H:%M UTC')}.

If you did not expect this invitation, you can safely ignore this email.

Best regards,
WhatsApp CRM Team
"""
            
            # HTML body
            body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; background-color: #f9fafb; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Team Invitation</h1>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p><strong>{inviter.name}</strong> has invited you to join <strong>{workspace.company_name}</strong> as a <strong>{invitation.role}</strong>.</p>
            <p>Click the button below to accept the invitation:</p>
            <p style="text-align: center;">
                <a href="{invitation_url}" class="button">Accept Invitation</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #4F46E5;">{invitation_url}</p>
            <p><strong>This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %H:%M UTC')}.</strong></p>
            <p>If you did not expect this invitation, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>WhatsApp CRM Team</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email using EmailHubService
            EmailHubService.queue_outbound_email(
                workspace_id=invitation.workspace_id,
                user_id=invitation.inviter_id,
                to_email=invitation.invitee_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html
            )
            
            logger.info(f"Sent invitation email to {invitation.invitee_email}")
            
        except Exception as e:
            # Log error but don't fail the invitation creation
            logger.error(f"Failed to send invitation email: {str(e)}")
