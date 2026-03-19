"""
Bug Condition Exploration Test for Drag-and-Drop Save

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

Property 1: Bug Condition - Drag-and-Drop Sıralama Kaydedilmemesi

For any drag-and-drop event where a contact or company is moved to a new position,
the UNFIXED system SHALL NOT save the new display_order values to the database,
the reorder API endpoints SHALL NOT exist (404), and the ordering SHALL NOT persist
after page refresh.

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
Expected counterexamples:
- display_order field does not exist in Contact/Company models
- POST /api/v1/contacts/reorder returns 404 Not Found
- POST /api/v1/companies/reorder returns 404 Not Found
- After simulated drag-drop, no backend API call can be made
- After page refresh, order reverts to original (alphabetical or creation date)

Test Strategy: Scoped PBT approach - concrete failing cases to ensure reproducibility.
"""

import unittest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models_crm import Contact, Company
from models import User, Workspace
from sqlalchemy import inspect


class TestBugConditionDragDropSave(unittest.TestCase):
    """
    Bug Condition Exploration: Drag-and-Drop Sıralama Kaydedilmemesi
    
    Tests the bug where drag-and-drop reordering works visually in frontend
    but changes are not saved to database because:
    1. display_order field doesn't exist in models
    2. Backend reorder API endpoints don't exist
    3. Frontend doesn't send reorder requests to backend
    """
    
    def setUp(self):
        """Set up test environment with clean database"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create all tables
        db.create_all()
        
        # Create test workspace
        self.workspace = Workspace(
            id=1,
            name='Test Workspace',
            subdomain='test'
        )
        db.session.add(self.workspace)
        
        # Create test user
        self.user = User(
            id=1,
            username='testuser',
            email='test@example.com',
            workspace_id=1
        )
        db.session.add(self.user)
        db.session.commit()
        
        # Set up session
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['workspace_id'] = 1
    
    def tearDown(self):
        """Clean up test environment"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_models_missing_display_order_field(self):
        """
        Test Case 1: Contact and Company Models Missing display_order Field
        
        Bug Condition: Models don't have display_order field.
        Without this field, user-defined ordering cannot be stored.
        
        UNFIXED CODE: display_order field doesn't exist (bug)
        FIXED CODE: display_order field exists (correct)
        """
        # Inspect Contact model columns
        inspector = inspect(db.engine)
        contact_columns = [col['name'] for col in inspector.get_columns('contacts')]
        company_columns = [col['name'] for col in inspector.get_columns('companies')]
        
        # EXPECTED BEHAVIOR: display_order field should exist in both models
        self.assertIn(
            'display_order',
            contact_columns,
            f"COUNTEREXAMPLE: Contact model missing 'display_order' field. "
            f"BUG CONFIRMED: Cannot store user-defined ordering."
        )
        
        self.assertIn(
            'display_order',
            company_columns,
            f"COUNTEREXAMPLE: Company model missing 'display_order' field. "
            f"BUG CONFIRMED: Cannot store user-defined ordering."
        )
    
    def test_reorder_endpoints_missing(self):
        """
        Test Case 2: POST /api/v1/contacts/reorder and companies/reorder Endpoints Missing
        
        Bug Condition: Backend doesn't have reorder endpoints.
        Without these endpoints, frontend cannot send new ordering to backend.
        
        UNFIXED CODE: Endpoints return 404 Not Found (bug)
        FIXED CODE: Endpoints return 200 OK (correct)
        """
        # Test contacts reorder endpoint
        response1 = self.client.post(
            '/api/v1/contacts/reorder',
            json={'contact_ids': [1, 2, 3]},
            content_type='application/json'
        )
        
        # Test companies reorder endpoint
        response2 = self.client.post(
            '/api/v1/companies/reorder',
            json={'company_ids': [1, 2, 3]},
            content_type='application/json'
        )
        
        # EXPECTED BEHAVIOR: Both endpoints should exist and return 200
        self.assertEqual(
            response1.status_code,
            200,
            f"COUNTEREXAMPLE: POST /api/v1/contacts/reorder returned {response1.status_code}. "
            f"BUG CONFIRMED: Reorder endpoint doesn't exist."
        )
        
        self.assertEqual(
            response2.status_code,
            200,
            f"COUNTEREXAMPLE: POST /api/v1/companies/reorder returned {response2.status_code}. "
            f"BUG CONFIRMED: Reorder endpoint doesn't exist."
        )
    
    def test_contact_drag_from_position_1_to_3_not_persisted(self):
        """
        Test Case 5: Contact Drag from Position 1 to 3 Not Persisted
        
        Bug Condition: User drags contact from position 1 to position 3.
        Visual reordering happens in frontend, but database is not updated.
        
        UNFIXED CODE: display_order not updated in DB (bug)
        FIXED CODE: display_order updated in DB (correct)
        """
        # Create 3 test contacts (reduced from 5 for faster execution)
        contacts = []
        for i in range(1, 4):
            contact = Contact(
                workspace_id=1,
                first_name=f'Contact{i}',
                last_name='Test',
                email=f'contact{i}@test.com',
                is_deleted=False
            )
            db.session.add(contact)
            contacts.append(contact)
        db.session.commit()
        
        # Get contact IDs
        contact_ids = [c.id for c in contacts]
        
        # Simulate drag-drop: move first contact to position 3
        # New order: [2, 3, 1]
        new_order = contact_ids[1:] + [contact_ids[0]]
        
        # Try to call reorder endpoint (will fail on unfixed code)
        response = self.client.post(
            '/api/v1/contacts/reorder',
            json={'contact_ids': new_order},
            content_type='application/json'
        )
        
        # If endpoint exists, verify display_order was updated
        if response.status_code == 200:
            # Refresh contacts from DB
            db.session.expire_all()
            
            # EXPECTED BEHAVIOR: Contacts should have display_order matching new_order
            for idx, contact_id in enumerate(new_order):
                contact = Contact.query.get(contact_id)
                
                # Check if display_order field exists and is set correctly
                self.assertTrue(
                    hasattr(contact, 'display_order'),
                    f"COUNTEREXAMPLE: Contact model has no 'display_order' attribute. "
                    f"BUG CONFIRMED: Cannot verify ordering without this field."
                )
                
                self.assertEqual(
                    contact.display_order,
                    idx,
                    f"COUNTEREXAMPLE: Contact {contact_id} expected display_order={idx}, "
                    f"got {contact.display_order}. "
                    f"BUG CONFIRMED: Reorder endpoint didn't update display_order in DB."
                )
        else:
            # Endpoint doesn't exist - this is the expected bug condition
            self.fail(
                f"COUNTEREXAMPLE: POST /api/v1/contacts/reorder returned {response.status_code}. "
                f"BUG CONFIRMED: Cannot save drag-drop ordering without backend endpoint."
            )
    
    def test_company_drag_from_position_2_to_1_not_persisted(self):
        """
        Test Case 6: Company Drag from Position 2 to 1 Not Persisted
        
        Bug Condition: User drags company from position 2 to position 1.
        Visual reordering happens in frontend, but database is not updated.
        
        UNFIXED CODE: display_order not updated in DB (bug)
        FIXED CODE: display_order updated in DB (correct)
        """
        # Create 3 test companies (reduced from 5 for faster execution)
        companies = []
        for i in range(1, 4):
            company = Company(
                workspace_id=1,
                name=f'Company{i}',
                is_deleted=False
            )
            db.session.add(company)
            companies.append(company)
        db.session.commit()
        
        # Get company IDs
        company_ids = [c.id for c in companies]
        
        # Simulate drag-drop: move second company to position 1
        # New order: [2, 1, 3]
        new_order = [company_ids[1], company_ids[0], company_ids[2]]
        
        # Try to call reorder endpoint (will fail on unfixed code)
        response = self.client.post(
            '/api/v1/companies/reorder',
            json={'company_ids': new_order},
            content_type='application/json'
        )
        
        # If endpoint exists, verify display_order was updated
        if response.status_code == 200:
            # Refresh companies from DB
            db.session.expire_all()
            
            # EXPECTED BEHAVIOR: Companies should have display_order matching new_order
            for idx, company_id in enumerate(new_order):
                company = Company.query.get(company_id)
                
                # Check if display_order field exists and is set correctly
                self.assertTrue(
                    hasattr(company, 'display_order'),
                    f"COUNTEREXAMPLE: Company model has no 'display_order' attribute. "
                    f"BUG CONFIRMED: Cannot verify ordering without this field."
                )
                
                self.assertEqual(
                    company.display_order,
                    idx,
                    f"COUNTEREXAMPLE: Company {company_id} expected display_order={idx}, "
                    f"got {company.display_order}. "
                    f"BUG CONFIRMED: Reorder endpoint didn't update display_order in DB."
                )
        else:
            # Endpoint doesn't exist - this is the expected bug condition
            self.fail(
                f"COUNTEREXAMPLE: POST /api/v1/companies/reorder returned {response.status_code}. "
                f"BUG CONFIRMED: Cannot save drag-drop ordering without backend endpoint."
            )
    
    def test_page_refresh_reverts_ordering(self):
        """
        Test Case 7: Page Refresh Reverts Ordering
        
        Bug Condition: After drag-drop reordering, page refresh (F5) causes
        items to revert to original order because changes weren't saved to DB.
        
        UNFIXED CODE: GET returns original order (bug)
        FIXED CODE: GET returns user-defined order (correct)
        """
        # Create 3 test contacts with specific names (alphabetical order)
        contacts_data = [
            ('Zeynep', 'Yılmaz'),  # Would be last alphabetically
            ('Ali', 'Demir'),      # Would be first alphabetically
            ('Mehmet', 'Kaya')     # Would be middle alphabetically
        ]
        
        created_contacts = []
        for first_name, last_name in contacts_data:
            contact = Contact(
                workspace_id=1,
                first_name=first_name,
                last_name=last_name,
                email=f'{first_name.lower()}@test.com',
                is_deleted=False
            )
            db.session.add(contact)
            created_contacts.append(contact)
        db.session.commit()
        
        # Get initial order from API (simulates page load)
        response1 = self.client.get('/api/v1/contacts')
        self.assertEqual(response1.status_code, 200)
        initial_data = response1.get_json()
        initial_order = [c['id'] for c in initial_data['contacts']]
        
        # Simulate drag-drop: reverse the order
        new_order = list(reversed(initial_order))
        
        # Try to save new order via reorder endpoint
        reorder_response = self.client.post(
            '/api/v1/contacts/reorder',
            json={'contact_ids': new_order},
            content_type='application/json'
        )
        
        # Simulate page refresh: GET contacts again
        response2 = self.client.get('/api/v1/contacts')
        self.assertEqual(response2.status_code, 200)
        after_refresh_data = response2.get_json()
        after_refresh_order = [c['id'] for c in after_refresh_data['contacts']]
        
        # EXPECTED BEHAVIOR: Order should persist after refresh
        self.assertEqual(
            after_refresh_order,
            new_order,
            f"COUNTEREXAMPLE: After drag-drop and page refresh, order reverted. "
            f"Initial order: {initial_order}, "
            f"New order: {new_order}, "
            f"After refresh: {after_refresh_order}. "
            f"BUG CONFIRMED: Ordering not persisted to database. "
            f"Reorder endpoint status: {reorder_response.status_code}."
        )


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
