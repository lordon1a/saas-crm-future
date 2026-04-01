"""
Form Service
Handles web form processing and submission logic.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


# Default form field types
FIELD_TYPES = ['text', 'email', 'tel', 'select', 'checkbox', 'textarea', 'number', 'date']


def create_web_form(
    workspace_id: int,
    name: str,
    created_by: int,
    fields_json: str,
    submit_action: str = 'create_contact',
    redirect_url: str = None,
    notify_user_id: int = None
):
    """Create a new web form."""
    from app import db
    from models_crm import WebForm
    
    form = WebForm(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        fields_json=fields_json,
        submit_action=submit_action,
        redirect_url=redirect_url,
        notify_user_id=notify_user_id
    )
    
    try:
        db.session.add(form)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    
    return form


def list_web_forms(workspace_id: int) -> List:
    """List all web forms for a workspace."""
    from models_crm import WebForm
    return WebForm.query.filter_by(
        workspace_id=workspace_id
    ).order_by(WebForm.created_at.desc()).all()


def get_web_form_by_id(form_id: int):
    """Get a web form by ID."""
    from models_crm import WebForm
    return WebForm.query.get(form_id)


def update_web_form(
    form_id: int,
    name: str = None,
    fields_json: str = None,
    submit_action: str = None,
    redirect_url: str = None,
    notify_user_id: int = None,
    is_active: bool = None
):
    """Update a web form."""
    from app import db
    from models_crm import WebForm
    
    form = WebForm.query.get(form_id)
    if not form:
        return None
    
    if name is not None:
        form.name = name
    if fields_json is not None:
        form.fields_json = fields_json
    if submit_action is not None:
        form.submit_action = submit_action
    if redirect_url is not None:
        form.redirect_url = redirect_url
    if notify_user_id is not None:
        form.notify_user_id = notify_user_id
    if is_active is not None:
        form.is_active = is_active
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return form


def delete_web_form(form_id: int) -> bool:
    """Delete a web form."""
    from app import db
    from models_crm import WebForm
    
    form = WebForm.query.get(form_id)
    if not form:
        return False
    
    try:
        db.session.delete(form)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return True


def get_default_fields() -> List[Dict[str, Any]]:
    """Get default form fields template."""
    return [
        {
            'id': 'f1',
            'type': 'text',
            'label': 'Full Name',
            'field_map': 'name',
            'required': True,
            'placeholder': 'Enter your name'
        },
        {
            'id': 'f2',
            'type': 'email',
            'label': 'Email Address',
            'field_map': 'email',
            'required': True,
            'placeholder': 'Enter your email'
        },
        {
            'id': 'f3',
            'type': 'tel',
            'label': 'Phone Number',
            'field_map': 'phone',
            'required': False,
            'placeholder': 'Enter your phone'
        },
        {
            'id': 'f4',
            'type': 'textarea',
            'label': 'Message',
            'field_map': 'note',
            'required': False,
            'placeholder': 'How can we help you?'
        }
    ]


def validate_form_data(fields_json: str, submitted_data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate submitted form data against field definitions.
    Returns (is_valid, error_list).
    """
    errors = []
    
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError:
        return False, ['Invalid form configuration']
    
    for field in fields:
        field_id = field.get('id')
        field_label = field.get('label', field_id)
        required = field.get('required', False)
        field_type = field.get('type', 'text')
        
        # Check required fields
        if required and (field_id not in submitted_data or not submitted_data[field_id]):
            errors.append(f'{field_label} is required')
            continue
        
        # Type-specific validation
        value = submitted_data.get(field_id)
        if value:
            if field_type == 'email' and not is_valid_email(value):
                errors.append(f'{field_label} must be a valid email address')
            elif field_type == 'tel' and not is_valid_phone(value):
                errors.append(f'{field_label} must be a valid phone number')
    
    return len(errors) == 0, errors


def is_valid_email(email: str) -> bool:
    """Simple email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_phone(phone: str) -> bool:
    """Simple phone validation - allows digits, spaces, +, -, ()"""
    import re
    pattern = r'^[\d\s\+\-\(\)]{7,20}$'
    return bool(re.match(pattern, phone))


def process_submission(
    form_id: int,
    data_dict: Dict,
    ip_address: str = None,
    user_agent: str = None
) -> Tuple[bool, Optional[Any], List[str], Optional[str]]:
    """
    Process a form submission.
    Returns (success, contact, errors, redirect_url).
    """
    from app import db
    from models_crm import WebForm, FormSubmission, Contact, Activity
    
    form = WebForm.query.get(form_id)
    if not form or not form.is_active:
        return False, None, ['Form not found or inactive'], None
    
    # Validate data
    is_valid, errors = validate_form_data(form.fields_json, data_dict)
    if not is_valid:
        return False, None, errors, None
    
    # Find or create contact based on email
    email_field = get_field_by_map(form.fields_json, 'email')
    email = data_dict.get(email_field) if email_field else None
    
    name_field = get_field_by_map(form.fields_json, 'name')
    name = data_dict.get(name_field) if name_field else 'Unknown'
    
    contact = None
    if email:
        # Look for existing contact
        contact = Contact.query.filter_by(
            workspace_id=form.workspace_id,
            email=email.lower()
        ).first()
        
        if contact:
            # Update existing contact
            update_contact_from_form(contact, form.fields_json, data_dict)
        else:
            # Create new contact
            contact = create_contact_from_form(
                workspace_id=form.workspace_id,
                fields_json=form.fields_json,
                data_dict=data_dict,
                created_by=form.created_by
            )
    else:
        # No email - create contact with just name
        contact = Contact(
            workspace_id=form.workspace_id,
            name=name,
            created_by=form.created_by
        )
        try:
            db.session.add(contact)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    
    # Create form submission record
    submission = FormSubmission(
        form_id=form_id,
        workspace_id=form.workspace_id,
        data_json=json.dumps(data_dict),
        contact_id=contact.id if contact else None,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(submission)
    
    # Update submission count
    form.submission_count += 1
    
    # Create activity
    if contact:
        activity = Activity(
            workspace_id=form.workspace_id,
            contact_id=contact.id,
            activity_type='form_submitted',
            description=f'Form submitted: {form.name}',
            notes=json.dumps(data_dict, indent=2),
            user_id=form.created_by
        )
        db.session.add(activity)
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # Trigger workflows after successful persistence.
    if contact:
        _trigger_form_submitted_workflow(
            workspace_id=form.workspace_id,
            contact_id=contact.id,
            form=form,
            data_dict=data_dict,
        )
    
    # Send notification if configured
    if form.notify_user_id:
        send_form_notification(form, contact, data_dict)
    
    return True, contact, [], form.redirect_url


def get_field_by_map(fields_json: str, field_map: str) -> Optional[str]:
    """Get the field ID that maps to a specific contact field."""
    try:
        fields = json.loads(fields_json)
        for field in fields:
            if field.get('field_map') == field_map:
                return field.get('id')
    except json.JSONDecodeError:
        pass
    return None


def update_contact_from_form(contact, fields_json: str, data_dict: Dict):
    """Update contact fields from form data."""
    from app import db
    
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError:
        return
    
    # Map form fields to contact fields
    field_mappings = {
        'name': 'name',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'email': 'email',
        'phone': 'phone',
        'company': 'company_name',
        'title': 'job_title',
        'note': 'note'
    }
    
    for field in fields:
        field_id = field.get('id')
        field_map = field.get('field_map')
        
        if field_id in data_dict and field_map in field_mappings:
            value = data_dict[field_id]
            contact_attr = field_mappings[field_map]
            
            if hasattr(contact, contact_attr) and value:
                setattr(contact, contact_attr, value)
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def create_contact_from_form(
    workspace_id: int,
    fields_json: str,
    data_dict: Dict,
    created_by: int = None
):
    """Create a new contact from form data."""
    from app import db
    from models_crm import Contact
    
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError:
        fields = []
    
    # Build contact data
    contact_data = {
        'workspace_id': workspace_id,
        'created_by': created_by
    }
    
    field_mappings = {
        'name': 'name',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'email': 'email',
        'phone': 'phone',
        'company': 'company_name',
        'title': 'job_title'
    }
    
    for field in fields:
        field_id = field.get('id')
        field_map = field.get('field_map')
        
        if field_id in data_dict and field_map in field_mappings:
            value = data_dict[field_id]
            contact_attr = field_mappings[field_map]
            if value:
                contact_data[contact_attr] = value
    
    # Ensure we have at least a name
    if 'name' not in contact_data and 'email' in contact_data:
        contact_data['name'] = contact_data['email'].split('@')[0]
    
    contact = Contact(**contact_data)
    try:
        db.session.add(contact)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    
    return contact


def send_form_notification(form, contact, data_dict):
    """Send notification to the configured user about new form submission."""
    from flask import current_app
    from models import User
    from services.email_hub_service import EmailHubService
    
    try:
        if not form.notify_user_id:
            return
        
        user = User.query.get(form.notify_user_id)
        if not user or not user.email:
            return
        
        subject = f'New Form Submission: {form.name}'
        
        # Build notification body
        contact_name = contact.name if contact else 'Unknown'
        contact_email = contact.email if contact else 'N/A'
        
        body = f"""
New form submission received!

Form: {form.name}
Contact: {contact_name}
Email: {contact_email}

Submitted Data:
"""
        for field_id, value in data_dict.items():
            body += f"- {field_id}: {value}\n"
        
        body += f"""
---
Submitted at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {data_dict.get('_ip', 'N/A')}
"""
        
        EmailHubService.queue_outbound_email(
            workspace_id=form.workspace_id,
            user_id=form.notify_user_id,
            to_email=user.email,
            subject=subject,
            body_text=body.strip(),
            body_html=None,
            contact_id=contact.id if contact else None
        )
    except Exception as e:
        current_app.logger.error(f"Failed to send form notification: {e}")


def _trigger_form_submitted_workflow(workspace_id: int, contact_id: int, form, data_dict: Dict):
    """Trigger workflow event for form submissions in best-effort mode."""
    from flask import current_app
    from services.workflow_service import WorkflowService

    try:
        WorkflowService.trigger_event(
            workspace_id=workspace_id,
            trigger_type='form_submitted',
            entity_type='contact',
            entity_id=contact_id,
            context={
                'form_id': form.id,
                'form_name': form.name,
                'submit_action': form.submit_action,
                'submission_data': data_dict,
            },
        )
    except Exception as exc:
        current_app.logger.warning(f"Form submitted workflow trigger failed: {exc}")


def list_form_submissions(form_id: int, page: int = 1, per_page: int = 50) -> Tuple[List, int]:
    """List submissions for a form with pagination."""
    from models_crm import FormSubmission
    
    query = FormSubmission.query.filter_by(form_id=form_id).order_by(FormSubmission.created_at.desc())
    
    total = query.count()
    submissions = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return submissions, total


def get_embed_code(form_id: int) -> str:
    """Get the embed code for a form."""
    return f'<script src="/static/form-embed.js" data-form-id="{form_id}"></script>'


def get_form_for_public(form_id: int):
    """Get an active form for public display."""
    from models_crm import WebForm
    form = WebForm.query.filter_by(id=form_id, is_active=True).first()
    return form
