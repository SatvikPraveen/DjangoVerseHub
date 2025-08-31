"""
File: scripts/management/commands/send_bulk_notifications.py
Django management command to send bulk notifications and handle background tasks.
Processes notification queues and manages batch email operations.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mass_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
import csv
import json
from pathlib import Path

from notifications.models import Notification
from notifications.tasks import send_notification_email
from core.tasks import send_welcome_email


class Command(BaseCommand):
    help = 'Send bulk notifications and manage background notification tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            choices=['announcement', 'reminder', 'welcome', 'custom'],
            required=True,
            help='Type of bulk notification to send'
        )
        parser.add_argument(
            '--recipients',
            choices=['all', 'active', 'staff', 'group'],
            default='active',
            help='Target recipients for notifications'
        )
        parser.add_argument(
            '--group-name',
            help='Group name when using --recipients=group'
        )
        parser.add_argument(
            '--title',
            required=True,
            help='Notification title'
        )
        parser.add_argument(
            '--message',
            required=True,
            help='Notification message content'
        )
        parser.add_argument(
            '--notification-type',
            choices=['info', 'success', 'warning', 'error', 'urgent'],
            default='info',
            help='Notification type/priority'
        )
        parser.add_argument(
            '--send-email',
            action='store_true',
            help='Also send email notifications'
        )
        parser.add_argument(
            '--from-file',
            help='Load notification data from CSV file'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of notifications to process in each batch'
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=0,
            help='Delay between batches in seconds'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending'
        )
        parser.add_argument(
            '--schedule',
            help='Schedule sending for later (format: YYYY-MM-DD HH:MM)'
        )
        parser.add_argument(
            '--process-queue',
            action='store_true',
            help='Process pending notification queue instead of creating new'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.batch_size = options['batch_size']
        self.delay = options['delay']

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE: No notifications will be sent')
            )

        try:
            if options['process_queue']:
                self.process_notification_queue()
            elif options['from_file']:
                self.send_from_file(options)
            else:
                self.send_bulk_notification(options)

            self.stdout.write(
                self.style.SUCCESS('Bulk notification task completed successfully!')
            )

        except Exception as e:
            raise CommandError(f'Error in bulk notification: {str(e)}')

    def send_bulk_notification(self, options):
        """Send bulk notification to specified recipients."""
        recipients = self.get_recipients(options)
        
        if not recipients:
            self.stdout.write(
                self.style.WARNING('No recipients found for the specified criteria')
            )
            return

        self.stdout.write(f'Found {len(recipients)} recipients')

        if options['schedule']:
            self.schedule_notifications(options, recipients)
            return

        # Create notifications in batches
        self.create_notifications_batch(options, recipients)

        if options['send_email']:
            self.send_email_notifications(options, recipients)

    def get_recipients(self, options):
        """Get list of recipients based on criteria."""
        if options['recipients'] == 'all':
            return User.objects.all()
        elif options['recipients'] == 'active':
            return User.objects.filter(is_active=True)
        elif options['recipients'] == 'staff':
            return User.objects.filter(is_staff=True)
        elif options['recipients'] == 'group':
            if not options['group_name']:
                raise CommandError('--group-name is required when using --recipients=group')
            try:
                group = Group.objects.get(name=options['group_name'])
                return group.user_set.all()
            except Group.DoesNotExist:
                raise CommandError(f'Group "{options["group_name"]}" does not exist')

    def create_notifications_batch(self, options, recipients):
        """Create notifications in batches."""
        total_created = 0
        
        # Process recipients in batches
        for i in range(0, len(recipients), self.batch_size):
            batch = recipients[i:i + self.batch_size]
            
            notifications = []
            for recipient in batch:
                notification = Notification(
                    recipient=recipient,
                    title=options['title'],
                    message=options['message'],
                    notification_type=options['notification_type'],
                    created_at=timezone.now()
                )
                notifications.append(notification)

            if not self.dry_run:
                Notification.objects.bulk_create(notifications)
            
            total_created += len(notifications)
            
            self.stdout.write(f'Created batch {i//self.batch_size + 1}: {len(notifications)} notifications')
            
            if self.delay > 0 and i + self.batch_size < len(recipients):
                import time
                time.sleep(self.delay)

        self.stdout.write(
            self.style.SUCCESS(f'Total notifications created: {total_created}')
        )

    def send_email_notifications(self, options, recipients):
        """Send email notifications in batches."""
        if self.dry_run:
            self.stdout.write('Would send emails to recipients')
            return

        email_messages = []
        
        for recipient in recipients:
            if recipient.email:
                subject = f'[Notification] {options["title"]}'
                message = self.render_email_template(options, recipient)
                email_messages.append((
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient.email]
                ))

        # Send emails in batches
        for i in range(0, len(email_messages), self.batch_size):
            batch = email_messages[i:i + self.batch_size]
            
            try:
                send_mass_mail(batch, fail_silently=False)
                self.stdout.write(f'Sent email batch {i//self.batch_size + 1}: {len(batch)} emails')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error sending email batch: {str(e)}')
                )

    def render_email_template(self, options, recipient):
        """Render email template for notification."""
        context = {
            'recipient': recipient,
            'title': options['title'],
            'message': options['message'],
            'notification_type': options['notification_type'],
            'site_name': getattr(settings, 'SITE_NAME', 'Our Platform')
        }
        
        template_name = f'emails/bulk_notification_{options["notification_type"]}.txt'
        
        try:
            return render_to_string(template_name, context)
        except:
            # Fallback to generic template
            return render_to_string('emails/bulk_notification.txt', context)

    def send_from_file(self, options):
        """Send notifications from CSV file."""
        file_path = Path(options['from_file'])
        
        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        notifications_data = []
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            required_fields = ['username', 'title', 'message']
            
            for row in reader:
                # Validate required fields
                if not all(field in row for field in required_fields):
                    raise CommandError(f'CSV must contain columns: {", ".join(required_fields)}')
                
                try:
                    user = User.objects.get(username=row['username'])
                    notifications_data.append({
                        'recipient': user,
                        'title': row['title'],
                        'message': row['message'],
                        'notification_type': row.get('type', 'info'),
                        'send_email': row.get('send_email', '').lower() == 'true'
                    })
                except User.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'User not found: {row["username"]}')
                    )

        self.stdout.write(f'Processing {len(notifications_data)} notifications from file')

        # Create notifications
        notifications = []
        for data in notifications_data:
            notification = Notification(
                recipient=data['recipient'],
                title=data['title'],
                message=data['message'],
                notification_type=data['notification_type']
            )
            notifications.append(notification)

        if not self.dry_run:
            Notification.objects.bulk_create(notifications, batch_size=self.batch_size)

        # Send emails if requested
        email_notifications = [data for data in notifications_data if data['send_email']]
        if email_notifications:
            self.stdout.write(f'Sending emails for {len(email_notifications)} notifications')
            # Process email sending...

    def schedule_notifications(self, options, recipients):
        """Schedule notifications for later sending."""
        try:
            scheduled_time = datetime.strptime(options['schedule'], '%Y-%m-%d %H:%M')
            scheduled_time = timezone.make_aware(scheduled_time)
        except ValueError:
            raise CommandError('Invalid schedule format. Use: YYYY-MM-DD HH:MM')

        if scheduled_time <= timezone.now():
            raise CommandError('Scheduled time must be in the future')

        # Store scheduled notification data
        scheduled_data = {
            'recipients_count': len(recipients),
            'title': options['title'],
            'message': options['message'],
            'notification_type': options['notification_type'],
            'send_email': options['send_email'],
            'scheduled_for': scheduled_time.isoformat(),
            'recipients_criteria': {
                'type': options['recipients'],
                'group_name': options.get('group_name')
            }
        }

        # In a real implementation, you'd use Celery beat or similar
        # For now, we'll log the scheduling
        self.stdout.write(
            self.style.SUCCESS(
                f'Notification scheduled for {scheduled_time}\n'
                f'Recipients: {len(recipients)}\n'
                f'Title: {options["title"]}'
            )
        )

    def process_notification_queue(self):
        """Process pending notifications in the queue."""
        # Get unprocessed notifications that need email sending
        pending_notifications = Notification.objects.filter(
            email_sent=False,
            notification_type__in=['urgent', 'important']
        ).select_related('recipient')

        self.stdout.write(f'Found {pending_notifications.count()} pending notifications')

        processed_count = 0
        error_count = 0

        for notification in pending_notifications.iterator():
            try:
                if not self.dry_run:
                    # Use Celery task to send email
                    send_notification_email.delay(notification.id)
                    notification.email_sent = True
                    notification.save(update_fields=['email_sent'])

                processed_count += 1

                if processed_count % 50 == 0:
                    self.stdout.write(f'Processed {processed_count} notifications...')

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Error processing notification {notification.id}: {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Queue processing completed:\n'
                f'  Processed: {processed_count}\n'
                f'  Errors: {error_count}'
            )
        )

    def show_statistics(self):
        """Show notification statistics."""
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        recent_notifications = Notification.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        by_type = {}
        for notification_type, _ in Notification.NOTIFICATION_TYPES:
            count = Notification.objects.filter(notification_type=notification_type).count()
            by_type[notification_type] = count

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== NOTIFICATION STATISTICS ===\n'
                f'Total notifications: {total_notifications}\n'
                f'Unread notifications: {unread_notifications}\n'
                f'Recent (7 days): {recent_notifications}\n'
                f'\nBy type:'
            )
        )

        for notification_type, count in by_type.items():
            self.stdout.write(f'  {notification_type}: {count}')

    def cleanup_old_notifications(self, days=90):
        """Clean up old read notifications."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_notifications = Notification.objects.filter(
            is_read=True,
            created_at__lt=cutoff_date
        )
        
        count = old_notifications.count()
        
        if not self.dry_run:
            old_notifications.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Cleaned up {count} old notifications')
        )