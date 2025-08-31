"""
File: scripts/management/commands/generate_demo_data.py
Django management command to generate demo data for development and testing.
Creates realistic sample data including users, profiles, and notifications.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.utils import timezone
from faker import Faker
import random
from datetime import timedelta

from accounts.models import UserProfile
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Generate demo data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=50,
            help='Number of users to create (default: 50)'
        )
        parser.add_argument(
            '--notifications',
            type=int,
            default=200,
            help='Number of notifications to create (default: 200)'
        )
        parser.add_argument(
            '--admin',
            action='store_true',
            help='Create admin users'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before creating new'
        )
        parser.add_argument(
            '--seed',
            type=int,
            help='Random seed for reproducible data generation'
        )

    def handle(self, *args, **options):
        fake = Faker()
        
        # Set random seed if provided
        if options['seed']:
            Faker.seed(options['seed'])
            random.seed(options['seed'])

        self.stdout.write(
            self.style.SUCCESS('Starting demo data generation...')
        )

        try:
            with transaction.atomic():
                if options['clear']:
                    self.clear_demo_data()

                # Create user groups
                user_groups = self.create_user_groups()

                # Create regular users
                users = self.create_users(fake, options['users'], user_groups)

                # Create admin users if requested
                if options['admin']:
                    admin_users = self.create_admin_users(fake)
                    users.extend(admin_users)

                # Create notifications
                self.create_notifications(fake, users, options['notifications'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created demo data:\n'
                        f'  - {len(users)} users\n'
                        f'  - {options["notifications"]} notifications\n'
                        f'  - {len(user_groups)} user groups'
                    )
                )

        except Exception as e:
            raise CommandError(f'Error generating demo data: {str(e)}')

    def clear_demo_data(self):
        """Clear existing demo data."""
        self.stdout.write('Clearing existing demo data...')
        
        # Delete users created by this script (excluding superusers)
        demo_users = User.objects.filter(
            is_superuser=False,
            email__contains='example.com'
        )
        
        notifications_count = Notification.objects.filter(
            recipient__in=demo_users
        ).count()
        
        users_count = demo_users.count()
        
        # Delete notifications first (foreign key constraint)
        Notification.objects.filter(recipient__in=demo_users).delete()
        demo_users.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Cleared {users_count} users and {notifications_count} notifications'
            )
        )

    def create_user_groups(self):
        """Create user groups for demo data."""
        groups_data = [
            ('Editors', 'Content editors'),
            ('Moderators', 'Community moderators'),
            ('Premium Users', 'Premium subscription users'),
            ('Beta Testers', 'Beta feature testers'),
        ]
        
        groups = []
        for name, description in groups_data:
            group, created = Group.objects.get_or_create(name=name)
            groups.append(group)
            if created:
                self.stdout.write(f'Created group: {name}')
        
        return groups

    def create_users(self, fake, count, groups):
        """Create regular demo users with profiles."""
        users = []
        
        self.stdout.write(f'Creating {count} users...')
        
        for i in range(count):
            # Generate user data
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f'{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}'
            email = fake.email()
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='demo123',  # Same password for all demo users
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                date_joined=fake.date_time_between(
                    start_date='-2y', 
                    end_date='now', 
                    tzinfo=timezone.get_current_timezone()
                )
            )
            
            # Update user profile
            profile = user.userprofile
            profile.bio = fake.paragraph(nb_sentences=3)
            profile.location = fake.city()
            profile.birth_date = fake.date_of_birth(
                tzinfo=None, 
                minimum_age=18, 
                maximum_age=80
            )
            profile.phone_number = fake.phone_number()
            profile.website = fake.url() if random.choice([True, False]) else ''
            profile.save()
            
            # Add to random groups
            user_groups = random.sample(groups, k=random.randint(0, 2))
            for group in user_groups:
                user.groups.add(group)
            
            users.append(user)
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f'  Created {i + 1} users...')
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {count} regular users')
        )
        
        return users

    def create_admin_users(self, fake):
        """Create admin users for demo purposes."""
        admin_users = []
        
        # Create staff user
        staff_user = User.objects.create_user(
            username='staff_demo',
            email='staff@example.com',
            password='demo123',
            first_name='Staff',
            last_name='User',
            is_staff=True,
            is_active=True
        )
        
        profile = staff_user.userprofile
        profile.bio = 'Demo staff user for testing administrative features.'
        profile.save()
        
        admin_users.append(staff_user)
        
        # Create manager user
        manager_user = User.objects.create_user(
            username='manager_demo',
            email='manager@example.com',
            password='demo123',
            first_name='Manager',
            last_name='User',
            is_staff=True,
            is_active=True
        )
        
        # Add to moderator group
        moderator_group, _ = Group.objects.get_or_create(name='Moderators')
        manager_user.groups.add(moderator_group)
        
        profile = manager_user.userprofile
        profile.bio = 'Demo manager user with moderation privileges.'
        profile.save()
        
        admin_users.append(manager_user)
        
        self.stdout.write(
            self.style.SUCCESS('Created admin users')
        )
        
        return admin_users

    def create_notifications(self, fake, users, count):
        """Create demo notifications."""
        if not users:
            self.stdout.write(
                self.style.WARNING('No users available for notifications')
            )
            return
        
        self.stdout.write(f'Creating {count} notifications...')
        
        notification_types = ['info', 'success', 'warning', 'error', 'welcome', 'urgent']
        
        notification_templates = {
            'info': {
                'titles': [
                    'System Update Available',
                    'New Feature Released',
                    'Maintenance Scheduled',
                    'Policy Update'
                ],
                'messages': [
                    'A new system update is available for installation.',
                    'We\'ve released a new feature based on user feedback.',
                    'Scheduled maintenance will occur this weekend.',
                    'Please review our updated privacy policy.'
                ]
            },
            'success': {
                'titles': [
                    'Profile Updated Successfully',
                    'Payment Processed',
                    'Account Verified',
                    'Task Completed'
                ],
                'messages': [
                    'Your profile has been updated successfully.',
                    'Your payment has been processed successfully.',
                    'Your account has been verified.',
                    'Your requested task has been completed.'
                ]
            },
            'warning': {
                'titles': [
                    'Password Expiring Soon',
                    'Storage Almost Full',
                    'Unusual Activity Detected',
                    'Subscription Ending'
                ],
                'messages': [
                    'Your password will expire in 7 days.',
                    'Your storage is 90% full.',
                    'We detected unusual activity on your account.',
                    'Your subscription will end soon.'
                ]
            },
            'error': {
                'titles': [
                    'Login Failed',
                    'Payment Failed',
                    'Upload Error',
                    'Connection Issue'
                ],
                'messages': [
                    'Multiple failed login attempts detected.',
                    'Your payment could not be processed.',
                    'File upload failed due to size limit.',
                    'Connection to external service failed.'
                ]
            },
            'welcome': {
                'titles': [
                    'Welcome to Our Platform!',
                    'Getting Started',
                    'Your Account is Ready',
                    'Welcome Aboard!'
                ],
                'messages': [
                    'Welcome! We\'re excited to have you join us.',
                    'Here\'s how to get started with your new account.',
                    'Your account is now ready to use.',
                    'Welcome aboard! Let\'s explore what we can do together.'
                ]
            },
            'urgent': {
                'titles': [
                    'Security Alert',
                    'Account Suspended',
                    'Immediate Action Required',
                    'Critical System Error'
                ],
                'messages': [
                    'Immediate action required for your account security.',
                    'Your account has been temporarily suspended.',
                    'Please take immediate action to resolve this issue.',
                    'A critical error requires your attention.'
                ]
            }
        }
        
        notifications = []
        
        for i in range(count):
            user = random.choice(users)
            notification_type = random.choice(notification_types)
            templates = notification_templates[notification_type]
            
            title = random.choice(templates['titles'])
            message = random.choice(templates['messages'])
            
            # Add some variation to messages
            if random.choice([True, False]):
                message += f' Reference ID: {fake.uuid4()[:8].upper()}'
            
            notification = Notification(
                recipient=user,
                title=title,
                message=message,
                notification_type=notification_type,
                is_read=random.choices([True, False], weights=[0.3, 0.7])[0],
                created_at=fake.date_time_between(
                    start_date='-30d',
                    end_date='now',
                    tzinfo=timezone.get_current_timezone()
                ),
                email_sent=random.choices([True, False], weights=[0.2, 0.8])[0]
            )
            
            notifications.append(notification)
        
        # Bulk create notifications
        Notification.objects.bulk_create(notifications, batch_size=100)
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {count} notifications')
        )

    def create_sample_data_summary(self):
        """Display summary of created data."""
        total_users = User.objects.count()
        total_notifications = Notification.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDemo Data Summary:\n'
                f'  Total Users: {total_users}\n'
                f'  Active Users: {active_users}\n'
                f'  Total Notifications: {total_notifications}\n'
                f'  \nDemo Login Credentials:\n'
                f'  Username: any created username\n'
                f'  Password: demo123'
            )
        )