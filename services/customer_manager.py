from models import db, Customer
from datetime import datetime

class CustomerManager:
    @staticmethod
    def get_or_create_customer(workspace_id, phone_number, profile_name=None):
        """Get existing customer or create new one for a specific workspace"""
        customer = Customer.query.filter_by(workspace_id=workspace_id, phone_number=phone_number).first()
        
        if customer:
            # Update profile name if provided and different
            if profile_name and customer.profile_name != profile_name:
                customer.profile_name = profile_name
                db.session.commit()
            return customer
        
        # Create new customer
        customer = Customer(
            workspace_id=workspace_id,
            phone_number=phone_number,
            profile_name=profile_name or phone_number
        )
        db.session.add(customer)
        db.session.commit()
        
        return customer
    
    @staticmethod
    def get_customer_by_phone(workspace_id, phone_number):
        """Get customer by phone number within a workspace"""
        return Customer.query.filter_by(workspace_id=workspace_id, phone_number=phone_number).first()
    
    @staticmethod
    def update_customer_profile(workspace_id, customer_id, profile_name):
        """Update customer profile name ensuring they belong to the given workspace"""
        customer = Customer.query.filter_by(id=customer_id, workspace_id=workspace_id).first()
        if not customer:
            raise ValueError(f"Customer with id {customer_id} not found in this workspace")
        
        customer.profile_name = profile_name
        db.session.commit()
        
        return customer
