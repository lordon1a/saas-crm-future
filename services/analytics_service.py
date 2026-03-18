"""
Analytics Service
Advanced reporting and analytics for CRM data
"""
from models import db
from models_crm import Deal, Contact, Company, Task, Activity, Pipeline, DealStage
from sqlalchemy import func, case
from datetime import datetime, timedelta, UTC
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for generating analytics and reports"""
    
    @staticmethod
    def get_kpi_metrics(workspace_id):
        """
        Get critical KPI metrics
        
        Returns:
            dict: {
                'total_revenue': float,
                'open_opportunities': int,
                'total_contacts': int,
                'total_companies': int,
                'active_tasks': int,
                'completed_tasks_this_month': int
            }
        """
        try:
            # Total revenue from won deals
            total_revenue = db.session.query(
                func.coalesce(func.sum(Deal.value), 0)
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'won'
            ).scalar() or 0
            
            # Open opportunities count
            open_opportunities = Deal.query.filter_by(
                workspace_id=workspace_id,
                is_deleted=False,
                status='open'
            ).count()
            
            # Total contacts
            total_contacts = Contact.query.filter_by(
                workspace_id=workspace_id,
                is_deleted=False,
            ).count()
            
            # Total companies
            total_companies = Company.query.filter_by(
                workspace_id=workspace_id,
                is_deleted=False,
            ).count()
            
            # Active tasks (not completed)
            active_tasks = Task.query.filter(
                Task.workspace_id == workspace_id,
                Task.status != 'completed'
            ).count()
            
            # Completed tasks this month
            start_of_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            completed_tasks_this_month = Task.query.filter(
                Task.workspace_id == workspace_id,
                Task.status == 'completed',
                Task.completed_at >= start_of_month
            ).count()
            
            return {
                'total_revenue': float(total_revenue),
                'open_opportunities': open_opportunities,
                'total_contacts': total_contacts,
                'total_companies': total_companies,
                'active_tasks': active_tasks,
                'completed_tasks_this_month': completed_tasks_this_month
            }
            
        except Exception as e:
            logger.error(f'Failed to get KPI metrics: {e}')
            raise
    
    @staticmethod
    def get_pipeline_distribution(workspace_id):
        """
        Get deal distribution across pipeline stages
        
        Returns:
            dict: {
                'stages': [
                    {
                        'stage_name': str,
                        'deal_count': int,
                        'total_value': float,
                        'probability': float
                    }
                ]
            }
        """
        try:
            # Get all stages with deal counts and values
            results = db.session.query(
                DealStage.name,
                DealStage.probability,
                func.count(Deal.id).label('deal_count'),
                func.coalesce(func.sum(Deal.value), 0).label('total_value')
            ).join(
                Deal, Deal.stage_id == DealStage.id
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'open'
            ).group_by(
                DealStage.id,
                DealStage.name,
                DealStage.probability
            ).order_by(
                DealStage.order
            ).all()
            
            stages = []
            for stage_name, probability, deal_count, total_value in results:
                stages.append({
                    'stage_name': stage_name,
                    'deal_count': deal_count,
                    'total_value': float(total_value),
                    'probability': float(probability) if probability else 0.0,
                    'weighted_value': float(total_value) * (float(probability) if probability else 0.0)
                })
            
            return {'stages': stages}
            
        except Exception as e:
            logger.error(f'Failed to get pipeline distribution: {e}')
            raise
    
    @staticmethod
    def get_win_loss_ratio(workspace_id):
        """
        Get win/loss ratio for closed deals
        
        Returns:
            dict: {
                'won_count': int,
                'lost_count': int,
                'won_value': float,
                'lost_value': float,
                'win_rate': float (percentage)
            }
        """
        try:
            # Count and sum won deals
            won_stats = db.session.query(
                func.count(Deal.id).label('count'),
                func.coalesce(func.sum(Deal.value), 0).label('value')
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'won'
            ).first()
            
            # Count and sum lost deals
            lost_stats = db.session.query(
                func.count(Deal.id).label('count'),
                func.coalesce(func.sum(Deal.value), 0).label('value')
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'lost'
            ).first()
            
            won_count = won_stats.count if won_stats else 0
            lost_count = lost_stats.count if lost_stats else 0
            won_value = float(won_stats.value) if won_stats else 0.0
            lost_value = float(lost_stats.value) if lost_stats else 0.0
            
            # Calculate win rate
            total_closed = won_count + lost_count
            win_rate = (won_count / total_closed * 100) if total_closed > 0 else 0.0
            
            return {
                'won_count': won_count,
                'lost_count': lost_count,
                'won_value': won_value,
                'lost_value': lost_value,
                'win_rate': round(win_rate, 2),
                'total_closed': total_closed
            }
            
        except Exception as e:
            logger.error(f'Failed to get win/loss ratio: {e}')
            raise
    
    @staticmethod
    def get_revenue_trend(workspace_id, days=30):
        """
        Get revenue trend over time
        
        Args:
            workspace_id: Workspace ID
            days: Number of days to look back
            
        Returns:
            dict: {
                'dates': [str],
                'revenue': [float]
            }
        """
        try:
            start_date = datetime.now(UTC) - timedelta(days=days)
            
            # Get deals closed in the period
            deals = Deal.query.filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'won',
                Deal.closed_at >= start_date
            ).order_by(Deal.closed_at).all()
            
            # Group by date
            revenue_by_date = {}
            for deal in deals:
                date_key = deal.closed_at.strftime('%Y-%m-%d')
                if date_key not in revenue_by_date:
                    revenue_by_date[date_key] = 0.0
                revenue_by_date[date_key] += float(deal.value)
            
            # Fill in missing dates with 0
            dates = []
            revenue = []
            current_date = start_date.date()
            end_date = datetime.now(UTC).date()
            
            while current_date <= end_date:
                date_key = current_date.strftime('%Y-%m-%d')
                dates.append(date_key)
                revenue.append(revenue_by_date.get(date_key, 0.0))
                current_date += timedelta(days=1)
            
            return {
                'dates': dates,
                'revenue': revenue
            }
            
        except Exception as e:
            logger.error(f'Failed to get revenue trend: {e}')
            raise
    
    @staticmethod
    def get_top_performers(workspace_id, limit=5):
        """
        Get top performing users by deal value
        
        Returns:
            dict: {
                'performers': [
                    {
                        'user_name': str,
                        'deals_won': int,
                        'total_value': float
                    }
                ]
            }
        """
        try:
            from models import User
            
            results = db.session.query(
                User.name,
                func.count(Deal.id).label('deals_won'),
                func.coalesce(func.sum(Deal.value), 0).label('total_value')
            ).join(
                Deal, Deal.owner_id == User.id
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'won'
            ).group_by(
                User.id,
                User.name
            ).order_by(
                func.sum(Deal.value).desc()
            ).limit(limit).all()
            
            performers = []
            for user_name, deals_won, total_value in results:
                performers.append({
                    'user_name': user_name,
                    'deals_won': deals_won,
                    'total_value': float(total_value)
                })
            
            return {'performers': performers}
            
        except Exception as e:
            logger.error(f'Failed to get top performers: {e}')
            raise
    
    @staticmethod
    def get_task_completion_rate(workspace_id):
        """
        Get task completion statistics
        
        Returns:
            dict: {
                'total_tasks': int,
                'completed_tasks': int,
                'completion_rate': float,
                'overdue_tasks': int
            }
        """
        try:
            total_tasks = Task.query.filter_by(workspace_id=workspace_id).count()
            
            completed_tasks = Task.query.filter_by(
                workspace_id=workspace_id,
                status='completed'
            ).count()
            
            # Overdue tasks (due_date passed and not completed)
            now = datetime.now(UTC)
            overdue_tasks = Task.query.filter(
                Task.workspace_id == workspace_id,
                Task.status != 'completed',
                Task.due_date < now
            ).count()
            
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
            
            return {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round(completion_rate, 2),
                'overdue_tasks': overdue_tasks
            }
            
        except Exception as e:
            logger.error(f'Failed to get task completion rate: {e}')
            raise

    @staticmethod
    def get_sales_cycle_duration(workspace_id, days=90):
        """
        Calculate sales cycle duration metrics for won deals.
        Duration is measured as closed_at - created_at in days.
        """
        try:
            start_date = datetime.now(UTC) - timedelta(days=days)
            deals = Deal.query.filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
                Deal.status == 'won',
                Deal.closed_at.isnot(None),
                Deal.created_at >= start_date
            ).all()

            durations = []
            for deal in deals:
                if deal.closed_at and deal.created_at and deal.closed_at >= deal.created_at:
                    durations.append((deal.closed_at - deal.created_at).days)

            if not durations:
                return {
                    'days_window': days,
                    'total_won_deals': 0,
                    'average_days': 0,
                    'min_days': 0,
                    'max_days': 0,
                }

            return {
                'days_window': days,
                'total_won_deals': len(durations),
                'average_days': round(sum(durations) / len(durations), 2),
                'min_days': min(durations),
                'max_days': max(durations),
            }

        except Exception as e:
            logger.error(f'Failed to calculate sales cycle duration: {e}')
            raise

    @staticmethod
    def get_stage_conversion_rate(workspace_id):
        """
        Calculate stage conversion distribution based on current deal allocation.
        """
        try:
            total_deals = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False).count()
            if total_deals == 0:
                return {'stages': [], 'total_deals': 0}

            rows = db.session.query(
                DealStage.name,
                func.count(Deal.id).label('deal_count')
            ).join(
                Deal, Deal.stage_id == DealStage.id
            ).filter(
                Deal.workspace_id == workspace_id,
                Deal.is_deleted == False,
            ).group_by(
                DealStage.id,
                DealStage.name
            ).order_by(
                DealStage.order
            ).all()

            stages = []
            for stage_name, deal_count in rows:
                rate = (deal_count / total_deals) * 100 if total_deals else 0
                stages.append({
                    'stage_name': stage_name,
                    'deal_count': int(deal_count),
                    'conversion_rate': round(rate, 2),
                })

            return {'stages': stages, 'total_deals': total_deals}

        except Exception as e:
            logger.error(f'Failed to calculate stage conversion rates: {e}')
            raise
