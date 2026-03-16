"""
Test suite for Task Management API
Tests task CRUD, dependencies, milestones, comments, and attachments
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, db
from models import User, Workspace
from models_crm import Task, TaskDependency, Milestone, TaskComment, Company
from datetime import datetime, timedelta
import json


class TestTasksAPI:
    """Test task management endpoints"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            
            # Create test workspace
            workspace = Workspace(company_name='Test Workspace')
            db.session.add(workspace)
            db.session.flush()
            
            # Create test user
            user = User(
                name='Test User',
                email='test@example.com',
                workspace_id=workspace.id,
                password_hash='dummy_hash'
            )
            db.session.add(user)
            
            # Create test company
            company = Company(
                workspace_id=workspace.id,
                name='Test Company',
                industry='Technology'
            )
            db.session.add(company)
            
            db.session.commit()
            
            cls.workspace_id = workspace.id
            cls.user_id = user.id
            cls.company_id = company.id
    
    @classmethod
    def teardown_class(cls):
        """Cleanup test environment"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def login(self):
        """Login test user"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
    
    def test_create_task(self):
        """Test creating a new task"""
        self.login()
        
        response = self.client.post('/api/v1/tasks', 
            json={
                'title': 'Test Task',
                'description': 'Test description',
                'priority': 'high',
                'status': 'not_started',
                'company_id': self.company_id,
                'is_customer_facing': True
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['title'] == 'Test Task'
        assert data['priority'] == 'high'
        assert data['is_customer_facing'] == True
        
        # Verify in database
        with app.app_context():
            task = Task.query.filter_by(title='Test Task').first()
            assert task is not None
            assert task.workspace_id == self.workspace_id
    
    def test_list_tasks(self):
        """Test listing tasks with filters"""
        self.login()
        
        # Create test tasks
        with app.app_context():
            task1 = Task(
                workspace_id=self.workspace_id,
                title='Task 1',
                priority='high',
                status='not_started',
                company_id=self.company_id
            )
            task2 = Task(
                workspace_id=self.workspace_id,
                title='Task 2',
                priority='low',
                status='completed',
                company_id=self.company_id
            )
            db.session.add_all([task1, task2])
            db.session.commit()
        
        # Test without filters
        response = self.client.get('/api/v1/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['tasks']) >= 2
        
        # Test with status filter
        response = self.client.get('/api/v1/tasks?status=completed')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert all(t['status'] == 'completed' for t in data['tasks'])
        
        # Test with priority filter
        response = self.client.get('/api/v1/tasks?priority=high')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert all(t['priority'] == 'high' for t in data['tasks'])
    
    def test_get_task(self):
        """Test getting task details"""
        self.login()
        
        with app.app_context():
            task = Task(
                workspace_id=self.workspace_id,
                title='Detail Task',
                description='Test description',
                priority='medium',
                status='in_progress'
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        response = self.client.get(f'/api/v1/tasks/{task_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Detail Task'
        assert data['status'] == 'in_progress'
        assert 'dependencies' in data
        assert 'can_start' in data
    
    def test_update_task(self):
        """Test updating a task"""
        self.login()
        
        with app.app_context():
            task = Task(
                workspace_id=self.workspace_id,
                title='Update Task',
                status='not_started'
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        response = self.client.patch(f'/api/v1/tasks/{task_id}',
            json={
                'title': 'Updated Task',
                'status': 'completed',
                'priority': 'urgent'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated Task'
        assert data['status'] == 'completed'
        assert data['priority'] == 'urgent'
        assert data['completed_at'] is not None
    
    def test_delete_task(self):
        """Test deleting a task"""
        self.login()
        
        with app.app_context():
            task = Task(
                workspace_id=self.workspace_id,
                title='Delete Task'
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        response = self.client.delete(f'/api/v1/tasks/{task_id}')
        assert response.status_code == 200
        
        # Verify deleted
        with app.app_context():
            task = Task.query.get(task_id)
            assert task is None
    
    def test_task_dependencies(self):
        """Test adding and removing task dependencies"""
        self.login()
        
        with app.app_context():
            task1 = Task(workspace_id=self.workspace_id, title='Task 1')
            task2 = Task(workspace_id=self.workspace_id, title='Task 2')
            db.session.add_all([task1, task2])
            db.session.commit()
            task1_id = task1.id
            task2_id = task2.id
        
        # Add dependency: task2 depends on task1
        response = self.client.post(f'/api/v1/tasks/{task2_id}/dependencies',
            json={'depends_on_task_id': task1_id}
        )
        assert response.status_code == 201
        
        # Verify dependency exists
        response = self.client.get(f'/api/v1/tasks/{task2_id}')
        data = json.loads(response.data)
        assert len(data['dependencies']) == 1
        assert data['dependencies'][0]['id'] == task1_id
        assert data['can_start'] == False  # task1 not completed
        
        # Complete task1
        self.client.patch(f'/api/v1/tasks/{task1_id}',
            json={'status': 'completed'}
        )
        
        # Check task2 can now start
        response = self.client.get(f'/api/v1/tasks/{task2_id}')
        data = json.loads(response.data)
        assert data['can_start'] == True
        
        # Remove dependency
        response = self.client.delete(f'/api/v1/tasks/{task2_id}/dependencies/{task1_id}')
        assert response.status_code == 200
        
        # Verify removed
        response = self.client.get(f'/api/v1/tasks/{task2_id}')
        data = json.loads(response.data)
        assert len(data['dependencies']) == 0
    
    def test_circular_dependency_prevention(self):
        """Test that circular dependencies are prevented"""
        self.login()
        
        with app.app_context():
            task1 = Task(workspace_id=self.workspace_id, title='Task A')
            task2 = Task(workspace_id=self.workspace_id, title='Task B')
            task3 = Task(workspace_id=self.workspace_id, title='Task C')
            db.session.add_all([task1, task2, task3])
            db.session.commit()
            task1_id = task1.id
            task2_id = task2.id
            task3_id = task3.id
        
        # Create chain: task2 -> task1, task3 -> task2
        self.client.post(f'/api/v1/tasks/{task2_id}/dependencies',
            json={'depends_on_task_id': task1_id}
        )
        self.client.post(f'/api/v1/tasks/{task3_id}/dependencies',
            json={'depends_on_task_id': task2_id}
        )
        
        # Try to create circular: task1 -> task3 (should fail)
        response = self.client.post(f'/api/v1/tasks/{task1_id}/dependencies',
            json={'depends_on_task_id': task3_id}
        )
        assert response.status_code == 400
    
    def test_milestones(self):
        """Test milestone creation and progress calculation"""
        self.login()
        
        # Create milestone
        response = self.client.post('/api/v1/milestones',
            json={
                'name': 'Q1 Launch',
                'company_id': self.company_id,
                'due_date': (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        milestone_id = data['id']
        assert data['name'] == 'Q1 Launch'
        
        # Create tasks for milestone
        with app.app_context():
            task1 = Task(
                workspace_id=self.workspace_id,
                title='Milestone Task 1',
                milestone_id=milestone_id,
                status='completed'
            )
            task2 = Task(
                workspace_id=self.workspace_id,
                title='Milestone Task 2',
                milestone_id=milestone_id,
                status='in_progress'
            )
            task3 = Task(
                workspace_id=self.workspace_id,
                title='Milestone Task 3',
                milestone_id=milestone_id,
                status='not_started'
            )
            db.session.add_all([task1, task2, task3])
            db.session.commit()
        
        # Get milestone with progress
        response = self.client.get(f'/api/v1/milestones/{milestone_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['progress']['total_tasks'] == 3
        assert data['progress']['completed_tasks'] == 1
        assert data['progress']['progress_percentage'] == 33.33
        
        # List milestones
        response = self.client.get('/api/v1/milestones')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['milestones']) >= 1
        
        # Update milestone
        response = self.client.patch(f'/api/v1/milestones/{milestone_id}',
            json={'name': 'Q1 Launch Updated'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Q1 Launch Updated'
    
    def test_task_comments(self):
        """Test adding and retrieving task comments"""
        self.login()
        
        with app.app_context():
            task = Task(workspace_id=self.workspace_id, title='Comment Task')
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        # Add comment
        response = self.client.post(f'/api/v1/tasks/{task_id}/comments',
            json={'content': 'This is a test comment'}
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['content'] == 'This is a test comment'
        assert data['user_id'] == self.user_id
        
        # Get comments
        response = self.client.get(f'/api/v1/tasks/{task_id}/comments')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['comments']) == 1
        assert data['comments'][0]['content'] == 'This is a test comment'
    
    def test_task_template(self):
        """Test creating tasks from template"""
        self.login()
        
        template_tasks = [
            {
                'title': 'Setup Environment',
                'description': 'Setup dev environment',
                'priority': 'high',
                'days_offset': 0,
                'depends_on_index': None
            },
            {
                'title': 'Write Code',
                'description': 'Implement features',
                'priority': 'medium',
                'days_offset': 3,
                'depends_on_index': 0
            },
            {
                'title': 'Testing',
                'description': 'Run tests',
                'priority': 'high',
                'days_offset': 7,
                'depends_on_index': 1
            }
        ]
        
        response = self.client.post('/api/v1/tasks/from-template',
            json={
                'template_tasks': template_tasks,
                'company_id': self.company_id
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert len(data['tasks']) == 3
        
        # Verify dependencies were created
        task2_id = data['tasks'][1]['id']
        response = self.client.get(f'/api/v1/tasks/{task2_id}')
        task_data = json.loads(response.data)
        assert len(task_data['dependencies']) == 1
        
        task3_id = data['tasks'][2]['id']
        response = self.client.get(f'/api/v1/tasks/{task3_id}')
        task_data = json.loads(response.data)
        assert len(task_data['dependencies']) == 1
    
    def test_customer_facing_filter(self):
        """Test filtering customer-facing tasks"""
        self.login()
        
        with app.app_context():
            task1 = Task(
                workspace_id=self.workspace_id,
                title='Internal Task',
                company_id=self.company_id,
                is_customer_facing=False
            )
            task2 = Task(
                workspace_id=self.workspace_id,
                title='Customer Task',
                company_id=self.company_id,
                is_customer_facing=True
            )
            db.session.add_all([task1, task2])
            db.session.commit()
        
        # Filter customer-facing only
        response = self.client.get('/api/v1/tasks?is_customer_facing=true')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert all(t['is_customer_facing'] for t in data['tasks'])
        assert any(t['title'] == 'Customer Task' for t in data['tasks'])
    
    def test_workspace_isolation(self):
        """Test that tasks are isolated by workspace"""
        self.login()
        
        # Create another workspace and task
        with app.app_context():
            other_workspace = Workspace(company_name='Other Workspace')
            db.session.add(other_workspace)
            db.session.flush()
            
            other_task = Task(
                workspace_id=other_workspace.id,
                title='Other Workspace Task'
            )
            db.session.add(other_task)
            db.session.commit()
            other_task_id = other_task.id
        
        # Try to access other workspace's task
        response = self.client.get(f'/api/v1/tasks/{other_task_id}')
        assert response.status_code == 404
        
        # List tasks should not include other workspace
        response = self.client.get('/api/v1/tasks')
        data = json.loads(response.data)
        assert not any(t['title'] == 'Other Workspace Task' for t in data['tasks'])


if __name__ == '__main__':
    # Simple test runner without pytest
    test = TestTasksAPI()
    test.setup_class()
    
    tests = [
        ('test_create_task', test.test_create_task),
        ('test_list_tasks', test.test_list_tasks),
        ('test_get_task', test.test_get_task),
        ('test_update_task', test.test_update_task),
        ('test_delete_task', test.test_delete_task),
        ('test_task_dependencies', test.test_task_dependencies),
        ('test_circular_dependency_prevention', test.test_circular_dependency_prevention),
        ('test_milestones', test.test_milestones),
        ('test_task_comments', test.test_task_comments),
        ('test_task_template', test.test_task_template),
        ('test_customer_facing_filter', test.test_customer_facing_filter),
        ('test_workspace_isolation', test.test_workspace_isolation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f'Running {test_name}...', end=' ')
            test_func()
            print('✓ PASSED')
            passed += 1
        except AssertionError as e:
            print(f'✗ FAILED: {e}')
            failed += 1
        except Exception as e:
            print(f'✗ ERROR: {e}')
            failed += 1
    
    test.teardown_class()
    
    print(f'\n{passed} passed, {failed} failed')
    exit(0 if failed == 0 else 1)
