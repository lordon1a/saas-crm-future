"""
Bug Condition Exploration Test for Import Duplicate Check

**Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.4**

Property 1: Email-Based Duplicate Check
For any CSV row where email address exists and is not empty, 
the execute_import() function SHALL check duplicates ONLY by email address
and SHALL NOT check by name. Records with same name but different emails
should be imported as separate records.

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
Expected counterexample: Second record with different email is incorrectly skipped
due to name match fallback in lines 772-777 of routes/import_wizard.py.

Test Strategy: Scoped PBT approach - concrete failing cases to ensure reproducibility.
"""

import unittest
import os
import sys
import tempfile
import pandas as pd
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models_crm import Contact, Company, Workspace
from models import User


class TestBugConditionEmailDuplicateCheck(unittest.TestCase):
    """
    Bug Condition Exploration: Email-Based Duplicate Check
    
    Tests the bug where same name + different email records are incorrectly
    marked as duplicates due to fallback name check in unfixed code.
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
    
    def create_csv_file(self, data):
        """Helper to create temporary CSV file"""
        df = pd.DataFrame(data)
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.csv',
            delete=False,
            newline='',
            encoding='utf-8'
        )
        df.to_csv(temp_file.name, index=False)
        temp_file.close()
        return temp_file.name
    
    def test_same_name_different_email_should_import_both(self):
        """
        Test Case 1: Same Name, Different Emails
        
        Bug Condition: When CSV contains "Ahmet Yılmaz" with ahmet@firma1.com
        and "Ahmet Yılmaz" with ahmet@firma2.com, both should be imported.
        
        UNFIXED CODE: Second record will be skipped (bug)
        FIXED CODE: Both records will be imported (correct)
        
        This test encodes the EXPECTED behavior and will FAIL on unfixed code.
        """
        # Prepare CSV data with same name, different emails
        csv_data = {
            'first_name': ['Ahmet', 'Ahmet'],
            'last_name': ['Yılmaz', 'Yılmaz'],
            'email': ['ahmet@firma1.com', 'ahmet@firma2.com'],
            'phone': ['+905551234567', '+905557654321']
        }
        
        csv_file = self.create_csv_file(csv_data)
        
        try:
            # Upload file
            with open(csv_file, 'rb') as f:
                response = self.client.post(
                    '/import_wizard/upload',
                    data={'file': (f, 'test.csv')},
                    content_type='multipart/form-data'
                )
            
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            file_id = result['file_id']
            
            # Execute import with skip duplicate action
            import_response = self.client.post(
                '/import_wizard/execute',
                json={
                    'file_id': file_id,
                    'object_type': 'contacts',
                    'field_mapping': {
                        'first_name': 'first_name',
                        'last_name': 'last_name',
                        'email': 'email',
                        'phone': 'phone'
                    },
                    'duplicate_action': 'skip'
                }
            )
            
            self.assertEqual(import_response.status_code, 200)
            import_result = import_response.get_json()
            
            # EXPECTED BEHAVIOR: Both records should be imported
            # Different emails = different contacts, even with same name
            self.assertEqual(
                import_result['imported_count'], 
                2,
                f"Expected 2 records imported (different emails), "
                f"got {import_result['imported_count']}. "
                f"Skipped: {import_result.get('skipped_count', 0)}. "
                f"BUG: Second record incorrectly skipped due to name match fallback."
            )
            
            self.assertEqual(
                import_result.get('skipped_count', 0),
                0,
                f"Expected 0 records skipped, got {import_result.get('skipped_count', 0)}. "
                f"COUNTEREXAMPLE: Record with email=ahmet@firma2.com was incorrectly "
                f"marked as duplicate due to name match in lines 772-777."
            )
            
            # Verify both contacts exist in database
            contacts = Contact.query.filter_by(
                workspace_id=1,
                first_name='Ahmet',
                last_name='Yılmaz',
                is_deleted=False
            ).all()
            
            self.assertEqual(
                len(contacts),
                2,
                f"Expected 2 contacts in DB, found {len(contacts)}. "
                f"BUG CONFIRMED: Name-based duplicate check triggered for email records."
            )
            
            # Verify emails are different
            emails = sorted([c.email for c in contacts])
            self.assertEqual(
                emails,
                ['ahmet@firma1.com', 'ahmet@firma2.com'],
                f"Expected both emails in DB, found {emails}"
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(csv_file):
                os.unlink(csv_file)
    
    def test_multiple_same_names_different_emails(self):
        """
        Test Case 2: Multiple Same Names, Different Emails
        
        Bug Condition: 3 "Mehmet Demir" records with different emails.
        All 3 should be imported as separate contacts.
        
        UNFIXED CODE: Only first record imported, 2 skipped (bug)
        FIXED CODE: All 3 records imported (correct)
        """
        # Prepare CSV with 3 same-name records, different emails
        csv_data = {
            'first_name': ['Mehmet'] * 3,
            'last_name': ['Demir'] * 3,
            'email': [f'mehmet{i}@firma.com' for i in range(1, 4)],
            'phone': [f'+90555000{i:04d}' for i in range(1, 4)]
        }
        
        csv_file = self.create_csv_file(csv_data)
        
        try:
            # Upload file
            with open(csv_file, 'rb') as f:
                response = self.client.post(
                    '/import_wizard/upload',
                    data={'file': (f, 'test.csv')},
                    content_type='multipart/form-data'
                )
            
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            file_id = result['file_id']
            
            # Execute import
            import_response = self.client.post(
                '/import_wizard/execute',
                json={
                    'file_id': file_id,
                    'object_type': 'contacts',
                    'field_mapping': {
                        'first_name': 'first_name',
                        'last_name': 'last_name',
                        'email': 'email',
                        'phone': 'phone'
                    },
                    'duplicate_action': 'skip'
                }
            )
            
            self.assertEqual(import_response.status_code, 200)
            import_result = import_response.get_json()
            
            # EXPECTED: All 3 records imported (different emails)
            self.assertEqual(
                import_result['imported_count'],
                3,
                f"Expected 3 records imported, got {import_result['imported_count']}. "
                f"Skipped: {import_result.get('skipped_count', 0)}. "
                f"COUNTEREXAMPLE: {import_result.get('skipped_count', 0)} records "
                f"incorrectly skipped due to name match fallback."
            )
            
            self.assertEqual(
                import_result.get('skipped_count', 0),
                0,
                f"Expected 0 skipped, got {import_result.get('skipped_count', 0)}. "
                f"BUG: After first 'Mehmet Demir' imported, subsequent records with "
                f"different emails incorrectly matched by name (lines 772-777)."
            )
            
        finally:
            if os.path.exists(csv_file):
                os.unlink(csv_file)
    
    def test_existing_contact_same_name_new_email(self):
        """
        Test Case 3: Existing Contact + New Record with Same Name, Different Email
        
        Bug Condition: DB has "Ali Veli" (ali@x.com), CSV has "Ali Veli" (ali@y.com).
        New record should be imported (different email = different person).
        
        UNFIXED CODE: New record skipped (bug)
        FIXED CODE: New record imported (correct)
        """
        # Create existing contact
        existing = Contact(
            workspace_id=1,
            first_name='Ali',
            last_name='Veli',
            email='ali@x.com',
            phone='+905551111111',
            is_deleted=False
        )
        db.session.add(existing)
        db.session.commit()
        
        # Prepare CSV with same name, different email
        csv_data = {
            'first_name': ['Ali'],
            'last_name': ['Veli'],
            'email': ['ali@y.com'],
            'phone': ['+905552222222']
        }
        
        csv_file = self.create_csv_file(csv_data)
        
        try:
            # Upload and import
            with open(csv_file, 'rb') as f:
                response = self.client.post(
                    '/import_wizard/upload',
                    data={'file': (f, 'test.csv')},
                    content_type='multipart/form-data'
                )
            
            result = response.get_json()
            file_id = result['file_id']
            
            import_response = self.client.post(
                '/import_wizard/execute',
                json={
                    'file_id': file_id,
                    'object_type': 'contacts',
                    'field_mapping': {
                        'first_name': 'first_name',
                        'last_name': 'last_name',
                        'email': 'email',
                        'phone': 'phone'
                    },
                    'duplicate_action': 'skip'
                }
            )
            
            import_result = import_response.get_json()
            
            # EXPECTED: 1 new record imported (different email)
            self.assertEqual(
                import_result['imported_count'],
                1,
                f"Expected 1 new record imported, got {import_result['imported_count']}. "
                f"COUNTEREXAMPLE: ali@y.com incorrectly matched to existing ali@x.com "
                f"by name (lines 772-777)."
            )
            
            self.assertEqual(
                import_result.get('skipped_count', 0),
                0,
                f"Expected 0 skipped, got {import_result.get('skipped_count', 0)}. "
                f"BUG: Email check failed (ali@y.com not in DB), then name check "
                f"incorrectly matched existing 'Ali Veli' record."
            )
            
            # Verify 2 contacts exist
            contacts = Contact.query.filter_by(
                workspace_id=1,
                first_name='Ali',
                last_name='Veli',
                is_deleted=False
            ).all()
            
            self.assertEqual(len(contacts), 2, f"Expected 2 contacts, found {len(contacts)}")
            
            emails = sorted([c.email for c in contacts])
            self.assertEqual(emails, ['ali@x.com', 'ali@y.com'])
            
        finally:
            if os.path.exists(csv_file):
                os.unlink(csv_file)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
