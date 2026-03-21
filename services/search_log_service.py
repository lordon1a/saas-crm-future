"""
Search Logging Service
Tracks and analyzes user search behavior
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import func, desc
from models import db
from models_crm import SearchLog


class SearchLogService:
    """Service for managing search logs and analytics"""
    
    @staticmethod
    def log_search(
        workspace_id: int,
        user_id: int,
        search_query: str,
        search_type: str,
        results_count: int = 0,
        entity_type: Optional[str] = None,
        search_duration_ms: Optional[int] = None,
        filters_applied: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> SearchLog:
        """
        Log a search query
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID who performed the search
            search_query: The search query string
            search_type: Type of search ('contact', 'company', 'deal', 'global')
            results_count: Number of results returned
            entity_type: Specific entity type searched (optional)
            search_duration_ms: Search execution time in milliseconds
            filters_applied: JSON string of applied filters
            user_agent: User's browser user agent
            ip_address: User's IP address
            
        Returns:
            SearchLog: Created search log entry
        """
        try:
            log = SearchLog(
                workspace_id=workspace_id,
                user_id=user_id,
                search_query=search_query.strip()[:500],  # Limit length
                search_type=search_type,
                entity_type=entity_type,
                results_count=results_count,
                search_duration_ms=search_duration_ms,
                filters_applied=filters_applied,
                user_agent=user_agent[:500] if user_agent else None,
                ip_address=ip_address
            )
            
            db.session.add(log)
            db.session.commit()
            
            return log
            
        except Exception as e:
            db.session.rollback()
            # Don't fail the main request if logging fails
            print(f"Error logging search: {str(e)}")
            return None
    
    @staticmethod
    def log_click(log_id: int, result_id: int, result_type: str) -> bool:
        """
        Update search log with clicked result
        
        Args:
            log_id: Search log ID
            result_id: ID of the clicked result
            result_type: Type of clicked result ('contact', 'company', 'deal')
            
        Returns:
            bool: Success status
        """
        try:
            log = SearchLog.query.get(log_id)
            if log:
                log.clicked_result_id = result_id
                log.clicked_result_type = result_type
                db.session.commit()
                return True
            return False
            
        except Exception as e:
            db.session.rollback()
            print(f"Error logging click: {str(e)}")
            return False
    
    @staticmethod
    def get_user_history(
        workspace_id: int,
        user_id: int,
        limit: int = 20,
        entity_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get user's search history
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            limit: Maximum number of results
            entity_type: Filter by entity type (optional)
            
        Returns:
            List of search log dictionaries
        """
        query = SearchLog.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id
        )
        
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        
        logs = query.order_by(desc(SearchLog.created_at)).limit(limit).all()
        
        return [log.to_dict() for log in logs]
    
    @staticmethod
    def get_popular_searches(
        workspace_id: int,
        days: int = 7,
        limit: int = 10,
        search_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get most popular search queries
        
        Args:
            workspace_id: Workspace ID
            days: Number of days to look back
            limit: Maximum number of results
            search_type: Filter by search type (optional)
            
        Returns:
            List of popular queries with counts
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.session.query(
            SearchLog.search_query,
            func.count(SearchLog.id).label('search_count'),
            func.avg(SearchLog.results_count).label('avg_results'),
            func.max(SearchLog.created_at).label('last_searched')
        ).filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= cutoff_date
        )
        
        if search_type:
            query = query.filter(SearchLog.search_type == search_type)
        
        results = query.group_by(SearchLog.search_query)\
                      .order_by(desc('search_count'))\
                      .limit(limit)\
                      .all()
        
        return [
            {
                'query': r.search_query,
                'count': r.search_count,
                'avg_results': round(r.avg_results, 1) if r.avg_results else 0,
                'last_searched': r.last_searched.isoformat() if r.last_searched else None
            }
            for r in results
        ]
    
    @staticmethod
    def get_analytics(
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get search analytics for workspace
        
        Args:
            workspace_id: Workspace ID
            start_date: Start date for analytics (default: 30 days ago)
            end_date: End date for analytics (default: now)
            
        Returns:
            Dictionary with analytics data
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Base query
        base_query = SearchLog.query.filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        )
        
        # Total searches
        total_searches = base_query.count()
        
        # Average results per search
        avg_results = db.session.query(
            func.avg(SearchLog.results_count)
        ).filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        ).scalar() or 0
        
        # Searches with no results
        no_result_searches = base_query.filter(
            SearchLog.results_count == 0
        ).count()
        
        # Average search duration
        avg_duration = db.session.query(
            func.avg(SearchLog.search_duration_ms)
        ).filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date,
            SearchLog.search_duration_ms.isnot(None)
        ).scalar() or 0
        
        # Searches by type
        searches_by_type = db.session.query(
            SearchLog.search_type,
            func.count(SearchLog.id).label('count')
        ).filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        ).group_by(SearchLog.search_type).all()
        
        # Top queries with no results
        no_result_queries = db.session.query(
            SearchLog.search_query,
            func.count(SearchLog.id).label('count')
        ).filter(
            SearchLog.workspace_id == workspace_id,
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date,
            SearchLog.results_count == 0
        ).group_by(SearchLog.search_query)\
         .order_by(desc('count'))\
         .limit(10)\
         .all()
        
        return {
            'total_searches': total_searches,
            'avg_results_per_search': round(avg_results, 1),
            'no_result_searches': no_result_searches,
            'no_result_percentage': round((no_result_searches / total_searches * 100) if total_searches > 0 else 0, 1),
            'avg_search_duration_ms': round(avg_duration, 0),
            'searches_by_type': {r.search_type: r.count for r in searches_by_type},
            'top_no_result_queries': [
                {'query': r.search_query, 'count': r.count}
                for r in no_result_queries
            ],
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
