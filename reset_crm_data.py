"""
Reset CRM Data
Clears all CRM data and reseeds with fresh data
"""
from app import app
from models import db
from models_crm import Company, Contact, Deal, Activity, CustomField, CustomFieldValue

def reset_crm_data():
    """Clear all CRM data"""
    with app.app_context():
        print("🗑️  Clearing CRM data...")
        
        # Delete in correct order (respecting foreign keys)
        Activity.query.delete()
        print("  ✓ Cleared activities")
        
        CustomFieldValue.query.delete()
        print("  ✓ Cleared custom field values")
        
        CustomField.query.delete()
        print("  ✓ Cleared custom fields")
        
        Deal.query.delete()
        print("  ✓ Cleared deals")
        
        Contact.query.delete()
        print("  ✓ Cleared contacts")
        
        Company.query.delete()
        print("  ✓ Cleared companies")
        
        db.session.commit()
        print("\n✅ CRM data cleared successfully!")

if __name__ == '__main__':
    reset_crm_data()
