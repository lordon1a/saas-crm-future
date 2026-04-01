"""
Contact Management Routes
API endpoints for companies and contacts
"""
from flask import Blueprint, request, jsonify, session, make_response, send_from_directory
from functools import wraps
from services.contact_service import ContactService
from services.collaboration_service import CollaborationService
import logging
import os
import json
import shutil
import time
from datetime import datetime
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
MAX_CONTACT_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _format_file_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.2f} KB"

contacts_bp = Blueprint('contacts', __name__)


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# COMPANY ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/companies', methods=['GET'])
@login_required
def get_companies():
    """Get all companies with optional filters and pagination"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        # Validate authentication
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Check for advanced filtering parameters
        filters_json = request.args.get('filters')
        quick_filter = request.args.get('quick_filter')
        sort_by = request.args.get('sort_by', 'display_order')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Legacy filter parameters (for backward compatibility)
        legacy_filters = {}
        if request.args.get('industry'):
            legacy_filters['industry'] = request.args.get('industry')
        if request.args.get('size'):
            legacy_filters['size'] = request.args.get('size')
        if request.args.get('search'):
            legacy_filters['search'] = request.args.get('search')
        # Add assigned_to filter
        if request.args.get('assigned_to'):
            assigned_to_value = request.args.get('assigned_to')
            if assigned_to_value == 'unassigned':
                legacy_filters['assigned_to'] = 'unassigned'
            elif assigned_to_value != 'all':
                try:
                    legacy_filters['assigned_to'] = int(assigned_to_value)
                except (TypeError, ValueError):
                    return jsonify({'error': 'Geçersiz assigned_to parametresi'}), 400
        
        from models_crm import Company
        from models import db
        from services.filter_service import FilterService
        from services.filter_validation_service import FilterValidationService
        from services.filter_cache_service import FilterCacheService
        from utils.rate_limiter import get_rate_limit_status
        
        # Use FilterService if advanced filters are provided
        if filters_json or quick_filter:
            try:
                # Check rate limit
                current_count, max_count, window_seconds = get_rate_limit_status(user_id)
                if current_count >= max_count:
                    return jsonify({
                        'error': f'Rate limit exceeded. Maximum {max_count} concurrent filter requests allowed. Please wait and try again.',
                        'retry_after': window_seconds
                    }), 429
                
                # Parse filters JSON
                filter_config = None
                if filters_json:
                    import json
                    try:
                        filter_config = json.loads(filters_json)
                    except json.JSONDecodeError as e:
                        return jsonify({'error': f'Invalid JSON in filters parameter: {str(e)}'}), 400
                elif quick_filter:
                    # Evaluate quick filter
                    try:
                        filter_config = FilterService.evaluate_quick_filter(quick_filter, 'company')
                    except ValueError as e:
                        return jsonify({'error': str(e)}), 400
                
                # Validate workspace access
                if not FilterValidationService.check_workspace_access(workspace_id, user_id):
                    logger.warning(f"Workspace access violation: user {user_id} attempted to access workspace {workspace_id}")
                    return jsonify({'error': 'Access denied to this workspace'}), 403
                
                # Check cache first
                cache_key = FilterCacheService.generate_cache_key('company', filter_config, workspace_id)
                cached_results = FilterCacheService.get_cached_results(cache_key)
                
                if cached_results:
                    cached_data, cached_pagination = cached_results
                    logger.info(f"Cache hit for company filters: {cache_key}")
                    
                    return jsonify({
                        'companies': cached_data,
                        'pagination': cached_pagination,
                        'applied_filters': filter_config,
                        'cached': True
                    }), 200
                
                # Apply filters using FilterService
                results, pagination_info = FilterService.apply_filters(
                    entity_type='company',
                    workspace_id=workspace_id,
                    user_id=user_id,
                    filters=filter_config,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
                
                # Build result
                result = []
                for c in results:
                    result.append({
                        'id': c.id,
                        'name': c.name,
                        'industry': c.industry,
                        'size': c.size,
                        'website': c.website,
                        'phone': c.phone,
                        'address': c.address,
                        'parent_company_id': c.parent_company_id,
                        'parent_company_name': c.parent_company.name if c.parent_company else None,
                        'created_at': c.created_at.isoformat() if c.created_at else None,
                        'updated_at': c.updated_at.isoformat() if c.updated_at else None
                    })
                
                # Cache the results
                FilterCacheService.set_cached_results(
                    cache_key=cache_key,
                    results=result,
                    pagination=pagination_info,
                    ttl=FilterCacheService.DEFAULT_TTL,
                    entity_type='company',
                    workspace_id=workspace_id
                )
                
                return jsonify({
                    'companies': result,
                    'pagination': pagination_info,
                    'applied_filters': filter_config
                }), 200
                
            except ValueError as e:
                logger.warning(f"Filter validation error: {str(e)}")
                return jsonify({'error': str(e)}), 400
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error: {str(e)}")
                return jsonify({'error': f'Invalid JSON format: {str(e)}'}), 400
            except Exception as e:
                logger.error(f"Error applying filters: {str(e)}", exc_info=True)
                return jsonify({'error': 'Internal server error while applying filters'}), 500
        
        # Legacy filtering (backward compatibility)
        query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        # Apply legacy filters
        if legacy_filters.get('industry'):
            query = query.filter_by(industry=legacy_filters['industry'])
        if legacy_filters.get('size'):
            query = query.filter_by(size=legacy_filters['size'])
        if legacy_filters.get('search'):
            search_term = f"%{legacy_filters['search']}%"
            query = query.filter(
                db.or_(
                    Company.name.ilike(search_term),
                    Company.website.ilike(search_term),
                    Company.phone.ilike(search_term)
                )
            )
        # Apply assigned_to filter
        if legacy_filters.get('assigned_to') == 'unassigned':
            query = query.filter(Company.assigned_to == None)
        elif legacy_filters.get('assigned_to'):
            query = query.filter(Company.assigned_to == legacy_filters['assigned_to'])
        
        # Eager load parent company
        query = query.options(db.joinedload(Company.parent_company))
        
        # Paginate with display_order sorting
        pagination = query.order_by(Company.display_order, Company.name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'companies': [
                {
                    'id': c.id,
                    'name': c.name,
                    'industry': c.industry,
                    'size': c.size,
                    'website': c.website,
                    'phone': c.phone,
                    'address': c.address,
                    'parent_company_id': c.parent_company_id,
                    'parent_company_name': c.parent_company.name if c.parent_company else None,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                }
                for c in pagination.items
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting companies: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>', methods=['GET'])
@login_required
def get_company(company_id):
    """Get a single company by ID"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Company
        from models import User
        
        company = Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, company, 'read'):
            logger.warning(f"Access denied: user {user_id} attempted to read company {company_id}")
            return jsonify({'error': 'Access denied to this company'}), 403
        
        # Get custom fields
        custom_fields = ContactService.get_custom_field_values(
            workspace_id, 'company', company_id
        )
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'parent_company_name': company.parent_company.name if company.parent_company else None,
            'custom_fields': custom_fields,
            'created_at': company.created_at.isoformat() if company.created_at else None,
            'updated_at': company.updated_at.isoformat() if company.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting company: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies', methods=['POST'])
@login_required
def create_company():
    """Create a new company"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company = ContactService.create_company(workspace_id, data, user_id)
        
        # Invalidate filter cache for companies
        try:
            from services.filter_cache_service import FilterCacheService
            FilterCacheService.invalidate_cache('company', workspace_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate filter cache: {str(e)}")
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'created_at': company.created_at.isoformat() if company.created_at else None
        }), 201
        
    except LookupError:
        return jsonify({'error': 'Kayıt bulunamadı'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>', methods=['PATCH'])
@login_required
def update_company(company_id):
    """Update a company"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Company
        from models import User
        
        # Get company first to check access
        company = Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, company, 'write'):
            logger.warning(f"Access denied: user {user_id} attempted to update company {company_id}")
            return jsonify({'error': 'Access denied to this company'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company = ContactService.update_company(workspace_id, company_id, data, user_id)
        
        # Invalidate filter cache for companies
        try:
            from services.filter_cache_service import FilterCacheService
            FilterCacheService.invalidate_cache('company', workspace_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate filter cache: {str(e)}")
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'updated_at': company.updated_at.isoformat() if company.updated_at else None
        }), 200
        
    except LookupError:
        return jsonify({'error': 'Kayıt bulunamadı'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating company: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>', methods=['DELETE'])
@login_required
def delete_company(company_id):
    """Soft delete a company"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from models_crm import Company
        from models import db, User

        company = Company.query.filter_by(id=company_id, workspace_id=workspace_id, is_deleted=False).first()
        if not company:
            return jsonify({'error': 'Company not found'}), 404

        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, company, 'delete'):
            logger.warning(f"Access denied: user {user_id} attempted to delete company {company_id}")
            return jsonify({'error': 'Access denied to this company'}), 403

        try:
            company.is_deleted = True
            company.deleted_at = datetime.utcnow()
            db.session.commit()
            
            # Invalidate filter cache for companies
            try:
                from services.filter_cache_service import FilterCacheService
                FilterCacheService.invalidate_cache('company', workspace_id)
            except Exception as e:
                logger.warning(f"Failed to invalidate filter cache: {str(e)}")
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error deleting company: {str(db_error)}")
            return jsonify({'error': 'Internal Server Error'}), 500

        return jsonify({'message': 'Kayıt başarıyla silindi (çöp kutusuna taşındı)'}), 200

    except Exception as e:
        logger.error(f"Error deleting company: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>/restore', methods=['POST'])
@login_required
def restore_company(company_id):
    """Restore a soft deleted company"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from models_crm import Company
        from models import db

        company = Company.query.filter_by(id=company_id, workspace_id=workspace_id, is_deleted=True).first()
        if not company:
            return jsonify({'error': 'Company not found'}), 404

        try:
            company.is_deleted = False
            company.deleted_at = None
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error restoring company: {str(db_error)}")
            return jsonify({'error': 'Internal Server Error'}), 500

        return jsonify({'message': 'Kayıt başarıyla geri yüklendi'}), 200

    except Exception as e:
        logger.error(f"Error restoring company: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# CONTACT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts', methods=['GET'])
@login_required
def get_contacts():
    """Get all contacts with optional filters and pagination - includes both CRM Contacts and Customers"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        # Validate authentication
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Check for advanced filtering parameters
        filters_json = request.args.get('filters')
        quick_filter = request.args.get('quick_filter')
        sort_by = request.args.get('sort_by', 'display_order')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Legacy filter parameters (for backward compatibility)
        legacy_filters = {}
        if request.args.get('company_id'):
            try:
                legacy_filters['company_id'] = int(request.args.get('company_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('role'):
            legacy_filters['role'] = request.args.get('role')
        if request.args.get('search'):
            legacy_filters['search'] = request.args.get('search')
        if request.args.get('limit'):
            try:
                per_page = min(int(request.args.get('limit')), 100)
            except (TypeError, ValueError):
                pass
        # Add assigned_to filter
        if request.args.get('assigned_to'):
            assigned_to_value = request.args.get('assigned_to')
            if assigned_to_value == 'unassigned':
                legacy_filters['assigned_to'] = 'unassigned'
            elif assigned_to_value != 'all':
                try:
                    legacy_filters['assigned_to'] = int(assigned_to_value)
                except (TypeError, ValueError):
                    return jsonify({'error': 'Geçersiz assigned_to parametresi'}), 400
        
        from models_crm import Contact, Deal, Company
        from models import db, Customer
        from sqlalchemy import func
        from services.filter_service import FilterService
        from services.filter_validation_service import FilterValidationService
        from services.filter_cache_service import FilterCacheService
        from utils.rate_limiter import filter_rate_limit, get_rate_limit_status
        
        # Use FilterService if advanced filters are provided
        if filters_json or quick_filter:
            try:
                # Check rate limit
                current_count, max_count, window_seconds = get_rate_limit_status(user_id)
                if current_count >= max_count:
                    return jsonify({
                        'error': f'Rate limit exceeded. Maximum {max_count} concurrent filter requests allowed. Please wait and try again.',
                        'retry_after': window_seconds
                    }), 429
                
                # Parse filters JSON
                filter_config = None
                if filters_json:
                    import json
                    try:
                        filter_config = json.loads(filters_json)
                    except json.JSONDecodeError as e:
                        return jsonify({'error': f'Invalid JSON in filters parameter: {str(e)}'}), 400
                elif quick_filter:
                    # Evaluate quick filter
                    try:
                        filter_config = FilterService.evaluate_quick_filter(quick_filter, 'contact')
                    except ValueError as e:
                        return jsonify({'error': str(e)}), 400
                
                # Validate workspace access
                if not FilterValidationService.check_workspace_access(workspace_id, user_id):
                    logger.warning(f"Workspace access violation: user {user_id} attempted to access workspace {workspace_id}")
                    return jsonify({'error': 'Access denied to this workspace'}), 403
                
                # Apply filters using FilterService (handles caching internally with page-aware cache keys)
                results, pagination_info = FilterService.apply_filters(
                    entity_type='contact',
                    workspace_id=workspace_id,
                    user_id=user_id,
                    filters=filter_config,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
                
                # Load custom field values for results
                contact_ids = [c.id for c in results]
                company_ids = [c.company_id for c in results if c.company_id]
                custom_field_values_map = {}
                open_deals_count_map = {}
                
                if contact_ids:
                    from services.custom_field_service import CustomFieldService
                    for contact_id in contact_ids:
                        try:
                            values = CustomFieldService.get_values('contact', contact_id, workspace_id)
                            custom_field_values_map[contact_id] = values
                        except:
                            custom_field_values_map[contact_id] = {}

                    # Count open deals per company
                    if company_ids:
                        open_deals_counts = db.session.query(
                            Deal.company_id,
                            func.count(Deal.id)
                        ).filter(
                            Deal.workspace_id == workspace_id,
                            Deal.company_id.in_(company_ids),
                            Deal.is_deleted == False,
                            Deal.status == 'open'
                        ).group_by(Deal.company_id).all()

                        open_deals_count_map = {
                            company_id: deal_count for company_id, deal_count in open_deals_counts
                        }
                
                # Build result
                result = []
                for c in results:
                    result.append({
                        'id': c.id,
                        'first_name': c.first_name,
                        'last_name': c.last_name,
                        'full_name': c.full_name,
                        'email': c.email,
                        'phone': c.phone,
                        'whatsapp_phone': c.whatsapp_phone,
                        'role': c.role,
                        'job_title': c.job_title,
                        'lead_score': c.lead_score,
                        'company_id': c.company_id,
                        'company_name': c.company.name if c.company else None,
                        'open_deals_count': open_deals_count_map.get(c.company_id, 0) if c.company_id else 0,
                        'customFieldValues': custom_field_values_map.get(c.id, {}),
                        'is_starred': c.is_starred,
                        'tags': [t.to_dict() for t in c.tags] if hasattr(c, 'tags') and c.tags else [],
                        'last_activity_at': c.last_activity_at.isoformat() if c.last_activity_at else None,
                        'lifecycle_stage': c.lifecycle_stage,
                        'created_at': c.created_at.isoformat() if c.created_at else None,
                        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                        'source': 'crm'
                    })
                
                # Note: Caching is handled by FilterService.apply_filters internally
                
                return jsonify({
                    'contacts': result,
                    'pagination': pagination_info,
                    'applied_filters': filter_config
                }), 200
                
            except ValueError as e:
                logger.warning(f"Filter validation error: {str(e)}")
                return jsonify({'error': str(e)}), 400
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error: {str(e)}")
                return jsonify({'error': f'Invalid JSON format: {str(e)}'}), 400
            except Exception as e:
                logger.error(f"Error applying filters: {str(e)}", exc_info=True)
                return jsonify({'error': 'Internal server error while applying filters'}), 500
        
        # Legacy filtering (backward compatibility)
        offset = (page - 1) * per_page
        
        # Get CRM Contacts
        query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        # Build applied_filters for legacy mode
        applied_filters = {'filters': [], 'legacy_mode': True}
        
        # Apply legacy filters
        if legacy_filters.get('company_id'):
            query = query.filter_by(company_id=legacy_filters['company_id'])
            applied_filters['filters'].append({
                'field': 'company_id',
                'operator': 'equals',
                'value': legacy_filters['company_id']
            })
        if legacy_filters.get('role'):
            query = query.filter_by(role=legacy_filters['role'])
            applied_filters['filters'].append({
                'field': 'role',
                'operator': 'equals',
                'value': legacy_filters['role']
            })
        if legacy_filters.get('assigned_to'):
            if legacy_filters['assigned_to'] == 'unassigned':
                query = query.filter(Contact.assigned_to.is_(None))
                applied_filters['filters'].append({
                    'field': 'assigned_to',
                    'operator': 'is_null',
                    'value': None
                })
            else:
                query = query.filter_by(assigned_to=legacy_filters['assigned_to'])
                applied_filters['filters'].append({
                    'field': 'assigned_to',
                    'operator': 'equals',
                    'value': legacy_filters['assigned_to']
                })
        if legacy_filters.get('search'):
            search_term = f"%{legacy_filters['search']}%"
            query = query.outerjoin(Company, Contact.company_id == Company.id).filter(
                db.or_(
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.phone.ilike(search_term),
                    Contact.whatsapp_phone.ilike(search_term),
                    Contact.job_title.ilike(search_term),
                    Company.name.ilike(search_term)
                )
            )
            applied_filters['filters'].append({
                'field': 'search',
                'operator': 'contains',
                'value': legacy_filters['search']
            })
        
        # Eager load company
        query = query.options(db.joinedload(Contact.company))
        
        # Get total count BEFORE pagination
        total = query.count()
        
        # Get CRM contacts with pagination, ordered by starred first, then display_order
        crm_contacts = query.order_by(Contact.is_starred.desc(), Contact.display_order, Contact.first_name, Contact.last_name).offset(offset).limit(per_page).all()
        
        # Also get Customers that are NOT linked to CRM Contacts (for Telegram/WhatsApp users)
        customer_query = Customer.query.filter_by(workspace_id=workspace_id)
        
        # Exclude customers that are already linked to CRM contacts
        linked_customer_ids = db.session.query(Contact.customer_id).filter(
            Contact.workspace_id == workspace_id,
            Contact.customer_id.isnot(None)
        ).all()
        linked_customer_ids = [cid[0] for cid in linked_customer_ids]
        
        if linked_customer_ids:
            customer_query = customer_query.filter(~Customer.id.in_(linked_customer_ids))
        
        if legacy_filters.get('search'):
            search_term = f"%{legacy_filters['search']}%"
            customer_query = customer_query.filter(
                db.or_(
                    Customer.profile_name.ilike(search_term),
                    Customer.phone_number.ilike(search_term),
                    Customer.email.ilike(search_term)
                )
            )
        
        # Get customers (limit to remaining slots)
        remaining_slots = per_page - len(crm_contacts)
        customers = customer_query.order_by(Customer.profile_name).limit(max(remaining_slots, 0)).all() if remaining_slots > 0 else []
        
        # Load custom field values for CRM contacts
        contact_ids = [c.id for c in crm_contacts]
        company_ids = [c.company_id for c in crm_contacts if c.company_id]
        custom_field_values_map = {}
        open_deals_count_map = {}
        
        if contact_ids:
            from services.custom_field_service import CustomFieldService
            for contact_id in contact_ids:
                try:
                    values = CustomFieldService.get_values('contact', contact_id, workspace_id)
                    custom_field_values_map[contact_id] = values
                except:
                    custom_field_values_map[contact_id] = {}

            # Count open deals per company
            if company_ids:
                open_deals_counts = db.session.query(
                    Deal.company_id,
                    func.count(Deal.id)
                ).filter(
                    Deal.workspace_id == workspace_id,
                    Deal.company_id.in_(company_ids),
                    Deal.is_deleted == False,
                    Deal.status == 'open'
                ).group_by(Deal.company_id).all()

                open_deals_count_map = {
                    company_id: deal_count for company_id, deal_count in open_deals_counts
                }
        
        # Build result combining CRM contacts and customers
        result = []
        
        # Add CRM contacts
        for c in crm_contacts:
            result.append({
                'id': c.id,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'full_name': c.full_name,
                'email': c.email,
                'phone': c.phone,
                'whatsapp_phone': c.whatsapp_phone,
                'role': c.role,
                'job_title': c.job_title,
                'lead_score': c.lead_score,
                'company_id': c.company_id,
                'company_name': c.company.name if c.company else None,
                'open_deals_count': open_deals_count_map.get(c.company_id, 0) if c.company_id else 0,
                'customFieldValues': custom_field_values_map.get(c.id, {}),
                'is_starred': c.is_starred,
                'tags': [t.to_dict() for t in c.tags] if hasattr(c, 'tags') and c.tags else [],
                'last_activity_at': c.last_activity_at.isoformat() if c.last_activity_at else None,
                'lifecycle_stage': c.lifecycle_stage,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'source': 'crm'
            })
        
        # Add customers (Telegram/WhatsApp users not yet in CRM)
        for customer in customers:
            result.append({
                'id': customer.id,
                'first_name': customer.profile_name or 'Unknown',
                'last_name': '',
                'full_name': customer.profile_name or 'Unknown',
                'email': customer.email,
                'phone': customer.phone_number,
                'whatsapp_phone': customer.phone_number,
                'role': None,
                'job_title': customer.job_title,
                'lead_score': 0,
                'company_id': None,
                'company_name': customer.company,
                'open_deals_count': 0,
                'customFieldValues': {},
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'updated_at': None,
                'source': 'customer',
                'customer_id': customer.id
            })
        
        # Calculate pagination info
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'contacts': result,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'applied_filters': applied_filters if applied_filters['filters'] else None
        }), 200
        
    except Exception as e:
        import traceback
        from flask import current_app
        error_details = traceback.format_exc()
        logger.error(f"Error getting contacts: {str(e)}\n{error_details}")
        # Return detailed error in development
        if current_app.config.get('DEBUG'):
            return jsonify({'error': 'Internal Server Error', 'details': str(e), 'traceback': error_details}), 500
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['GET'])
@login_required
def get_contact(contact_id):
    """Get a single contact by ID"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import User
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, contact, 'read'):
            logger.warning(f"Access denied: user {user_id} attempted to read contact {contact_id}")
            return jsonify({'error': 'Access denied to this contact'}), 403
        
        # Get custom fields
        custom_fields = ContactService.get_custom_field_values(
            workspace_id, 'contact', contact_id
        )
        
        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'lead_source': contact.lead_source,
            'lifecycle_stage': contact.lifecycle_stage,
            'company_id': contact.company_id,
            'company_name': contact.company.name if contact.company else None,
            'custom_fields': custom_fields,
            'tags': [t.to_dict() for t in contact.tags] if hasattr(contact, 'tags') and contact.tags else [],
            'last_activity_at': contact.last_activity_at.isoformat() if contact.last_activity_at else None,
            'is_starred': contact.is_starred,
            'assigned_to': contact.assigned_to,
            'customer_id': contact.customer_id,
            'created_at': contact.created_at.isoformat() if contact.created_at else None,
            'updated_at': contact.updated_at.isoformat() if contact.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/segments', methods=['GET'])
@login_required
def get_contact_segments(contact_id):
    """Get all current segments for a contact."""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from models_crm import Contact
        from services.segment_service import SegmentService

        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        segments = SegmentService.get_contact_segments(contact_id, workspace_id)
        return jsonify({'success': True, 'segments': segments}), 200

    except Exception as e:
        logger.error(f"Error getting contact segments: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/companies/<int:company_id>')
@login_required
def view_company_page(company_id):
    """View company detail page"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return redirect('/login')

        from models_crm import Company
        from flask import render_template, redirect

        company = Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()

        if not company:
            return "Company not found", 404

        return render_template('company_detail.html', company=company)

    except Exception as e:
        logger.error(f"Error viewing company: {str(e)}")
        return str(e), 500


@contacts_bp.route('/api/companies/<int:company_id>/timeline', methods=['GET'])
@login_required
def get_company_timeline(company_id):
    """Get notes timeline for a company."""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
        except (TypeError, ValueError):
            return jsonify({'error': 'Geçersiz parametre'}), 400

        page = max(1, page)
        per_page = min(max(1, per_page), 100)

        from models_crm import Company
        from models_contact_timeline import CompanyNote

        company = Company.query.filter_by(
            id=company_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not company:
            return jsonify({'error': 'Company not found'}), 404

        notes_page = CompanyNote.query.filter_by(
            company_id=company_id, workspace_id=workspace_id
        ).order_by(CompanyNote.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        timeline = [n.to_dict() for n in notes_page.items]
        return jsonify({
            'data': timeline,
            'meta': {
                'current_page': page,
                'total_pages': notes_page.pages or 1,
                'has_next': notes_page.has_next
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting company timeline: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/companies/<int:company_id>/notes', methods=['POST'])
@login_required
def create_company_note(company_id):
    """Create a note for a company."""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        data = request.get_json() or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'error': 'Not içeriği boş olamaz'}), 400

        from models_crm import Company
        from models_contact_timeline import CompanyNote

        company = Company.query.filter_by(
            id=company_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not company:
            return jsonify({'error': 'Company not found'}), 404

        note = CompanyNote(
            workspace_id=workspace_id,
            company_id=company_id,
            user_id=user_id,
            content=content,
        )
        try:
            db.session.add(note)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return jsonify(note.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating company note: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/contacts/<int:contact_id>')
@login_required
def view_contact_page(contact_id):
    """View contact detail page"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return redirect('/login')
        
        from models_crm import Contact
        from flask import render_template, redirect
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return "Contact not found", 404
        
        return render_template('contact_detail.html', contact=contact)
        
    except Exception as e:
        logger.error(f"Error viewing contact: {str(e)}")
        return str(e), 500


# ============================================================================
# CONTACT TIMELINE API (Enterprise Grade)
# ============================================================================

@contacts_bp.route('/api/contacts/<int:contact_id>/timeline', methods=['GET'])
@login_required
def get_contact_timeline(contact_id):
    """
    Get unified timeline for contact (notes + activity logs).
    Returns merged and sorted by created_at DESC.
    """
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
        except (TypeError, ValueError):
            return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400

        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 20
        per_page = min(per_page, 100)
        
        from models_crm import Contact
        from models_contact_timeline import ContactNote, ContactActivityLog
        
        # Verify contact exists and belongs to workspace
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get notes
        notes_pagination = ContactNote.query.filter_by(
            contact_id=contact_id,
            workspace_id=workspace_id
        ).order_by(ContactNote.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Get activity logs
        activities_pagination = ContactActivityLog.query.filter_by(
            contact_id=contact_id,
            workspace_id=workspace_id
        ).order_by(ContactActivityLog.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Merge and sort
        timeline = []
        timeline.extend([note.to_dict() for note in notes_pagination.items])
        timeline.extend([activity.to_dict() for activity in activities_pagination.items])
        
        # Sort by created_at descending
        timeline.sort(key=lambda x: x['created_at'], reverse=True)
        timeline = timeline[:per_page]

        total_pages = max(notes_pagination.pages, activities_pagination.pages, 1)
        has_next = notes_pagination.has_next or activities_pagination.has_next
        
        return jsonify({
            'data': timeline,
            'meta': {
                'current_page': page,
                'total_pages': total_pages,
                'has_next': has_next
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact timeline: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/notes', methods=['POST'])
@login_required
def create_contact_note(contact_id):
    """
    Create a new note for contact.
    Uses transaction with rollback on error.
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models_contact_timeline import ContactNote
        from models import db
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        data = request.get_json()
        if not data or not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'error': 'Content cannot be empty'}), 400
        
        # Create note with transaction
        try:
            note = ContactNote(
                workspace_id=workspace_id,
                contact_id=contact_id,
                user_id=user_id,
                content=content
            )
            
            db.session.add(note)
            db.session.commit()
            
            # Return created note
            return jsonify(note.to_dict()), 201
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error creating note: {str(db_error)}")
            return jsonify({'error': 'Failed to create note'}), 500
        
    except Exception as e:
        logger.error(f"Error creating contact note: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/activities', methods=['POST'])
@login_required
def create_contact_activity(contact_id):
    """Create a new activity for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models_contact_timeline import ContactActivityLog
        from models import db
        import json
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        data = request.get_json()
        action_type = data.get('action_type', 'activity')
        description = data.get('description', '').strip()
        metadata = data.get('metadata', {})
        
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        
        try:
            activity = ContactActivityLog(
                workspace_id=workspace_id,
                contact_id=contact_id,
                user_id=user_id,
                action_type=action_type,
                description=description,
                metadata_json=json.dumps(metadata) if metadata else None
            )
            
            db.session.add(activity)
            db.session.commit()
            
            return jsonify(activity.to_dict()), 201
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error creating activity: {str(db_error)}")
            return jsonify({'error': 'Failed to create activity'}), 500
        
    except Exception as e:
        logger.error(f"Error creating contact activity: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files', methods=['GET'])
@login_required
def get_contact_files(contact_id):
    """Get files for contact"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get files from upload directory
        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        files = []

        if os.path.exists(upload_dir):
            for filename in os.listdir(upload_dir):
                filepath = os.path.join(upload_dir, filename)
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    file_mtime = os.path.getmtime(filepath)

                    # Hide generated timestamp prefix in UI
                    display_name = filename
                    if '_' in filename:
                        parts = filename.split('_', 1)
                        if len(parts) > 1:
                            display_name = parts[1]

                    files.append({
                        'name': display_name,
                        'stored_name': filename,
                        'download_url': f"/api/contacts/{contact_id}/files/download/{filename}",
                        'path': filepath,
                        'size': _format_file_size(file_size),
                        'uploaded_at': datetime.fromtimestamp(file_mtime).strftime('%d.%m.%Y %H:%M')
                    })

        return jsonify({
            'files': files,
            'total': len(files)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact files: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/files/upload', methods=['POST'])
@login_required
def upload_contact_files():
    """Upload files for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        contact_id = request.form.get('contact_id')
        if not contact_id:
            return jsonify({'error': 'Contact ID is required'}), 400
        
        from models_crm import Contact
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=int(contact_id),
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Check if files are in request
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')

        # Validate all file sizes before saving anything
        for file in files:
            if not file.filename:
                continue
            file.stream.seek(0, os.SEEK_END)
            file_size = file.stream.tell()
            file.stream.seek(0)
            if file_size > MAX_CONTACT_FILE_SIZE:
                return jsonify({'error': f"'{file.filename}' dosyasi 50MB sinirini asiyor"}), 413
        
        from models import db
        from models_contact_timeline import ContactActivityLog

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        os.makedirs(upload_dir, exist_ok=True)

        uploaded_files = []
        for file in files:
            if not file.filename:
                continue

            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(upload_dir, unique_filename)

            file.save(filepath)
            file_size = os.path.getsize(filepath)

            uploaded_files.append({
                'name': filename,
                'stored_name': unique_filename,
                'path': filepath,
                'size': _format_file_size(file_size),
                'uploaded_at': datetime.now().strftime('%d.%m.%Y %H:%M')
            })

        if not uploaded_files:
            return jsonify({'error': 'No valid files to upload'}), 400

        try:
            activity = ContactActivityLog(
                workspace_id=workspace_id,
                contact_id=int(contact_id),
                user_id=user_id,
                action_type='file_upload',
                description=f'{len(uploaded_files)} dosya yüklendi',
                metadata_json=json.dumps({'files': [f['name'] for f in uploaded_files]})
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while creating file upload activity: {str(db_error)}")
            return jsonify({'error': 'Files uploaded but activity log creation failed'}), 500

        return jsonify({
            'uploaded': len(uploaded_files),
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} files uploaded successfully'
        }), 200
        
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error uploading files: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files', methods=['DELETE'])
@login_required
def delete_contact_file(contact_id):
    """Delete a file for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')

        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        from models_crm import Contact
        from models import db
        from models_contact_timeline import ContactActivityLog
        import json

        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        payload = request.get_json(silent=True) or {}
        stored_name = (payload.get('stored_name') or '').strip()
        if not stored_name:
            return jsonify({'error': 'stored_name zorunludur'}), 400

        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        file_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name
        os.remove(file_path)

        activity = ContactActivityLog(
            workspace_id=workspace_id,
            contact_id=contact_id,
            user_id=user_id,
            action_type='file_delete',
            description='1 dosya silindi',
            metadata_json=json.dumps({'file': display_name})
        )
        db.session.add(activity)
        try:
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while creating file delete activity: {str(db_error)}")
            return jsonify({'error': 'Dosya silindi ancak aktivite kaydi olusturulamadi'}), 500

        return jsonify({'status': 'deleted', 'file': display_name}), 200

    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error deleting contact file: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files/download/<path:stored_name>', methods=['GET'])
@login_required
def download_contact_file(contact_id, stored_name):
    """Download a file belonging to a contact in current workspace."""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        from models_crm import Contact
        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id, is_deleted=False).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        file_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name
        return send_from_directory(upload_dir, stored_name, as_attachment=True, download_name=display_name)

    except Exception as e:
        logger.error(f"Error downloading contact file: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files/share-to-chat', methods=['POST'])
@login_required
def share_contact_file_to_chat(contact_id):
    """Share a contact file into the linked Telegram chat conversation."""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        payload = request.get_json(silent=True) or {}
        stored_name = (payload.get('stored_name') or '').strip()
        caption = (payload.get('caption') or '').strip()
        channel = (payload.get('channel') or 'telegram').strip().lower()

        if channel != 'telegram':
            return jsonify({'error': 'Su anda sadece Telegram destekleniyor'}), 400

        if not stored_name:
            return jsonify({'error': 'stored_name zorunludur'}), 400
        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        from models_crm import Contact
        from models import db, Workspace
        from services.conversation_manager import ConversationManager
        from services.message_manager import MessageManager
        from services.telegram_service import TelegramService
        from realtime import emit_chat_message_event

        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id, is_deleted=False).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        if not contact.customer_id:
            return jsonify({'error': 'Bu kisiye bagli aktif chat bulunamadi'}), 400

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        source_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(source_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name

        conversation = ConversationManager.get_or_create_conversation(workspace_id, contact.customer_id)
        workspace = Workspace.query.get(workspace_id)
        if not workspace or not workspace.telegram_bot_token:
            return jsonify({'error': 'Telegram kanali yapilandirilmamis'}), 400

        telegram_chat_id = contact.telegram_chat_id
        if not telegram_chat_id and conversation.customer:
            telegram_chat_id = conversation.customer.telegram_chat_id
        if not telegram_chat_id:
            return jsonify({'error': 'Bu kisi icin telegram_chat_id bulunamadi'}), 400

        media_root = os.path.abspath(os.path.join('uploads', f'workspace_{workspace_id}'))
        os.makedirs(media_root, exist_ok=True)

        safe_original = secure_filename(display_name) or 'document.pdf'
        safe_name = secure_filename(f"{time.time_ns()}_{contact_id}_{safe_original}")[:220]
        if not safe_name:
            safe_name = f"{time.time_ns()}_{contact_id}_document.pdf"

        shared_path = os.path.join(media_root, safe_name)
        shutil.copy2(source_path, shared_path)

        relative_path = f"workspace_{workspace_id}/{safe_name}"
        telegram_service = TelegramService(workspace.telegram_bot_token)
        result = telegram_service.send_document(
            chat_id=telegram_chat_id,
            file_path=shared_path,
            caption=caption or None,
            filename=display_name,
        )

        if not result.get('success'):
            try:
                if os.path.exists(shared_path):
                    os.remove(shared_path)
            except Exception:
                pass
            return jsonify({'error': result.get('error', 'Dosya Telegram sohbetinde paylasilamadi')}), 500

        body_label = f"[📄 Telegram Belge] {display_name}"
        if caption:
            body_label += f" - {caption}"

        try:
            message = MessageManager.save_outgoing_message(
                conversation_id=conversation.id,
                message_body=body_label,
                sender_id=user_id,
                meta_message_id=result.get('message_id'),
                channel='telegram',
                media_type='document',
                media_url=relative_path,
            )
            message.is_read = True
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while saving shared file message: {str(db_error)}")
            return jsonify({'error': 'Dosya gonderildi ancak chat kaydi olusturulamadi'}), 500

        try:
            ConversationManager.update_last_message_time(conversation.id)
        except Exception as conv_error:
            logger.warning(f"Conversation timestamp update warning: {str(conv_error)}")

        try:
            emit_chat_message_event(message.id, workspace_id=workspace_id)
        except Exception as emit_error:
            logger.warning(f"Realtime emit warning: {str(emit_error)}")

        return jsonify({
            'status': 'sent',
            'channel': 'telegram',
            'conversation_id': conversation.id,
            'conversation_public_id': conversation.public_id,
            'message_id': message.id,
            'message': {
                'id': message.id,
                'conversation_id': conversation.id,
                'message_body': message.message_body,
                'media_type': message.media_type,
                'media_url': f"/api/media/{message.media_url}",
                'created_at': message.created_at.isoformat(),
            },
        }), 200

    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error sharing contact file to chat: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts', methods=['POST'])
@login_required
def create_contact():
    """Create a new contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact = ContactService.create_contact(workspace_id, data, user_id)
        
        # Calculate lead score
        lead_score = ContactService.calculate_lead_score(contact)
        contact.lead_score = lead_score
        from models import db
        db.session.commit()
        
        # Invalidate filter cache for contacts
        try:
            from services.filter_cache_service import FilterCacheService
            FilterCacheService.invalidate_cache('contact', workspace_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate filter cache: {str(e)}")

        try:
            from services.webhook_service import WebhookService
            WebhookService.dispatch_event(workspace_id, 'contact.created', {
                'contact_id': contact.id,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'full_name': contact.full_name,
                'email': contact.email,
                'phone': contact.phone,
                'company_id': contact.company_id,
                'created_at': contact.created_at.isoformat() if contact.created_at else None,
            })
        except Exception as exc:
            logger.warning('Webhook dispatch failed for contact.created: %s', exc)
        
        # Trigger workflow automation for contact_created
        try:
            from services.workflow_service import WorkflowService
            WorkflowService.trigger_event(
                workspace_id=workspace_id,
                trigger_type='contact_created',
                entity_type='contact',
                entity_id=contact.id
            )
        except Exception as e:
            logger.error(f"Workflow trigger error for contact_created: {e}")
        
        # Mark onboarding step as complete
        from services.onboarding_service import OnboardingService
        OnboardingService.complete_step(workspace_id, 'first_contact_added')
        
        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'company_id': contact.company_id,
            'created_at': contact.created_at.isoformat() if contact.created_at else None
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['PATCH'])
@login_required
def update_contact(contact_id):
    """Update a contact"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import User
        
        # Get contact first to check access
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, contact, 'write'):
            logger.warning(f"Access denied: user {user_id} attempted to update contact {contact_id}")
            return jsonify({'error': 'Access denied to this contact'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact = ContactService.update_contact(workspace_id, contact_id, data, user_id)
        
        # Recalculate lead score
        lead_score = ContactService.calculate_lead_score(contact)
        contact.lead_score = lead_score
        from models import db
        db.session.commit()
        
        # Invalidate filter cache for contacts
        try:
            from services.filter_cache_service import FilterCacheService
            FilterCacheService.invalidate_cache('contact', workspace_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate filter cache: {str(e)}")

        CollaborationService.notify_followers_on_entity_change(
            workspace_id=workspace_id,
            entity_type='contact',
            entity_id=contact.id,
            message=f'Takip ettiginiz kisi guncellendi: {contact.full_name}',
        )

        # Trigger workflow automation for contact_updated
        try:
            from services.workflow_service import WorkflowService
            WorkflowService.trigger_event(
                workspace_id=workspace_id,
                trigger_type='contact_updated',
                entity_type='contact',
                entity_id=contact.id
            )
        except Exception as e:
            logger.error(f"Workflow trigger error for contact_updated: {e}")

        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'company_id': contact.company_id,
            'updated_at': contact.updated_at.isoformat() if contact.updated_at else None
        }), 200
        
    except LookupError:
        return jsonify({'error': 'Kayıt bulunamadı'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    """Soft delete a contact"""
    from utils.permissions import check_entity_access
    
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import db, User
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        current_user = User.query.get(user_id)
        if not check_entity_access(current_user, contact, 'delete'):
            logger.warning(f"Access denied: user {user_id} attempted to delete contact {contact_id}")
            return jsonify({'error': 'Access denied to this contact'}), 403
        
        try:
            contact.is_deleted = True
            contact.deleted_at = datetime.utcnow()
            db.session.commit()
            
            # Invalidate filter cache for contacts
            try:
                from services.filter_cache_service import FilterCacheService
                FilterCacheService.invalidate_cache('contact', workspace_id)
            except Exception as e:
                logger.warning(f"Failed to invalidate filter cache: {str(e)}")
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error deleting contact: {str(db_error)}")
            return jsonify({'error': 'Internal Server Error'}), 500

        return jsonify({'message': 'Kayıt başarıyla silindi (çöp kutusuna taşındı)'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/restore', methods=['POST'])
@login_required
def restore_contact(contact_id):
    """Restore a soft deleted contact"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from models_crm import Contact
        from models import db

        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id, is_deleted=True).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        try:
            contact.is_deleted = False
            contact.deleted_at = None
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error restoring contact: {str(db_error)}")
            return jsonify({'error': 'Internal Server Error'}), 500

        return jsonify({'message': 'Kayıt başarıyla geri yüklendi'}), 200

    except Exception as e:
        logger.error(f"Error restoring contact: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# CSV IMPORT/EXPORT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/export', methods=['GET', 'POST'])
@login_required
def export_contacts():
    """Export contacts to CSV or Excel (supports both simple GET and advanced POST with filters)"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Handle POST request with advanced filtering
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Get parameters
            filters = data.get('filters', {})
            export_format = data.get('format', 'csv').lower()
            columns = data.get('columns', [
                'first_name', 'last_name', 'email', 'phone', 
                'whatsapp_phone', 'role', 'job_title', 'lead_score', 
                'company_name', 'is_starred', 'created_at', 'updated_at'
            ])
            
            # Validate format
            if export_format not in ['csv', 'xlsx']:
                return jsonify({'error': 'Invalid format. Must be csv or xlsx'}), 400
            
            from services.filter_service import FilterService
            
            # Apply filters without pagination (max 10,000 records)
            try:
                results, pagination_info = FilterService.apply_filters(
                    entity_type='contact',
                    workspace_id=workspace_id,
                    user_id=user_id,
                    filters=filters,
                    page=1,
                    per_page=10000,
                    sort_by='created_at',
                    sort_order='desc'
                )
                
                # Check result count limit
                if pagination_info['total'] > 10000:
                    return jsonify({
                        'error': f'Too many records to export ({pagination_info["total"]}). Maximum is 10,000. Please apply more filters.'
                    }), 400
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y-%m-%d')
                filename = f'contacts_filtered_{timestamp}.{export_format}'
                
                # Export based on format
                if export_format == 'csv':
                    csv_data = FilterService.export_to_csv(results, columns, 'contact')
                    
                    response = make_response(csv_data)
                    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
                    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                    return response
                    
                else:  # xlsx
                    excel_data = FilterService.export_to_excel(results, columns, 'contact')
                    
                    response = make_response(excel_data)
                    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                    return response
                    
            except Exception as e:
                logger.error(f"Error applying filters for export: {str(e)}")
                return jsonify({'error': f'Filter error: {str(e)}'}), 500
        
        # Handle GET request (simple export - backward compatibility)
        else:
            filters = {}
            if request.args.get('company_id'):
                try:
                    filters['company_id'] = int(request.args.get('company_id'))
                except (TypeError, ValueError):
                    return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
            if request.args.get('role'):
                filters['role'] = request.args.get('role')
            if request.args.get('search'):
                filters['search'] = request.args.get('search')
            
            csv_content = ContactService.export_contacts_csv(workspace_id, filters)
            
            response = make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=contacts.csv'
            
            return response
        
    except Exception as e:
        logger.error(f"Error exporting contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/import', methods=['POST'])
@login_required
def import_contacts():
    """Import contacts from CSV"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Read CSV content
        csv_content = file.read().decode('utf-8')
        
        # Import contacts
        logger.info(f"Import request - workspace_id: {workspace_id}, user_id: {user_id}")
        created_count, skipped_count, errors = ContactService.import_contacts_csv(
            workspace_id, csv_content, user_id
        )
        
        return jsonify({
            'created': created_count,
            'skipped': skipped_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        logger.error(f"Error importing contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/export', methods=['GET', 'POST'])
@login_required
def export_companies():
    """Export companies to CSV or Excel (supports both simple GET and advanced POST with filters)"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Handle POST request with advanced filtering
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Get parameters
            filters = data.get('filters', {})
            export_format = data.get('format', 'csv').lower()
            columns = data.get('columns', [
                'name', 'industry', 'size', 'website', 'phone', 
                'address', 'parent_company_name', 'created_at', 'updated_at'
            ])
            
            # Validate format
            if export_format not in ['csv', 'xlsx']:
                return jsonify({'error': 'Invalid format. Must be csv or xlsx'}), 400
            
            from services.filter_service import FilterService
            
            # Apply filters without pagination (max 10,000 records)
            try:
                results, pagination_info = FilterService.apply_filters(
                    entity_type='company',
                    workspace_id=workspace_id,
                    user_id=user_id,
                    filters=filters,
                    page=1,
                    per_page=10000,
                    sort_by='created_at',
                    sort_order='desc'
                )
                
                # Check result count limit
                if pagination_info['total'] > 10000:
                    return jsonify({
                        'error': f'Too many records to export ({pagination_info["total"]}). Maximum is 10,000. Please apply more filters.'
                    }), 400
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y-%m-%d')
                filename = f'companies_filtered_{timestamp}.{export_format}'
                
                # Export based on format
                if export_format == 'csv':
                    csv_data = FilterService.export_to_csv(results, columns, 'company')
                    
                    response = make_response(csv_data)
                    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
                    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                    return response
                    
                else:  # xlsx
                    excel_data = FilterService.export_to_excel(results, columns, 'company')
                    
                    response = make_response(excel_data)
                    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                    return response
                    
            except Exception as e:
                logger.error(f"Error applying filters for export: {str(e)}")
                return jsonify({'error': f'Filter error: {str(e)}'}), 500
        
        # Handle GET request (simple export - backward compatibility)
        else:
            filters = {}
            if request.args.get('industry'):
                filters['industry'] = request.args.get('industry')
            if request.args.get('size'):
                filters['size'] = request.args.get('size')
            if request.args.get('search'):
                filters['search'] = request.args.get('search')
            
            csv_content = ContactService.export_companies_csv(workspace_id, filters)
            
            response = make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=companies.csv'
            
            return response
        
    except Exception as e:
        logger.error(f"Error exporting companies: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/bulk-update', methods=['POST'])
@login_required
def bulk_update_contacts():
    """Bulk update multiple contacts"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact_ids = data.get('contact_ids', [])
        updates = data.get('updates', {})
        
        if not contact_ids:
            return jsonify({'error': 'No contact IDs provided'}), 400
        
        if not updates:
            return jsonify({'error': 'No updates provided'}), 400
        
        # Validate contact IDs belong to workspace
        from models_crm import Contact
        from models import db
        
        contacts = Contact.query.filter(
            Contact.id.in_(contact_ids),
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
        ).all()
        
        if len(contacts) != len(contact_ids):
            return jsonify({'error': 'Some contacts not found'}), 404
        
        # Update each contact
        updated_count = 0
        ALLOWED_UPDATE_FIELDS = {'first_name', 'last_name', 'email', 'phone', 'company_id'}
        for contact in contacts:
            try:
                # Apply updates
                for field, value in updates.items():
                    if field in ALLOWED_UPDATE_FIELDS:
                        setattr(contact, field, value)
                
                # Recalculate lead score if relevant fields changed
                if any(f in updates for f in ['email', 'phone', 'role', 'company_id']):
                    contact.lead_score = ContactService.calculate_lead_score(contact)
                
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating contact {contact.id}: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'updated': updated_count,
            'total': len(contact_ids)
        }), 200
        
    except Exception as e:
        logger.error(f"Error bulk updating contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_contacts():
    """Bulk delete multiple contacts"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact_ids = data.get('contact_ids', [])
        
        if not contact_ids:
            return jsonify({'error': 'No contact IDs provided'}), 400
        
        # Hard delete contacts
        from models_crm import Contact
        from models import db
        
        deleted_count = db.session.query(Contact).filter(
            Contact.id.in_(contact_ids),
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
        ).delete(synchronize_session=False)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        
        return jsonify({
            'deleted': deleted_count,
            'total': len(contact_ids)
        }), 200
        
    except Exception as e:
        logger.error(f"Error bulk deleting contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/bulk-delete-all', methods=['POST'])
@login_required
def bulk_delete_all_contacts():
    """Delete ALL contacts in workspace (dangerous operation)"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import db
        
        count = Contact.query.filter_by(
            workspace_id=workspace_id,
            is_deleted=False
        ).count()
        
        # Önce soft delete yap (foreign key sorununu önler)
        Contact.query.filter_by(
            workspace_id=workspace_id,
            is_deleted=False
        ).update({
            'is_deleted': True,
            'deleted_at': datetime.utcnow()
        }, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'deleted_count': count,
            'message': f'{count} kişi başarıyla silindi'
        }), 200
        
    except Exception as e:
        import traceback
        logger.error(f"bulk_delete_all error: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/companies/bulk-delete-all', methods=['POST'])
@login_required
def bulk_delete_all_companies():
    """Delete ALL companies in workspace (dangerous operation)"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Company
        from models import db
        
        # Hard delete all non-deleted companies
        deleted_count = db.session.query(Company).filter(
            Company.workspace_id == workspace_id,
            Company.is_deleted == False,
        ).delete(synchronize_session=False)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        
        return jsonify({
            'deleted_count': deleted_count,
            'message': f'{deleted_count} şirket başarıyla silindi'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting all companies: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# USER PREFERENCES
# ============================================================================

@contacts_bp.route('/api/v1/user-preferences/contacts-columns', methods=['GET'])
@login_required
def get_contacts_column_preferences():
    """Get user's column preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        # Try to get from database
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'columns': json.loads(result[0])}), 200
        
        # Return default columns
        default_columns = [
            'name', 'company', 'email', 'phone', 'role', 'lead_score', 'deals'
        ]
        
        return jsonify({'columns': default_columns}), 200
        
    except Exception as e:
        logger.error(f"Error getting column preferences: {str(e)}")
        # Return defaults on error
        return jsonify({'columns': ['name', 'company', 'email', 'phone', 'role', 'lead_score', 'deals']}), 200


@contacts_bp.route('/api/v1/user-preferences/contacts-columns', methods=['POST'])
@login_required
def save_contacts_column_preferences():
    """Save user's column preferences for contacts table"""
    user_id = session.get('user_id')
    workspace_id = session.get('workspace_id')
    
    logger.info(f"Saving column preferences for user {user_id}, workspace {workspace_id}")
    
    if not user_id or not workspace_id:
        logger.error("User or workspace not found in session")
        return jsonify({'error': 'User or workspace not found'}), 400
    
    data = request.get_json()
    if not data or 'columns' not in data:
        logger.error(f"Invalid data received: {data}")
        return jsonify({'error': 'No columns provided'}), 400
    
    columns = data['columns']
    logger.info(f"Columns to save: {columns}")
    
    from models import db
    from sqlalchemy import text
    import json
    
    try:
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            logger.info(f"Updating existing preference (id: {result[0]})")
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
                {'value': json.dumps(columns), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            logger.info("Creating new preference")
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'contacts_visible_columns', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(columns)}
            )
        
        db.session.commit()
        logger.info("Column preferences saved successfully")
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving column preferences: {str(e)}", exc_info=True)
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500


@contacts_bp.route('/api/v1/user-preferences/contacts-column-widths', methods=['GET'])
@login_required
def get_contacts_column_widths():
    """Get user's column width preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'widths': json.loads(result[0])}), 200
        
        return jsonify({'widths': {}}), 200
        
    except Exception as e:
        logger.error(f"Error getting column widths: {str(e)}")
        return jsonify({'widths': {}}), 200


@contacts_bp.route('/api/v1/user-preferences/contacts-column-widths', methods=['POST'])
@login_required
def save_contacts_column_widths():
    """Save user's column width preferences for contacts table"""
    user_id = session.get('user_id')
    workspace_id = session.get('workspace_id')
    
    if not user_id or not workspace_id:
        return jsonify({'error': 'User or workspace not found'}), 400
    
    data = request.get_json()
    if not data or 'widths' not in data:
        return jsonify({'error': 'No widths provided'}), 400
    
    widths = data['widths']
    
    from models import db
    from sqlalchemy import text
    import json
    
    try:
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
                {'value': json.dumps(widths), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'contacts_column_widths', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(widths)}
            )
        
        db.session.commit()
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving column widths: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/user-preferences/contacts-assignee-filter', methods=['GET'])
@login_required
def get_contacts_assignee_filter():
    """Get user's assignee filter preference for contacts"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_assignee_filter'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'assignee_filter': json.loads(result[0])}), 200
        
        # Default to "all"
        return jsonify({'assignee_filter': 'all'}), 200
        
    except Exception as e:
        logger.error(f"Error getting assignee filter: {str(e)}")
        return jsonify({'assignee_filter': 'all'}), 200


@contacts_bp.route('/api/v1/user-preferences/contacts-assignee-filter', methods=['POST'])
@login_required
def save_contacts_assignee_filter():
    """Save user's assignee filter preference for contacts"""
    user_id = session.get('user_id')
    workspace_id = session.get('workspace_id')
    
    if not user_id or not workspace_id:
        return jsonify({'error': 'User or workspace not found'}), 400
    
    data = request.get_json()
    if not data or 'assignee_filter' not in data:
        return jsonify({'error': 'No assignee_filter provided'}), 400
    
    assignee_filter = data['assignee_filter']
    
    from models import db
    from sqlalchemy import text
    import json
    
    try:
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_assignee_filter'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_assignee_filter'"),
                {'value': json.dumps(assignee_filter), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'contacts_assignee_filter', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(assignee_filter)}
            )
        
        db.session.commit()
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving assignee filter: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/user-preferences/companies-assignee-filter', methods=['GET'])
@login_required
def get_companies_assignee_filter():
    """Get user's assignee filter preference for companies"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'companies_assignee_filter'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'assignee_filter': json.loads(result[0])}), 200
        
        # Default to "all"
        return jsonify({'assignee_filter': 'all'}), 200
        
    except Exception as e:
        logger.error(f"Error getting companies assignee filter: {str(e)}")
        return jsonify({'assignee_filter': 'all'}), 200


@contacts_bp.route('/api/v1/user-preferences/companies-assignee-filter', methods=['POST'])
@login_required
def save_companies_assignee_filter():
    """Save user's assignee filter preference for companies"""
    user_id = session.get('user_id')
    workspace_id = session.get('workspace_id')
    
    if not user_id or not workspace_id:
        return jsonify({'error': 'User or workspace not found'}), 400
    
    data = request.get_json()
    if not data or 'assignee_filter' not in data:
        return jsonify({'error': 'No assignee_filter provided'}), 400
    
    assignee_filter = data['assignee_filter']
    
    from models import db
    from sqlalchemy import text
    import json
    
    try:
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'companies_assignee_filter'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'companies_assignee_filter'"),
                {'value': json.dumps(assignee_filter), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'companies_assignee_filter', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(assignee_filter)}
            )
        
        db.session.commit()
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving companies assignee filter: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# DRAG-AND-DROP REORDERING ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/reorder', methods=['POST'])
@login_required
def reorder_contacts():
    """Reorder contacts by updating display_order"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact_ids = data.get('contact_ids', [])
        
        if not contact_ids:
            return jsonify({'error': 'No contact IDs provided'}), 400
        
        from models_crm import Contact
        from models import db
        
        # Validate all contacts belong to workspace
        contacts = Contact.query.filter(
            Contact.id.in_(contact_ids),
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
        ).all()
        
        if len(contacts) != len(contact_ids):
            return jsonify({'error': 'Some contacts not found or do not belong to workspace'}), 404
        
        # Update display_order for each contact
        try:
            for idx, contact_id in enumerate(contact_ids):
                contact = next((c for c in contacts if c.id == contact_id), None)
                if contact:
                    contact.display_order = idx
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Reordered {len(contact_ids)} contacts',
                'updated': len(contact_ids)
            }), 200
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error reordering contacts: {str(db_error)}")
            return jsonify({'error': 'Failed to save new order'}), 500
        
    except Exception as e:
        logger.error(f"Error reordering contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/toggle-star', methods=['POST'])
@login_required
def toggle_contact_star(contact_id):
    """Toggle starred status for a contact"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import db
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        try:
            # Toggle the starred status
            contact.is_starred = not contact.is_starred
            db.session.commit()
            
            return jsonify({
                'success': True,
                'is_starred': contact.is_starred,
                'message': 'Yıldız durumu güncellendi'
            }), 200
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error toggling star: {str(db_error)}")
            return jsonify({'error': 'Failed to update star status'}), 500
        
    except Exception as e:
        logger.error(f"Error toggling contact star: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/reorder', methods=['POST'])
@login_required
def reorder_companies():
    """Reorder companies by updating display_order"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company_ids = data.get('company_ids', [])
        
        if not company_ids:
            return jsonify({'error': 'No company IDs provided'}), 400
        
        from models_crm import Company
        from models import db
        
        # Validate all companies belong to workspace
        companies = Company.query.filter(
            Company.id.in_(company_ids),
            Company.workspace_id == workspace_id,
            Company.is_deleted == False,
        ).all()
        
        if len(companies) != len(company_ids):
            return jsonify({'error': 'Some companies not found or do not belong to workspace'}), 404
        
        # Update display_order for each company
        try:
            for idx, company_id in enumerate(company_ids):
                company = next((c for c in companies if c.id == company_id), None)
                if company:
                    company.display_order = idx
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Reordered {len(company_ids)} companies',
                'updated': len(company_ids)
            }), 200
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error reordering companies: {str(db_error)}")
            return jsonify({'error': 'Failed to save new order'}), 500
        
    except Exception as e:
        logger.error(f"Error reordering companies: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# SAVED FILTER ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/saved-filters', methods=['POST'])
@login_required
def create_saved_filter():
    """Create a new saved filter"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'name' not in data:
            return jsonify({'error': 'Filter name is required'}), 400
        if 'entity_type' not in data:
            return jsonify({'error': 'Entity type is required'}), 400
        if 'filter_config' not in data:
            return jsonify({'error': 'Filter configuration is required'}), 400
        
        # Validate entity_type
        if data['entity_type'] not in ['contact', 'company']:
            return jsonify({'error': 'Invalid entity type. Must be contact or company'}), 400
        
        from services.saved_filter_service import SavedFilterService
        
        try:
            saved_filter = SavedFilterService.create_filter(
                workspace_id=workspace_id,
                user_id=user_id,
                name=data['name'],
                entity_type=data['entity_type'],
                filter_config=data['filter_config'],
                is_shared=data.get('is_shared', False)
            )
            
            return jsonify({
                'id': saved_filter.id,
                'name': saved_filter.name,
                'entity_type': saved_filter.entity_type,
                'filter_config': saved_filter.filter_config,
                'is_shared': saved_filter.is_shared,
                'created_at': saved_filter.created_at.isoformat() if saved_filter.created_at else None
            }), 201
            
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Error creating saved filter: {str(e)}")
            return jsonify({'error': 'Failed to create filter'}), 500
        
    except Exception as e:
        logger.error(f"Error in create_saved_filter: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/saved-filters', methods=['GET'])
@login_required
def get_saved_filters():
    """Get user's saved filters"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get entity_type from query params
        entity_type = request.args.get('entity_type')
        if not entity_type:
            return jsonify({'error': 'entity_type parameter is required'}), 400
        
        if entity_type not in ['contact', 'company']:
            return jsonify({'error': 'Invalid entity type. Must be contact or company'}), 400
        
        from services.saved_filter_service import SavedFilterService
        
        filters = SavedFilterService.get_user_filters(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=entity_type
        )
        
        return jsonify({
            'filters': [
                {
                    'id': f.id,
                    'name': f.name,
                    'entity_type': f.entity_type,
                    'filter_config': f.filter_config,
                    'is_shared': f.is_shared,
                    'created_at': f.created_at.isoformat() if f.created_at else None,
                    'updated_at': f.updated_at.isoformat() if f.updated_at else None
                }
                for f in filters
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting saved filters: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/saved-filters/<int:filter_id>', methods=['DELETE'])
@login_required
def delete_saved_filter(filter_id):
    """Delete a saved filter"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from services.saved_filter_service import SavedFilterService
        
        try:
            SavedFilterService.delete_filter(
                filter_id=filter_id,
                workspace_id=workspace_id,
                user_id=user_id
            )
            
            return jsonify({'message': 'Filter deleted successfully'}), 200
            
        except PermissionError as e:
            return jsonify({'error': str(e)}), 403
        except LookupError as e:
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Error deleting saved filter: {str(e)}")
            return jsonify({'error': 'Failed to delete filter'}), 500
        
    except Exception as e:
        logger.error(f"Error in delete_saved_filter: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/saved-filters/<int:filter_id>/share', methods=['PATCH'])
@login_required
def share_saved_filter(filter_id):
    """Share or unshare a saved filter"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data or 'is_shared' not in data:
            return jsonify({'error': 'is_shared field is required'}), 400
        
        if not isinstance(data['is_shared'], bool):
            return jsonify({'error': 'is_shared must be a boolean'}), 400
        
        from services.saved_filter_service import SavedFilterService
        
        try:
            saved_filter = SavedFilterService.share_filter(
                filter_id=filter_id,
                workspace_id=workspace_id,
                user_id=user_id,
                is_shared=data['is_shared']
            )
            
            return jsonify({
                'id': saved_filter.id,
                'name': saved_filter.name,
                'is_shared': saved_filter.is_shared,
                'updated_at': saved_filter.updated_at.isoformat() if saved_filter.updated_at else None
            }), 200
            
        except PermissionError as e:
            return jsonify({'error': str(e)}), 403
        except LookupError as e:
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Error sharing saved filter: {str(e)}")
            return jsonify({'error': 'Failed to update filter'}), 500
        
    except Exception as e:
        logger.error(f"Error in share_saved_filter: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# ADVANCED EXPORT ENDPOINTS (with filtering)
# ============================================================================

@contacts_bp.route('/api/v1/contacts/export-filtered', methods=['POST'])
@login_required
def export_contacts_filtered():
    """Export contacts with advanced filtering to CSV or Excel"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get parameters
        filters = data.get('filters', {'filters': []})
        export_format = data.get('format', 'csv').lower()
        columns = data.get('columns', [
            'id', 'first_name', 'last_name', 'email', 'phone', 
            'whatsapp_phone', 'role', 'job_title', 'lead_score', 
            'company_id', 'is_starred', 'created_at', 'updated_at'
        ])
        
        # Validate format
        if export_format not in ['csv', 'xlsx']:
            return jsonify({'error': 'Invalid format. Must be csv or xlsx'}), 400
        
        from services.filter_service import FilterService
        
        # Apply filters without pagination (max 5000 records)
        try:
            results, pagination_info = FilterService.apply_filters(
                entity_type='contact',
                workspace_id=workspace_id,
                user_id=user_id,
                filters=filters,
                page=1,
                per_page=5000,
                sort_by='created_at',
                sort_order='desc'
            )
            
            # Check result count limit
            if pagination_info['total'] > 5000:
                return jsonify({
                    'error': f'Too many records to export ({pagination_info["total"]}). Maximum is 5000. Please apply more filters.'
                }), 400
            
            # Export based on format
            if export_format == 'csv':
                csv_data = FilterService.export_to_csv(results, columns, 'contact')
                
                response = make_response(csv_data)
                response.headers['Content-Type'] = 'text/csv; charset=utf-8'
                response.headers['Content-Disposition'] = f'attachment; filename=contacts_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                return response
                
            else:  # xlsx
                excel_data = FilterService.export_to_excel(results, columns, 'contact')
                
                response = make_response(excel_data.read())
                response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                response.headers['Content-Disposition'] = f'attachment; filename=contacts_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                return response
                
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Error exporting contacts: {str(e)}")
            return jsonify({'error': 'Export failed'}), 500
        
    except Exception as e:
        logger.error(f"Error in export_contacts_filtered: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/export-filtered', methods=['POST'])
@login_required
def export_companies_filtered():
    """Export companies with advanced filtering to CSV or Excel"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get parameters
        filters = data.get('filters', {'filters': []})
        export_format = data.get('format', 'csv').lower()
        columns = data.get('columns', [
            'id', 'name', 'industry', 'size', 'website', 
            'phone', 'address', 'parent_company_id', 
            'created_at', 'updated_at'
        ])
        
        # Validate format
        if export_format not in ['csv', 'xlsx']:
            return jsonify({'error': 'Invalid format. Must be csv or xlsx'}), 400
        
        from services.filter_service import FilterService
        
        # Apply filters without pagination (max 5000 records)
        try:
            results, pagination_info = FilterService.apply_filters(
                entity_type='company',
                workspace_id=workspace_id,
                user_id=user_id,
                filters=filters,
                page=1,
                per_page=5000,
                sort_by='created_at',
                sort_order='desc'
            )
            
            # Check result count limit
            if pagination_info['total'] > 5000:
                return jsonify({
                    'error': f'Too many records to export ({pagination_info["total"]}). Maximum is 5000. Please apply more filters.'
                }), 400
            
            # Export based on format
            if export_format == 'csv':
                csv_data = FilterService.export_to_csv(results, columns, 'company')
                
                response = make_response(csv_data)
                response.headers['Content-Type'] = 'text/csv; charset=utf-8'
                response.headers['Content-Disposition'] = f'attachment; filename=companies_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                return response
                
            else:  # xlsx
                excel_data = FilterService.export_to_excel(results, columns, 'company')
                
                response = make_response(excel_data.read())
                response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                response.headers['Content-Disposition'] = f'attachment; filename=companies_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                return response
                
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Error exporting companies: {str(e)}")
            return jsonify({'error': 'Export failed'}), 500
        
    except Exception as e:
        logger.error(f"Error in export_companies_filtered: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# LEAD MANAGEMENT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/<int:contact_id>/qualify', methods=['POST'])
@login_required
def qualify_lead(contact_id):
    """
    Qualify a lead (move from 'lead' to 'qualified_lead' stage)
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models import db
        
        # Get contact
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Check if already qualified
        if contact.lifecycle_stage != 'lead':
            return jsonify({'error': f'Contact is already in {contact.lifecycle_stage} stage'}), 400
        
        try:
            # Update lifecycle stage
            contact.lifecycle_stage = 'qualified_lead'
            contact.qualified_at = datetime.utcnow()
            contact.updated_at = datetime.utcnow()
            
            # Log activity
            from models_crm import Activity
            activity = Activity(
                workspace_id=workspace_id,
                activity_type='system',
                contact_id=contact_id,
                company_id=contact.company_id,
                user_id=user_id,
                subject='Lead Qualified',
                body=f'{contact.full_name} was qualified as a lead',
                created_at=datetime.utcnow()
            )
            db.session.add(activity)
            
            db.session.commit()
            
            logger.info(f"Lead {contact_id} qualified by user {user_id}")
            
            return jsonify({
                'status': 'ok',
                'message': 'Lead qualified successfully',
                'contact': {
                    'id': contact.id,
                    'lifecycle_stage': contact.lifecycle_stage,
                    'qualified_at': contact.qualified_at.isoformat() if contact.qualified_at else None
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to qualify lead {contact_id}: {str(e)}")
            return jsonify({'error': 'Failed to qualify lead'}), 500
            
    except Exception as e:
        logger.exception(f"Error qualifying lead {contact_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/convert', methods=['POST'])
@login_required
def convert_to_customer(contact_id):
    """
    Convert a qualified lead to customer
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models import db
        
        # Get contact
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Check if can be converted
        if contact.lifecycle_stage not in ['lead', 'qualified_lead']:
            return jsonify({'error': f'Contact is already in {contact.lifecycle_stage} stage'}), 400
        
        try:
            # Update lifecycle stage
            old_stage = contact.lifecycle_stage
            contact.lifecycle_stage = 'customer'
            contact.converted_at = datetime.utcnow()
            contact.updated_at = datetime.utcnow()
            
            # If not qualified yet, mark as qualified too
            if not contact.qualified_at:
                contact.qualified_at = datetime.utcnow()
            
            # Log activity
            from models_crm import Activity
            activity = Activity(
                workspace_id=workspace_id,
                activity_type='system',
                contact_id=contact_id,
                company_id=contact.company_id,
                user_id=user_id,
                subject='Lead Converted to Customer',
                body=f'{contact.full_name} was converted from {old_stage} to customer',
                created_at=datetime.utcnow()
            )
            db.session.add(activity)
            
            db.session.commit()
            
            logger.info(f"Lead {contact_id} converted to customer by user {user_id}")
            
            return jsonify({
                'status': 'ok',
                'message': 'Lead converted to customer successfully',
                'contact': {
                    'id': contact.id,
                    'lifecycle_stage': contact.lifecycle_stage,
                    'qualified_at': contact.qualified_at.isoformat() if contact.qualified_at else None,
                    'converted_at': contact.converted_at.isoformat() if contact.converted_at else None
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to convert lead {contact_id}: {str(e)}")
            return jsonify({'error': 'Failed to convert lead'}), 500
            
    except Exception as e:
        logger.exception(f"Error converting lead {contact_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/lifecycle-stage', methods=['PATCH'])
@login_required
def update_lifecycle_stage(contact_id):
    """
    Update contact lifecycle stage manually
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        new_stage = data.get('lifecycle_stage')
        if not new_stage:
            return jsonify({'error': 'lifecycle_stage is required'}), 400
        
        # Validate stage
        valid_stages = ['lead', 'qualified_lead', 'customer', 'evangelist']
        if new_stage not in valid_stages:
            return jsonify({'error': f'Invalid lifecycle_stage. Must be one of: {", ".join(valid_stages)}'}), 400
        
        from models_crm import Contact
        from models import db
        
        # Get contact
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        try:
            old_stage = contact.lifecycle_stage
            contact.lifecycle_stage = new_stage
            contact.updated_at = datetime.utcnow()
            
            # Update timestamps based on stage
            if new_stage in ['qualified_lead', 'customer', 'evangelist'] and not contact.qualified_at:
                contact.qualified_at = datetime.utcnow()
            
            if new_stage in ['customer', 'evangelist'] and not contact.converted_at:
                contact.converted_at = datetime.utcnow()
            
            # Log activity
            from models_crm import Activity
            activity = Activity(
                workspace_id=workspace_id,
                activity_type='system',
                contact_id=contact_id,
                company_id=contact.company_id,
                user_id=user_id,
                subject='Lifecycle Stage Updated',
                body=f'{contact.full_name} moved from {old_stage} to {new_stage}',
                created_at=datetime.utcnow()
            )
            db.session.add(activity)
            
            db.session.commit()
            
            logger.info(f"Contact {contact_id} lifecycle stage updated from {old_stage} to {new_stage} by user {user_id}")
            
            return jsonify({
                'status': 'ok',
                'message': 'Lifecycle stage updated successfully',
                'contact': {
                    'id': contact.id,
                    'lifecycle_stage': contact.lifecycle_stage,
                    'qualified_at': contact.qualified_at.isoformat() if contact.qualified_at else None,
                    'converted_at': contact.converted_at.isoformat() if contact.converted_at else None
                }
            }), 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update lifecycle stage for contact {contact_id}: {str(e)}")
            return jsonify({'error': 'Failed to update lifecycle stage'}), 500
            
    except Exception as e:
        logger.exception(f"Error updating lifecycle stage for contact {contact_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/api/v1/leads/stats', methods=['GET'])
@login_required
def get_lead_stats():
    """
    Get lead statistics (counts by stage, source, etc.)
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models import db
        from sqlalchemy import func
        
        # Get counts by lifecycle stage
        stage_counts = db.session.query(
            Contact.lifecycle_stage,
            func.count(Contact.id).label('count')
        ).filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False
        ).group_by(Contact.lifecycle_stage).all()
        
        # Get counts by lead source
        source_counts = db.session.query(
            Contact.lead_source,
            func.count(Contact.id).label('count')
        ).filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lead_source.isnot(None)
        ).group_by(Contact.lead_source).all()
        
        # Get conversion metrics
        total_leads = Contact.query.filter_by(
            workspace_id=workspace_id,
            is_deleted=False
        ).count()
        
        qualified_leads = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lifecycle_stage.in_(['qualified_lead', 'customer', 'evangelist'])
        ).count()
        
        customers = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lifecycle_stage.in_(['customer', 'evangelist'])
        ).count()
        
        # Calculate conversion rates
        qualification_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
        conversion_rate = (customers / total_leads * 100) if total_leads > 0 else 0
        
        return jsonify({
            'status': 'ok',
            'stats': {
                'by_stage': {stage: count for stage, count in stage_counts},
                'by_source': {source: count for source, count in source_counts if source},
                'totals': {
                    'total_contacts': total_leads,
                    'qualified_leads': qualified_leads,
                    'customers': customers
                },
                'conversion_rates': {
                    'qualification_rate': round(qualification_rate, 2),
                    'conversion_rate': round(conversion_rate, 2)
                }
            }
        }), 200
        
    except Exception as e:
        logger.exception(f"Error getting lead stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# TAG MANAGEMENT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/tags', methods=['GET'])
@login_required
def get_tags():
    """Get all tags for the workspace"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from services.tag_service import TagService
        tags = TagService.get_tags(workspace_id)
        return jsonify({'tags': [t.to_dict() for t in tags]}), 200

    except Exception as e:
        logger.error(f"Error getting tags: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/tags', methods=['POST'])
@login_required
def create_tag():
    """Create a new tag"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'Tag name is required'}), 400

        from services.tag_service import TagService
        tag = TagService.create_tag(workspace_id, data['name'], data.get('color', '#6366f1'))
        return jsonify(tag.to_dict()), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating tag: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/tags/<int:tag_id>', methods=['PATCH'])
@login_required
def update_tag(tag_id):
    """Update a tag"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        from services.tag_service import TagService
        tag = TagService.update_tag(workspace_id, tag_id, data)
        return jsonify(tag.to_dict()), 200

    except LookupError:
        return jsonify({'error': 'Tag not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating tag: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def delete_tag(tag_id):
    """Delete a tag"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from services.tag_service import TagService
        TagService.delete_tag(workspace_id, tag_id)
        return jsonify({'message': 'Tag deleted'}), 200

    except LookupError:
        return jsonify({'error': 'Tag not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting tag: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/tags', methods=['GET'])
@login_required
def get_contact_tags(contact_id):
    """Get tags for a contact"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from services.tag_service import TagService
        tags = TagService.get_contact_tags(contact_id)
        return jsonify({'tags': [t.to_dict() for t in tags]}), 200

    except Exception as e:
        logger.error(f"Error getting contact tags: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


def _trigger_contact_tag_added(workspace_id, contact_id, tag_name):
    try:
        from services.workflow_service import WorkflowService
        WorkflowService.trigger_event(
            workspace_id=workspace_id,
            trigger_type='contact_tag_added',
            entity_type='contact',
            entity_id=contact_id,
            context={'tag_name': tag_name}
        )
    except Exception as e:
        logger.error(f"Workflow trigger error for contact_tag_added: {e}")


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/tags', methods=['POST'])
@login_required
def add_contact_tags(contact_id):
    """Add tags to a contact. Body: { tag_ids: [1,2,3] } or { tag_name: 'VIP' }"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        from services.tag_service import TagService

        # Support adding by name (auto-create)
        if 'tag_name' in data:
            tag = TagService.get_or_create_tag(workspace_id, data['tag_name'], data.get('color', '#6366f1'))
            tags = TagService.add_tags_to_contact(workspace_id, contact_id, [tag.id])
            _trigger_contact_tag_added(workspace_id, contact_id, data['tag_name'])
            return jsonify({'tags': [t.to_dict() for t in tags]}), 200

        tag_ids = data.get('tag_ids', [])
        if not tag_ids:
            return jsonify({'error': 'tag_ids or tag_name is required'}), 400

        tags = TagService.add_tags_to_contact(workspace_id, contact_id, tag_ids)
        _trigger_contact_tag_added(workspace_id, contact_id, '')
        return jsonify({'tags': [t.to_dict() for t in tags]}), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding contact tags: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def remove_contact_tag(contact_id, tag_id):
    """Remove a tag from a contact"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        from services.tag_service import TagService
        TagService.remove_tag_from_contact(contact_id, tag_id)
        return jsonify({'message': 'Tag removed'}), 200

    except Exception as e:
        logger.error(f"Error removing contact tag: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>/tags/set', methods=['PUT'])
@login_required
def set_contact_tags(contact_id):
    """Replace all tags on a contact. Body: { tag_ids: [1,2,3] }"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        data = request.get_json()
        tag_ids = data.get('tag_ids', []) if data else []

        from services.tag_service import TagService
        tags = TagService.set_contact_tags(workspace_id, contact_id, tag_ids)
        return jsonify({'tags': [t.to_dict() for t in tags]}), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error setting contact tags: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# COMPANY MERGE ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/companies/duplicates', methods=['GET'])
@login_required
def find_company_duplicates():
    """Find duplicate companies in the workspace."""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        company_id = request.args.get('company_id', type=int)

        from services.company_merge_service import CompanyMergeService
        groups = CompanyMergeService.find_duplicates(workspace_id, company_id)
        return jsonify({'duplicate_groups': groups}), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error finding company duplicates: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/companies/merge', methods=['POST'])
@login_required
def merge_companies():
    """Merge two companies. Body: { primary_id, secondary_id, field_overrides? }"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        primary_id = data.get('primary_id')
        secondary_id = data.get('secondary_id')
        if not primary_id or not secondary_id:
            return jsonify({'error': 'primary_id and secondary_id are required'}), 400

        from services.company_merge_service import CompanyMergeService
        company = CompanyMergeService.merge_companies(
            workspace_id=workspace_id,
            primary_id=primary_id,
            secondary_id=secondary_id,
            user_id=user_id,
            field_overrides=data.get('field_overrides'),
        )

        return jsonify({
            'message': 'Companies merged successfully',
            'company': {
                'id': company.id,
                'name': company.name,
                'industry': company.industry,
                'size': company.size,
                'website': company.website,
                'phone': company.phone,
            }
        }), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error merging companies: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# CONTACT MERGE ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/duplicates', methods=['GET'])
@login_required
def find_duplicates():
    """Find duplicate contacts in the workspace"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        contact_id = request.args.get('contact_id', type=int)

        from services.contact_merge_service import ContactMergeService
        groups = ContactMergeService.find_duplicates(workspace_id, contact_id)
        return jsonify({'duplicate_groups': groups}), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@contacts_bp.route('/api/v1/contacts/merge', methods=['POST'])
@login_required
def merge_contacts():
    """Merge two contacts. Body: { primary_id, secondary_id, field_overrides? }"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        primary_id = data.get('primary_id')
        secondary_id = data.get('secondary_id')
        if not primary_id or not secondary_id:
            return jsonify({'error': 'primary_id and secondary_id are required'}), 400

        from services.contact_merge_service import ContactMergeService
        contact = ContactMergeService.merge_contacts(
            workspace_id, primary_id, secondary_id, user_id,
            data.get('field_overrides')
        )

        return jsonify({
            'message': 'Contacts merged successfully',
            'contact': {
                'id': contact.id,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'full_name': contact.full_name,
                'email': contact.email,
                'phone': contact.phone,
            }
        }), 200

    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error merging contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# WHATSAPP TIMELINE INTEGRATION
# ============================================================================

@contacts_bp.route('/api/v1/contacts/<int:contact_id>/whatsapp-messages', methods=['GET'])
@login_required
def get_contact_whatsapp_messages(contact_id):
    """Get WhatsApp/Telegram message history for a contact"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        from models_crm import Contact
        from models import db, Customer, Conversation, Message

        contact = Contact.query.filter_by(
            id=contact_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        # Find linked customer
        customer_id = contact.customer_id
        if not customer_id:
            return jsonify({'messages': [], 'pagination': {'page': page, 'total': 0, 'pages': 0}}), 200

        # Get conversation
        conversation = Conversation.query.filter_by(
            workspace_id=workspace_id, customer_id=customer_id
        ).first()
        if not conversation:
            return jsonify({'messages': [], 'pagination': {'page': page, 'total': 0, 'pages': 0}}), 200

        # Get messages
        messages_page = Message.query.filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        result = []
        for msg in messages_page.items:
            result.append({
                'id': msg.id,
                'body': msg.message_body,
                'direction': 'outgoing' if msg.sender_id else 'incoming',
                'sender_name': msg.sender.name if msg.sender_id and msg.sender else contact.full_name,
                'media_type': msg.media_type,
                'media_url': f"/api/media/{msg.media_url}" if msg.media_url else None,
                'channel': msg.channel if hasattr(msg, 'channel') else 'whatsapp',
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
            })

        return jsonify({
            'messages': result,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': messages_page.total,
                'pages': messages_page.pages,
                'has_next': messages_page.has_next,
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting WhatsApp messages: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ============================================================================
# INACTIVITY TRACKING
# ============================================================================

@contacts_bp.route('/api/v1/contacts/inactive', methods=['GET'])
@login_required
def get_inactive_contacts():
    """Get contacts with no activity in the last N days (default 30)"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        days = request.args.get('days', 30, type=int)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)

        from models_crm import Contact
        from models import db
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            db.or_(
                Contact.last_activity_at.is_(None),
                Contact.last_activity_at < cutoff
            )
        ).order_by(Contact.last_activity_at.asc().nullsfirst())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        contacts = []
        for c in pagination.items:
            days_inactive = None
            if c.last_activity_at:
                days_inactive = (datetime.utcnow() - c.last_activity_at).days
            elif c.created_at:
                days_inactive = (datetime.utcnow() - c.created_at).days

            contacts.append({
                'id': c.id,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'full_name': c.full_name,
                'email': c.email,
                'phone': c.phone,
                'company_name': c.company.name if c.company else None,
                'last_activity_at': c.last_activity_at.isoformat() if c.last_activity_at else None,
                'days_inactive': days_inactive,
                'lead_score': c.lead_score,
            })

        return jsonify({
            'contacts': contacts,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
            },
            'threshold_days': days,
        }), 200

    except Exception as e:
        logger.error(f"Error getting inactive contacts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500
