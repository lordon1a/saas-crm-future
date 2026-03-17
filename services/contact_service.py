"""
Contact Service
Business logic for company and contact management
"""
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import or_, and_
from models import db
from models_crm import Company, Contact, CustomField, CustomFieldValue, Activity

logger = logging.getLogger(__name__)


class ContactService:
    """Service for managing companies and contacts"""
    
    # ============================================================================
    # COMPANY OPERATIONS
    # ============================================================================
    
    @staticmethod
    def create_company(workspace_id: int, data: Dict[str, Any], user_id: int) -> Company:
        """
        Create a new company.
        
        Args:
            workspace_id: Workspace ID
            data: Company data (name, industry, size, website, phone, address, parent_company_id)
            user_id: User creating the company
        
        Returns:
            Company: Created company instance
        
        Raises:
            ValueError: If required fields are missing
        """
        if 'name' not in data or not data['name'].strip():
            raise ValueError("Company name is required")
        
        company = Company(
            workspace_id=workspace_id,
            name=data['name'],
            industry=data.get('industry'),
            size=data.get('size'),
            parent_company_id=data.get('parent_company_id'),
            website=data.get('website'),
            phone=data.get('phone'),
            address=data.get('address')
        )
        
        db.session.add(company)
        db.session.flush()
        
        # Create activity
        ContactService._create_activity(
            workspace_id=workspace_id,
            company_id=company.id,
            user_id=user_id,
            activity_type='system',
            subject=f'Company created: {company.name}',
            body=f'Company "{company.name}" was created'
        )
        
        # Handle custom fields
        if 'custom_fields' in data:
            ContactService._save_custom_fields(
                workspace_id, 'company', company.id, data['custom_fields']
            )
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Created company {company.id}: {company.name}")
        
        return company
    
    @staticmethod
    def update_company(workspace_id: int, company_id: int, data: Dict[str, Any], user_id: int) -> Company:
        """Update a company."""
        company = Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not company:
            raise LookupError(f"Company {company_id} not found")
        
        # Validate parent company if provided
        if 'parent_company_id' in data and data['parent_company_id']:
            if data['parent_company_id'] == company_id:
                raise ValueError("Company cannot be its own parent")
            
            parent = Company.query.filter_by(
                id=data['parent_company_id'],
                workspace_id=workspace_id,
                is_deleted=False,
            ).first()
            
            if not parent:
                raise ValueError(f"Parent company {data['parent_company_id']} not found in workspace")
        
        # Track changes
        changes = {}
        for field in ['name', 'industry', 'size', 'website', 'phone', 'address', 'parent_company_id']:
            if field in data and getattr(company, field) != data[field]:
                old_value = getattr(company, field)
                setattr(company, field, data[field])
                changes[field] = {'old': old_value, 'new': data[field]}
        
        if changes:
            company.updated_at = datetime.utcnow()
            
            change_desc = ', '.join([f"{k}: {v['old']} → {v['new']}" for k, v in changes.items()])
            ContactService._create_activity(
                workspace_id=workspace_id,
                company_id=company.id,
                user_id=user_id,
                activity_type='system',
                subject=f'Company updated: {company.name}',
                body=f'Changes: {change_desc}'
            )
        
        # Handle custom fields
        if 'custom_fields' in data:
            ContactService._save_custom_fields(
                workspace_id, 'company', company.id, data['custom_fields']
            )
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Updated company {company.id}")
        
        return company
    
    @staticmethod
    def get_companies(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Company]:
        """Get companies with optional filters."""
        query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        if filters:
            if 'industry' in filters:
                query = query.filter_by(industry=filters['industry'])
            if 'size' in filters:
                query = query.filter_by(size=filters['size'])
            if 'search' in filters and filters['search']:
                search = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Company.name.ilike(search),
                        Company.website.ilike(search),
                        Company.phone.ilike(search)
                    )
                )
        
        return query.order_by(Company.name.asc()).all()
    
    # ============================================================================
    # CONTACT OPERATIONS
    # ============================================================================
    
    @staticmethod
    def create_contact(workspace_id: int, data: Dict[str, Any], user_id: int) -> Contact:
        """
        Create a new contact.
        
        Args:
            workspace_id: Workspace ID
            data: Contact data (first_name, last_name, email, phone, company_id, role, job_title)
            user_id: User creating the contact
        
        Returns:
            Contact: Created contact instance
        
        Raises:
            ValueError: If required fields are missing
        """
        if 'first_name' not in data or not data['first_name'].strip():
            raise ValueError("First name is required")
        
        # Validate company if provided
        if data.get('company_id'):
            company = Company.query.filter_by(
                id=data['company_id'],
                workspace_id=workspace_id,
                is_deleted=False,
            ).first()
            
            if not company:
                raise ValueError(f"Company {data['company_id']} not found in workspace")
        
        # Check for duplicates
        if data.get('email') or data.get('phone'):
            duplicates = ContactService.find_duplicates(
                workspace_id,
                email=data.get('email'),
                phone=data.get('phone')
            )
            if duplicates:
                logger.warning(f"Potential duplicates found for contact: {duplicates}")
        
        contact = Contact(
            workspace_id=workspace_id,
            company_id=data.get('company_id'),
            first_name=data['first_name'],
            last_name=data.get('last_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            whatsapp_phone=data.get('whatsapp_phone'),
            role=data.get('role'),
            job_title=data.get('job_title'),
            lead_score=data.get('lead_score', 0),
            customer_id=data.get('customer_id')
        )
        
        db.session.add(contact)
        db.session.flush()
        
        # Create activity
        ContactService._create_activity(
            workspace_id=workspace_id,
            contact_id=contact.id,
            company_id=contact.company_id,
            user_id=user_id,
            activity_type='system',
            subject=f'Contact created: {contact.full_name}',
            body=f'Contact "{contact.full_name}" was created'
        )
        
        # Handle custom fields
        if 'custom_fields' in data:
            ContactService._save_custom_fields(
                workspace_id, 'contact', contact.id, data['custom_fields']
            )
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Created contact {contact.id}: {contact.full_name}")
        
        return contact
    
    @staticmethod
    def update_contact(workspace_id: int, contact_id: int, data: Dict[str, Any], user_id: int) -> Contact:
        """Update a contact."""
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not contact:
            raise LookupError(f"Contact {contact_id} not found")

        if 'company_id' in data and data['company_id'] is not None:
            target_company = Company.query.filter_by(id=data['company_id'], is_deleted=False).first()
            if not target_company or target_company.workspace_id != contact.workspace_id:
                raise ValueError("Yetkisiz şirket ataması")
        
        # Track changes
        changes = {}
        for field in ['first_name', 'last_name', 'email', 'phone', 'whatsapp_phone', 
                     'role', 'job_title', 'lead_score', 'company_id']:
            if field in data and getattr(contact, field) != data[field]:
                old_value = getattr(contact, field)
                setattr(contact, field, data[field])
                changes[field] = {'old': old_value, 'new': data[field]}
        
        if changes:
            contact.updated_at = datetime.utcnow()
            
            change_desc = ', '.join([f"{k}: {v['old']} → {v['new']}" for k, v in changes.items()])
            ContactService._create_activity(
                workspace_id=workspace_id,
                contact_id=contact.id,
                company_id=contact.company_id,
                user_id=user_id,
                activity_type='system',
                subject=f'Contact updated: {contact.full_name}',
                body=f'Changes: {change_desc}'
            )
        
        # Handle custom fields
        if 'custom_fields' in data:
            ContactService._save_custom_fields(
                workspace_id, 'contact', contact.id, data['custom_fields']
            )
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Updated contact {contact.id}")
        
        return contact
    
    @staticmethod
    def get_contacts(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Contact]:
        """Get contacts with optional filters."""
        query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        if filters:
            if 'company_id' in filters:
                query = query.filter_by(company_id=filters['company_id'])
            if 'role' in filters:
                query = query.filter_by(role=filters['role'])
            if 'search' in filters and filters['search']:
                search = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Contact.first_name.ilike(search),
                        Contact.last_name.ilike(search),
                        Contact.email.ilike(search),
                        Contact.phone.ilike(search),
                        Contact.job_title.ilike(search)
                    )
                )
        
        return query.order_by(Contact.first_name.asc()).all()
    
    @staticmethod
    def find_duplicates(workspace_id: int, email: Optional[str] = None, 
                       phone: Optional[str] = None) -> List[Contact]:
        """
        Find potential duplicate contacts by email or phone.
        
        Args:
            workspace_id: Workspace ID
            email: Email to search for
            phone: Phone to search for
        
        Returns:
            List[Contact]: List of potential duplicates
        """
        if not email and not phone:
            return []
        
        conditions = []
        if email:
            conditions.append(Contact.email == email)
        if phone:
            conditions.append(Contact.phone == phone)
        
        query = Contact.query.filter(
            and_(
                Contact.workspace_id == workspace_id,
                Contact.is_deleted == False,
                or_(*conditions)
            )
        )
        
        return query.all()
    
    @staticmethod
    def calculate_lead_score(contact: Contact) -> int:
        """
        Calculate lead score for a contact based on various factors.
        
        Scoring criteria:
        - Has email: +20
        - Has phone: +10
        - Has company: +15
        - Has role (Decision Maker/Influencer): +25
        - Has job title: +10
        - Has WhatsApp: +20
        
        Returns:
            int: Lead score (0-100)
        """
        score = 0
        
        if contact.email:
            score += 20
        if contact.phone:
            score += 10
        if contact.company_id:
            score += 15
        if contact.role in ['Decision Maker', 'Influencer', 'Champion']:
            score += 25
        elif contact.role:
            score += 10
        if contact.job_title:
            score += 10
        if contact.whatsapp_phone:
            score += 20
        
        return min(score, 100)
    
    # ============================================================================
    # CUSTOM FIELDS
    # ============================================================================
    
    @staticmethod
    def create_custom_field(workspace_id: int, data: Dict[str, Any]) -> CustomField:
        """
        Create a custom field definition.
        
        Args:
            workspace_id: Workspace ID
            data: Field data (entity_type, field_name, field_type, options, is_required)
        
        Returns:
            CustomField: Created custom field
        """
        required_fields = ['entity_type', 'field_name', 'field_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if data['entity_type'] not in ['contact', 'company', 'deal']:
            raise ValueError("entity_type must be 'contact', 'company', or 'deal'")
        
        if data['field_type'] not in ['text', 'number', 'date', 'dropdown', 'checkbox', 'multi_select']:
            raise ValueError("Invalid field_type")
        
        # Check for duplicate field name
        existing = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type=data['entity_type'],
            field_name=data['field_name']
        ).first()
        
        if existing:
            raise ValueError(f"Custom field '{data['field_name']}' already exists for {data['entity_type']}")
        
        custom_field = CustomField(
            workspace_id=workspace_id,
            entity_type=data['entity_type'],
            field_name=data['field_name'],
            field_type=data['field_type'],
            options=json.dumps(data.get('options', [])) if data.get('options') else None,
            is_required=data.get('is_required', False)
        )
        
        db.session.add(custom_field)
        db.session.commit()
        
        logger.info(f"Created custom field {custom_field.id}: {custom_field.field_name}")
        
        return custom_field
    
    @staticmethod
    def get_custom_fields(workspace_id: int, entity_type: Optional[str] = None) -> List[CustomField]:
        """Get custom field definitions."""
        query = CustomField.query.filter_by(workspace_id=workspace_id)
        
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        
        return query.all()
    
    @staticmethod
    def get_custom_field_values(workspace_id: int, entity_type: str, entity_id: int) -> Dict[str, Any]:
        """
        Get custom field values for an entity.
        
        Returns:
            Dict mapping field_name to value
        """
        # Get field definitions
        fields = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type=entity_type
        ).all()
        
        # Get values
        values = CustomFieldValue.query.filter_by(entity_id=entity_id).all()
        value_map = {v.custom_field_id: v.value for v in values}
        
        # Build result
        result = {}
        for field in fields:
            result[field.field_name] = value_map.get(field.id)
        
        return result
    
    @staticmethod
    def _save_custom_fields(workspace_id: int, entity_type: str, entity_id: int, 
                           field_values: Dict[str, Any]) -> None:
        """Save custom field values for an entity."""
        # Get field definitions
        fields = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type=entity_type
        ).all()
        
        field_map = {f.field_name: f for f in fields}

        # Auto-create missing field definitions so first-time usage works seamlessly.
        for field_name in field_values.keys():
            if field_name in field_map:
                continue

            guessed_type = 'number' if field_name in ('annual_revenue', 'employee_count') else 'text'
            new_field = CustomField(
                workspace_id=workspace_id,
                entity_type=entity_type,
                field_name=field_name,
                field_type=guessed_type,
                is_required=False,
            )
            db.session.add(new_field)
            db.session.flush()
            field_map[field_name] = new_field
        
        for field_name, value in field_values.items():
            if field_name not in field_map:
                logger.warning(f"Custom field '{field_name}' not found, skipping")
                continue
            
            field = field_map[field_name]
            
            # Find or create value record
            field_value = CustomFieldValue.query.filter_by(
                custom_field_id=field.id,
                entity_id=entity_id
            ).first()
            
            if field_value:
                field_value.value = str(value) if value is not None else None
                field_value.updated_at = datetime.utcnow()
            else:
                field_value = CustomFieldValue(
                    custom_field_id=field.id,
                    entity_id=entity_id,
                    value=str(value) if value is not None else None
                )
                db.session.add(field_value)
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    @staticmethod
    def _create_activity(workspace_id: int, user_id: int, activity_type: str, 
                        subject: str, body: str, contact_id: Optional[int] = None,
                        company_id: Optional[int] = None) -> Activity:
        """Create an activity record."""
        activity = Activity(
            workspace_id=workspace_id,
            contact_id=contact_id,
            company_id=company_id,
            user_id=user_id,
            activity_type=activity_type,
            subject=subject,
            body=body
        )
        db.session.add(activity)
        return activity

    # ============================================================================
    # CSV IMPORT/EXPORT
    # ============================================================================
    
    @staticmethod
    def export_contacts_csv(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> str:
        """
        Export contacts to CSV format.
        
        Args:
            workspace_id: Workspace ID
            filters: Optional filters to apply
        
        Returns:
            str: CSV content as string
        """
        import csv
        from io import StringIO
        
        contacts = ContactService.get_contacts(workspace_id, filters)
        
        # Get all custom fields for contacts
        custom_fields = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type='contact'
        ).all()
        
        output = StringIO()
        
        # Build header
        headers = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'whatsapp_phone',
            'role', 'job_title', 'lead_score', 'company_id', 'company_name',
            'created_at', 'updated_at'
        ]
        
        # Add custom field headers
        for field in custom_fields:
            headers.append(f'custom_{field.field_name}')
        
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        # Write rows
        for contact in contacts:
            row = {
                'id': contact.id,
                'first_name': contact.first_name,
                'last_name': contact.last_name or '',
                'email': contact.email or '',
                'phone': contact.phone or '',
                'whatsapp_phone': contact.whatsapp_phone or '',
                'role': contact.role or '',
                'job_title': contact.job_title or '',
                'lead_score': contact.lead_score,
                'company_id': contact.company_id or '',
                'company_name': contact.company.name if contact.company else '',
                'created_at': contact.created_at.isoformat() if contact.created_at else '',
                'updated_at': contact.updated_at.isoformat() if contact.updated_at else ''
            }
            
            # Add custom field values
            custom_values = ContactService.get_custom_field_values(
                workspace_id, 'contact', contact.id
            )
            for field in custom_fields:
                row[f'custom_{field.field_name}'] = custom_values.get(field.field_name, '')
            
            writer.writerow(row)
        
        return output.getvalue()
    
    @staticmethod
    def import_contacts_csv(workspace_id: int, csv_content: str, user_id: int) -> Tuple[int, int, List[str]]:
        """
        Import contacts from CSV.
        
        Args:
            workspace_id: Workspace ID
            csv_content: CSV content as string
            user_id: User performing the import
        
        Returns:
            Tuple[int, int, List[str]]: (created_count, skipped_count, errors)
        """
        import csv
        from io import StringIO
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        try:
            reader = csv.DictReader(StringIO(csv_content))
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Validate required fields
                    if not row.get('first_name') or not row['first_name'].strip():
                        errors.append(f"Row {row_num}: First name is required")
                        skipped_count += 1
                        continue
                    
                    # Check for duplicates
                    email = row.get('email', '').strip() or None
                    phone = row.get('phone', '').strip() or None
                    
                    if email or phone:
                        duplicates = ContactService.find_duplicates(workspace_id, email, phone)
                        if duplicates:
                            errors.append(f"Row {row_num}: Duplicate contact found (email: {email}, phone: {phone})")
                            skipped_count += 1
                            continue
                    
                    # Find company by name if provided
                    company_id = None
                    company_name = row.get('company_name', '').strip()
                    if company_name:
                        company = Company.query.filter_by(
                            workspace_id=workspace_id,
                            name=company_name,
                            is_deleted=False,
                        ).first()
                        if company:
                            company_id = company.id
                        else:
                            errors.append(f"Row {row_num}: Company '{company_name}' not found, contact created without company")
                    
                    # Build contact data
                    contact_data = {
                        'first_name': row['first_name'].strip(),
                        'last_name': row.get('last_name', '').strip() or None,
                        'email': email,
                        'phone': phone,
                        'whatsapp_phone': row.get('whatsapp_phone', '').strip() or None,
                        'role': row.get('role', '').strip() or None,
                        'job_title': row.get('job_title', '').strip() or None,
                        'company_id': company_id
                    }
                    
                    # Extract custom fields (columns starting with 'custom_')
                    custom_fields = {}
                    for key, value in row.items():
                        if key.startswith('custom_') and value:
                            field_name = key[7:]  # Remove 'custom_' prefix
                            custom_fields[field_name] = value.strip()
                    
                    if custom_fields:
                        contact_data['custom_fields'] = custom_fields
                    
                    # Create contact
                    contact = ContactService.create_contact(workspace_id, contact_data, user_id)
                    
                    # Calculate and update lead score
                    lead_score = ContactService.calculate_lead_score(contact)
                    contact.lead_score = lead_score
                    db.session.commit()
                    
                    created_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    skipped_count += 1
                    db.session.rollback()
                    continue
            
            logger.info(f"CSV import completed: {created_count} created, {skipped_count} skipped")
            
        except Exception as e:
            errors.append(f"CSV parsing error: {str(e)}")
            logger.error(f"CSV import failed: {str(e)}")
        
        return created_count, skipped_count, errors
    
    @staticmethod
    def export_companies_csv(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> str:
        """
        Export companies to CSV format.
        
        Args:
            workspace_id: Workspace ID
            filters: Optional filters to apply
        
        Returns:
            str: CSV content as string
        """
        import csv
        from io import StringIO
        
        companies = ContactService.get_companies(workspace_id, filters)
        
        # Get all custom fields for companies
        custom_fields = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type='company'
        ).all()
        
        output = StringIO()
        
        # Build header
        headers = [
            'id', 'name', 'industry', 'size', 'website', 'phone', 'address',
            'parent_company_id', 'parent_company_name', 'created_at', 'updated_at'
        ]
        
        # Add custom field headers
        for field in custom_fields:
            headers.append(f'custom_{field.field_name}')
        
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        # Write rows
        for company in companies:
            row = {
                'id': company.id,
                'name': company.name,
                'industry': company.industry or '',
                'size': company.size or '',
                'website': company.website or '',
                'phone': company.phone or '',
                'address': company.address or '',
                'parent_company_id': company.parent_company_id or '',
                'parent_company_name': company.parent_company.name if company.parent_company else '',
                'created_at': company.created_at.isoformat() if company.created_at else '',
                'updated_at': company.updated_at.isoformat() if company.updated_at else ''
            }
            
            # Add custom field values
            custom_values = ContactService.get_custom_field_values(
                workspace_id, 'company', company.id
            )
            for field in custom_fields:
                row[f'custom_{field.field_name}'] = custom_values.get(field.field_name, '')
            
            writer.writerow(row)
        
        return output.getvalue()
