"""
Saved Filter Service
Business logic for managing saved and user-defined filters
"""
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from models import db
from models_crm import SavedFilter, UserDefinedFilter

logger = logging.getLogger(__name__)


class SavedFilterService:
    """Service for managing saved and user-defined filters"""
    
    # In-memory cache for filter results (filter_id -> (results, timestamp))
    _cache = {}
    CACHE_TTL = 300  # 5 minutes in seconds
    
    @staticmethod
    def create_filter(
        workspace_id: int,
        user_id: int,
        name: str,
        entity_type: str,
        filter_config: Dict[str, Any],
        is_shared: bool = False
    ) -> SavedFilter:
        """
        Create a new saved filter.
        
        Args:
            workspace_id: Current workspace ID
            user_id: Current user ID
            name: Filter name
            entity_type: 'contact' or 'company'
            filter_config: Filter configuration dict
            is_shared: Whether filter is shared with workspace
            
        Returns:
            SavedFilter instance
            
        Raises:
            ValueError: If user has reached limit (20 filters per entity type)
        """
        # Check user's filter count (limit: 50 per entity type)
        existing_count = db.session.query(SavedFilter).filter(
            SavedFilter.workspace_id == workspace_id,
            SavedFilter.user_id == user_id,
            SavedFilter.entity_type == entity_type
        ).count()
        
        if existing_count >= 50:
            raise ValueError(f"Maximum 50 saved filters per entity type reached")
        
        # Validate entity type
        if entity_type not in ['contact', 'company']:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        # Create filter
        saved_filter = SavedFilter(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            entity_type=entity_type,
            filter_config=json.dumps(filter_config),
            is_shared=is_shared
        )
        
        try:
            db.session.add(saved_filter)
            db.session.commit()
            logger.info(f"Created saved filter '{name}' for user {user_id}")
            return saved_filter
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create saved filter: {str(e)}")
            raise
    
    @staticmethod
    def get_user_filters(
        workspace_id: int,
        user_id: int,
        entity_type: str
    ) -> List[SavedFilter]:
        """
        Get all filters accessible to user (own + shared).
        
        Args:
            workspace_id: Current workspace ID
            user_id: Current user ID
            entity_type: 'contact' or 'company'
            
        Returns:
            List of SavedFilter instances
        """
        # Get user's own filters + shared filters from other users
        filters = db.session.query(SavedFilter).filter(
            SavedFilter.workspace_id == workspace_id,
            SavedFilter.entity_type == entity_type,
            db.or_(
                SavedFilter.user_id == user_id,
                SavedFilter.is_shared == True
            )
        ).order_by(SavedFilter.created_at.desc()).all()
        
        return filters
    
    @staticmethod
    def delete_filter(filter_id: int, user_id: int, workspace_id: int):
        """
        Delete a saved filter (only if user is creator).
        
        Args:
            filter_id: Filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            
        Raises:
            PermissionError: If user is not the creator
            ValueError: If filter not found
        """
        saved_filter = db.session.query(SavedFilter).filter(
            SavedFilter.id == filter_id,
            SavedFilter.workspace_id == workspace_id
        ).first()
        
        if not saved_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if saved_filter.user_id != user_id:
            raise PermissionError("Only the filter creator can delete this filter")
        
        try:
            # Remove from cache if exists
            if filter_id in SavedFilterService._cache:
                del SavedFilterService._cache[filter_id]
            
            db.session.delete(saved_filter)
            db.session.commit()
            logger.info(f"Deleted saved filter {filter_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete saved filter: {str(e)}")
            raise
    
    @staticmethod
    def share_filter(
        filter_id: int,
        user_id: int,
        workspace_id: int,
        is_shared: bool
    ):
        """
        Share or unshare a filter.
        
        Args:
            filter_id: Filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            is_shared: True to share, False to unshare
            
        Raises:
            PermissionError: If user is not the creator
            ValueError: If filter not found
        """
        saved_filter = db.session.query(SavedFilter).filter(
            SavedFilter.id == filter_id,
            SavedFilter.workspace_id == workspace_id
        ).first()
        
        if not saved_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if saved_filter.user_id != user_id:
            raise PermissionError("Only the filter creator can share/unshare this filter")
        
        try:
            saved_filter.is_shared = is_shared
            saved_filter.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"{'Shared' if is_shared else 'Unshared'} filter {filter_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update filter sharing: {str(e)}")
            raise
    
    @staticmethod
    def get_cached_results(filter_id: int, workspace_id: int) -> Optional[Any]:
        """
        Get cached filter results (5 minute TTL).
        
        Args:
            filter_id: Filter ID
            workspace_id: Current workspace ID
            
        Returns:
            Cached results or None if not cached/expired
        """
        if filter_id not in SavedFilterService._cache:
            return None
        
        cached_data = SavedFilterService._cache[filter_id]
        cached_time = cached_data.get('timestamp')
        
        # Check if cache is expired
        if (datetime.utcnow() - cached_time).total_seconds() > SavedFilterService.CACHE_TTL:
            del SavedFilterService._cache[filter_id]
            return None
        
        # Verify workspace matches
        if cached_data.get('workspace_id') != workspace_id:
            return None
        
        return cached_data.get('results')
    
    @staticmethod
    def set_cached_results(filter_id: int, workspace_id: int, results: Any):
        """
        Cache filter results.
        
        Args:
            filter_id: Filter ID
            workspace_id: Current workspace ID
            results: Results to cache
        """
        SavedFilterService._cache[filter_id] = {
            'results': results,
            'workspace_id': workspace_id,
            'timestamp': datetime.utcnow()
        }
    
    # ============================================================================
    # USER-DEFINED FILTERS (Advanced filters with complex logic)
    # ============================================================================
    
    @staticmethod
    def create_user_defined_filter(
        workspace_id: int,
        user_id: int,
        user_name: str,
        name: str,
        description: Optional[str],
        entity_type: str,
        filter_config: Dict[str, Any],
        is_shared: bool = False
    ) -> UserDefinedFilter:
        """
        Create a new user-defined filter with complex logic.
        
        Args:
            workspace_id: Current workspace ID
            user_id: Current user ID
            user_name: User's name for display
            name: Filter name
            description: Optional description
            entity_type: 'contact' or 'company'
            filter_config: Complex filter configuration dict
            is_shared: Whether filter is shared with workspace
            
        Returns:
            UserDefinedFilter instance
        """
        # Validate entity type
        if entity_type not in ['contact', 'company']:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        # Create filter
        user_filter = UserDefinedFilter(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            description=description,
            entity_type=entity_type,
            filter_config=json.dumps(filter_config),
            is_shared=is_shared,
            created_by_name=user_name
        )
        
        try:
            db.session.add(user_filter)
            db.session.commit()
            logger.info(f"Created user-defined filter '{name}' for user {user_id}")
            return user_filter
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create user-defined filter: {str(e)}")
            raise
    
    @staticmethod
    def get_user_defined_filters(
        workspace_id: int,
        user_id: int,
        entity_type: str
    ) -> List[UserDefinedFilter]:
        """
        Get all user-defined filters accessible to user (own + shared).
        
        Args:
            workspace_id: Current workspace ID
            user_id: Current user ID
            entity_type: 'contact' or 'company'
            
        Returns:
            List of UserDefinedFilter instances
        """
        filters = db.session.query(UserDefinedFilter).filter(
            UserDefinedFilter.workspace_id == workspace_id,
            UserDefinedFilter.entity_type == entity_type,
            db.or_(
                UserDefinedFilter.user_id == user_id,
                UserDefinedFilter.is_shared == True
            )
        ).order_by(UserDefinedFilter.created_at.desc()).all()
        
        return filters
    
    @staticmethod
    def update_user_defined_filter(
        filter_id: int,
        user_id: int,
        workspace_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        filter_config: Optional[Dict[str, Any]] = None
    ) -> UserDefinedFilter:
        """
        Update a user-defined filter.
        
        Args:
            filter_id: Filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            name: New name (optional)
            description: New description (optional)
            filter_config: New filter config (optional)
            
        Returns:
            Updated UserDefinedFilter instance
            
        Raises:
            PermissionError: If user is not the creator
            ValueError: If filter not found
        """
        user_filter = db.session.query(UserDefinedFilter).filter(
            UserDefinedFilter.id == filter_id,
            UserDefinedFilter.workspace_id == workspace_id
        ).first()
        
        if not user_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if user_filter.user_id != user_id:
            raise PermissionError("Only the filter creator can edit this filter")
        
        try:
            if name is not None:
                user_filter.name = name
            if description is not None:
                user_filter.description = description
            if filter_config is not None:
                user_filter.filter_config = json.dumps(filter_config)
            
            user_filter.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"Updated user-defined filter {filter_id}")
            return user_filter
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update user-defined filter: {str(e)}")
            raise
    
    @staticmethod
    def delete_user_defined_filter(filter_id: int, user_id: int, workspace_id: int):
        """
        Delete a user-defined filter (only if user is creator).
        
        Args:
            filter_id: Filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            
        Raises:
            PermissionError: If user is not the creator
            ValueError: If filter not found
        """
        user_filter = db.session.query(UserDefinedFilter).filter(
            UserDefinedFilter.id == filter_id,
            UserDefinedFilter.workspace_id == workspace_id
        ).first()
        
        if not user_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if user_filter.user_id != user_id:
            raise PermissionError("Only the filter creator can delete this filter")
        
        try:
            db.session.delete(user_filter)
            db.session.commit()
            logger.info(f"Deleted user-defined filter {filter_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete user-defined filter: {str(e)}")
            raise

    @staticmethod
    def get_shared_filters(workspace_id: int, entity_type: str) -> List[SavedFilter]:
        """
        Get all shared filters in workspace (excluding user's own).
        
        Args:
            workspace_id: Current workspace ID
            entity_type: 'contact' or 'company'
            
        Returns:
            List of shared SavedFilter instances
        """
        filters = db.session.query(SavedFilter).filter(
            SavedFilter.workspace_id == workspace_id,
            SavedFilter.entity_type == entity_type,
            SavedFilter.is_shared == True
        ).order_by(SavedFilter.updated_at.desc()).all()
        
        return filters
    
    @staticmethod
    def update_filter(
        filter_id: int,
        user_id: int,
        workspace_id: int,
        name: Optional[str] = None,
        filter_config: Optional[Dict[str, Any]] = None,
        is_shared: Optional[bool] = None
    ) -> SavedFilter:
        """
        Update a saved filter (only owner can update).
        
        Args:
            filter_id: Filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            name: New name (optional)
            filter_config: New filter config (optional)
            is_shared: New sharing status (optional)
            
        Returns:
            Updated SavedFilter instance
            
        Raises:
            PermissionError: If user is not the creator
            ValueError: If filter not found
        """
        saved_filter = db.session.query(SavedFilter).filter(
            SavedFilter.id == filter_id,
            SavedFilter.workspace_id == workspace_id
        ).first()
        
        if not saved_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if saved_filter.user_id != user_id:
            raise PermissionError("Only the filter creator can update this filter")
        
        try:
            if name is not None:
                saved_filter.name = name
            
            if filter_config is not None:
                saved_filter.filter_config = json.dumps(filter_config)
            
            if is_shared is not None:
                saved_filter.is_shared = is_shared
            
            saved_filter.updated_at = datetime.utcnow()
            
            # Invalidate cache
            if filter_id in SavedFilterService._cache:
                del SavedFilterService._cache[filter_id]
            
            db.session.commit()
            logger.info(f"Updated saved filter {filter_id}")
            return saved_filter
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update saved filter: {str(e)}")
            raise
    
    @staticmethod
    def duplicate_filter(
        filter_id: int,
        user_id: int,
        workspace_id: int
    ) -> SavedFilter:
        """
        Duplicate a shared filter to user's own filters.
        
        Args:
            filter_id: Original filter ID
            user_id: Current user ID
            workspace_id: Current workspace ID
            
        Returns:
            New SavedFilter instance (duplicate)
            
        Raises:
            ValueError: If filter not found or not shared
        """
        original_filter = db.session.query(SavedFilter).filter(
            SavedFilter.id == filter_id,
            SavedFilter.workspace_id == workspace_id
        ).first()
        
        if not original_filter:
            raise ValueError(f"Filter {filter_id} not found")
        
        if not original_filter.is_shared:
            raise ValueError("Only shared filters can be duplicated")
        
        # Check user's filter count (limit: 50 per entity type)
        existing_count = db.session.query(SavedFilter).filter(
            SavedFilter.workspace_id == workspace_id,
            SavedFilter.user_id == user_id,
            SavedFilter.entity_type == original_filter.entity_type
        ).count()
        
        if existing_count >= 50:
            raise ValueError(f"Maximum 50 saved filters per entity type reached")
        
        # Create duplicate
        duplicate = SavedFilter(
            workspace_id=workspace_id,
            user_id=user_id,
            name=f"{original_filter.name} (Copy)",
            entity_type=original_filter.entity_type,
            filter_config=original_filter.filter_config,
            is_shared=False  # User's copy is not shared by default
        )
        
        try:
            db.session.add(duplicate)
            db.session.commit()
            logger.info(f"Duplicated filter {filter_id} for user {user_id}")
            return duplicate
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to duplicate filter: {str(e)}")
            raise
