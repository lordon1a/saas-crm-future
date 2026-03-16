"""
Seed script for task management data
Creates sample tasks, milestones, and dependencies for testing
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, db
from models import User, Workspace
from models_crm import Task, Milestone, TaskDependency, TaskComment, Company
from datetime import datetime, timedelta


def seed_tasks():
    """Seed task management data"""
    with app.app_context():
        print("Seeding task management data...")
        
        # Get first workspace and user
        workspace = Workspace.query.first()
        if not workspace:
            print("No workspace found. Please run seed_crm_data.py first.")
            return
        
        user = User.query.filter_by(workspace_id=workspace.id).first()
        if not user:
            print("No user found. Please create a user first.")
            return
        
        company = Company.query.filter_by(workspace_id=workspace.id).first()
        if not company:
            print("No company found. Please run seed_crm_data.py first.")
            return
        
        # Create milestones
        milestones = [
            Milestone(
                workspace_id=workspace.id,
                name='Q1 Product Launch',
                company_id=company.id,
                due_date=datetime.utcnow() + timedelta(days=90),
                status='active'
            ),
            Milestone(
                workspace_id=workspace.id,
                name='Customer Onboarding',
                company_id=company.id,
                due_date=datetime.utcnow() + timedelta(days=30),
                status='active'
            ),
            Milestone(
                workspace_id=workspace.id,
                name='System Integration',
                company_id=company.id,
                due_date=datetime.utcnow() + timedelta(days=60),
                status='active'
            )
        ]
        
        for milestone in milestones:
            db.session.add(milestone)
        
        db.session.flush()
        print(f"Created {len(milestones)} milestones")
        
        # Create tasks for Q1 Product Launch
        launch_tasks = [
            Task(
                workspace_id=workspace.id,
                title='Requirements Gathering',
                description='Collect and document all product requirements',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='completed',
                priority='high',
                due_date=datetime.utcnow() - timedelta(days=10),
                is_customer_facing=False,
                completed_at=datetime.utcnow() - timedelta(days=8)
            ),
            Task(
                workspace_id=workspace.id,
                title='Design Mockups',
                description='Create UI/UX designs for new features',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='completed',
                priority='high',
                due_date=datetime.utcnow() - timedelta(days=5),
                is_customer_facing=False,
                completed_at=datetime.utcnow() - timedelta(days=3)
            ),
            Task(
                workspace_id=workspace.id,
                title='Backend Development',
                description='Implement API endpoints and business logic',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='in_progress',
                priority='urgent',
                due_date=datetime.utcnow() + timedelta(days=15),
                is_customer_facing=False
            ),
            Task(
                workspace_id=workspace.id,
                title='Frontend Development',
                description='Build user interface components',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='not_started',
                priority='high',
                due_date=datetime.utcnow() + timedelta(days=20),
                is_customer_facing=False
            ),
            Task(
                workspace_id=workspace.id,
                title='Testing & QA',
                description='Comprehensive testing of all features',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='not_started',
                priority='high',
                due_date=datetime.utcnow() + timedelta(days=30),
                is_customer_facing=False
            ),
            Task(
                workspace_id=workspace.id,
                title='Product Launch',
                description='Deploy to production and announce',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[0].id,
                status='not_started',
                priority='urgent',
                due_date=datetime.utcnow() + timedelta(days=40),
                is_customer_facing=True
            )
        ]
        
        for task in launch_tasks:
            db.session.add(task)
        
        db.session.flush()
        
        # Create task dependencies
        dependencies = [
            (launch_tasks[1].id, launch_tasks[0].id),  # Design depends on Requirements
            (launch_tasks[2].id, launch_tasks[1].id),  # Backend depends on Design
            (launch_tasks[3].id, launch_tasks[1].id),  # Frontend depends on Design
            (launch_tasks[4].id, launch_tasks[2].id),  # Testing depends on Backend
            (launch_tasks[4].id, launch_tasks[3].id),  # Testing depends on Frontend
            (launch_tasks[5].id, launch_tasks[4].id),  # Launch depends on Testing
        ]
        
        for task_id, depends_on_id in dependencies:
            dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id)
            db.session.add(dep)
        
        print(f"Created {len(launch_tasks)} tasks with {len(dependencies)} dependencies")
        
        # Create tasks for Customer Onboarding
        onboarding_tasks = [
            Task(
                workspace_id=workspace.id,
                title='Initial Consultation',
                description='Meet with customer to understand needs',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[1].id,
                status='completed',
                priority='high',
                due_date=datetime.utcnow() - timedelta(days=5),
                is_customer_facing=True,
                completed_at=datetime.utcnow() - timedelta(days=4)
            ),
            Task(
                workspace_id=workspace.id,
                title='Account Setup',
                description='Create customer accounts and configure settings',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[1].id,
                status='in_progress',
                priority='high',
                due_date=datetime.utcnow() + timedelta(days=3),
                is_customer_facing=True
            ),
            Task(
                workspace_id=workspace.id,
                title='Training Session',
                description='Provide product training to customer team',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[1].id,
                status='not_started',
                priority='medium',
                due_date=datetime.utcnow() + timedelta(days=10),
                is_customer_facing=True
            ),
            Task(
                workspace_id=workspace.id,
                title='Go-Live Support',
                description='Provide support during initial usage',
                assignee_id=user.id,
                company_id=company.id,
                milestone_id=milestones[1].id,
                status='not_started',
                priority='high',
                due_date=datetime.utcnow() + timedelta(days=15),
                is_customer_facing=True
            )
        ]
        
        for task in onboarding_tasks:
            db.session.add(task)
        
        db.session.flush()
        print(f"Created {len(onboarding_tasks)} onboarding tasks")
        
        # Add comments to some tasks
        comments = [
            TaskComment(
                task_id=launch_tasks[2].id,
                user_id=user.id,
                content='Making good progress on the API endpoints. Should be done by end of week.'
            ),
            TaskComment(
                task_id=launch_tasks[2].id,
                user_id=user.id,
                content='Need to discuss authentication approach with the team.'
            ),
            TaskComment(
                task_id=onboarding_tasks[1].id,
                user_id=user.id,
                content='Customer requested additional user accounts. Adding 5 more.'
            )
        ]
        
        for comment in comments:
            db.session.add(comment)
        
        print(f"Created {len(comments)} task comments")
        
        db.session.commit()
        print("✓ Task management data seeded successfully!")
        
        # Print summary
        print("\nSummary:")
        print(f"  - Milestones: {len(milestones)}")
        print(f"  - Tasks: {len(launch_tasks) + len(onboarding_tasks)}")
        print(f"  - Dependencies: {len(dependencies)}")
        print(f"  - Comments: {len(comments)}")


if __name__ == '__main__':
    seed_tasks()
