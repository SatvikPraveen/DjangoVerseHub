"""
File: scripts/management/commands/cleanup_unused_media.py
Django management command to clean up unused media files.
Identifies and removes orphaned media files that are no longer referenced by any models.
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.apps import apps
from django.db import models
from django.core.files.storage import default_storage
from collections import defaultdict
import mimetypes
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Clean up unused media files that are no longer referenced by any models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting files'
        )
        parser.add_argument(
            '--older-than',
            type=int,
            default=30,
            help='Only delete files older than N days (default: 30)'
        )
        parser.add_argument(
            '--file-types',
            nargs='+',
            default=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx'],
            help='File extensions to consider for cleanup'
        )
        parser.add_argument(
            '--exclude-dirs',
            nargs='+',
            default=['admin', 'cache'],
            help='Directories to exclude from cleanup'
        )
        parser.add_argument(
            '--min-size',
            type=int,
            help='Only delete files larger than N bytes'
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Ask for confirmation before deleting each file'
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Only show statistics without cleaning up'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.older_than_days = options['older_than']
        self.file_types = [ext.lower() for ext in options['file_types']]
        self.exclude_dirs = options['exclude_dirs']
        self.min_size = options['min_size']
        self.interactive = options['interactive']
        self.stats_only = options['stats_only']

        self.stdout.write(
            self.style.SUCCESS('Starting media files cleanup...')
        )

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE: No files will be actually deleted')
            )

        try:
            # Collect all media file references from database
            referenced_files = self.get_referenced_files()
            
            # Get all files in media directory
            all_media_files = self.get_all_media_files()
            
            # Find unused files
            unused_files = self.find_unused_files(referenced_files, all_media_files)
            
            # Filter files by criteria
            filtered_files = self.filter_files(unused_files)
            
            # Show statistics
            self.show_statistics(all_media_files, referenced_files, unused_files, filtered_files)
            
            if not self.stats_only and filtered_files:
                # Clean up files
                self.cleanup_files(filtered_files)
            
            self.stdout.write(
                self.style.SUCCESS('Media cleanup completed successfully!')
            )

        except Exception as e:
            raise CommandError(f'Error during media cleanup: {str(e)}')

    def get_referenced_files(self):
        """Get all file references from database models."""
        referenced_files = set()
        
        self.stdout.write('Scanning database for file references...')
        
        # Iterate through all models
        for model in apps.get_models():
            # Find FileField and ImageField
            file_fields = []
            for field in model._meta.get_fields():
                if isinstance(field, (models.FileField, models.ImageField)):
                    file_fields.append(field.name)
            
            if file_fields:
                self.stdout.write(f'  Checking {model._meta.label}...')
                
                # Query all instances and collect file paths
                for instance in model.objects.all().iterator():
                    for field_name in file_fields:
                        file_field = getattr(instance, field_name)
                        if file_field and file_field.name:
                            referenced_files.add(file_field.name)
        
        self.stdout.write(
            self.style.SUCCESS(f'Found {len(referenced_files)} referenced files')
        )
        
        return referenced_files

    def get_all_media_files(self):
        """Get all files in the media directory."""
        media_files = []
        
        self.stdout.write('Scanning media directory...')
        
        media_root = Path(settings.MEDIA_ROOT)
        
        if not media_root.exists():
            self.stdout.write(
                self.style.ERROR(f'Media root does not exist: {media_root}')
            )
            return media_files
        
        for root, dirs, files in os.walk(media_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(media_root)
                
                # Convert to forward slashes for consistency with Django
                relative_path_str = str(relative_path).replace('\\', '/')
                
                media_files.append({
                    'path': relative_path_str,
                    'full_path': file_path,
                    'size': file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime),
                    'extension': file_path.suffix.lower().lstrip('.')
                })
        
        self.stdout.write(
            self.style.SUCCESS(f'Found {len(media_files)} files in media directory')
        )
        
        return media_files

    def find_unused_files(self, referenced_files, all_media_files):
        """Find files that are not referenced in the database."""
        unused_files = []
        
        for file_info in all_media_files:
            if file_info['path'] not in referenced_files:
                unused_files.append(file_info)
        
        self.stdout.write(
            self.style.WARNING(f'Found {len(unused_files)} unused files')
        )
        
        return unused_files

    def filter_files(self, unused_files):
        """Filter files based on command line criteria."""
        filtered_files = []
        cutoff_date = datetime.now() - timedelta(days=self.older_than_days)
        
        for file_info in unused_files:
            # Check file extension
            if self.file_types and file_info['extension'] not in self.file_types:
                continue
            
            # Check age
            if file_info['modified'] > cutoff_date:
                continue
            
            # Check minimum size
            if self.min_size and file_info['size'] < self.min_size:
                continue
            
            filtered_files.append(file_info)
        
        return filtered_files

    def show_statistics(self, all_files, referenced_files, unused_files, filtered_files):
        """Display cleanup statistics."""
        total_size = sum(f['size'] for f in all_files)
        unused_size = sum(f['size'] for f in unused_files)
        filtered_size = sum(f['size'] for f in filtered_files)
        
        # File type breakdown
        file_types = defaultdict(lambda: {'count': 0, 'size': 0})
        for file_info in filtered_files:
            ext = file_info['extension'] or 'no_extension'
            file_types[ext]['count'] += 1
            file_types[ext]['size'] += file_info['size']
        
        self.stdout.write(
            self.style.SUCCESS('\n=== CLEANUP STATISTICS ===')
        )
        self.stdout.write(f'Total files in media directory: {len(all_files)}')
        self.stdout.write(f'Total media size: {self.format_size(total_size)}')
        self.stdout.write(f'Referenced files: {len(referenced_files)}')
        self.stdout.write(f'Unused files: {len(unused_files)}')
        self.stdout.write(f'Unused size: {self.format_size(unused_size)}')
        self.stdout.write(f'Files to be cleaned (after filters): {len(filtered_files)}')
        self.stdout.write(f'Size to be freed: {self.format_size(filtered_size)}')
        
        if file_types:
            self.stdout.write('\n=== FILES BY TYPE ===')
            for ext, info in sorted(file_types.items()):
                self.stdout.write(
                    f'{ext}: {info["count"]} files, {self.format_size(info["size"])}'
                )

    def cleanup_files(self, files_to_delete):
        """Delete the unused files."""
        if not files_to_delete:
            self.stdout.write('No files to delete.')
            return
        
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        self.stdout.write(f'\nProcessing {len(files_to_delete)} files...')
        
        for file_info in files_to_delete:
            file_path = file_info['full_path']
            
            # Interactive confirmation
            if self.interactive:
                response = input(f'Delete {file_path}? [y/N]: ')
                if response.lower() not in ['y', 'yes']:
                    continue
            
            try:
                if not self.dry_run:
                    # Delete the file
                    if default_storage.exists(file_info['path']):
                        default_storage.delete(file_info['path'])
                    elif file_path.exists():
                        file_path.unlink()
                
                deleted_count += 1
                deleted_size += file_info['size']
                
                if deleted_count % 50 == 0:
                    self.stdout.write(f'  Deleted {deleted_count} files...')
                    
            except Exception as e:
                errors.append(f'Error deleting {file_path}: {str(e)}')
                continue
        
        # Cleanup empty directories
        if not self.dry_run:
            self.cleanup_empty_directories()
        
        # Show results
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== CLEANUP RESULTS ===\n'
                f'Deleted files: {deleted_count}\n'
                f'Space freed: {self.format_size(deleted_size)}\n'
                f'Errors: {len(errors)}'
            )
        )
        
        if errors:
            self.stdout.write(self.style.ERROR('\nERRORS:'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  {error}'))

    def cleanup_empty_directories(self):
        """Remove empty directories in media root."""
        media_root = Path(settings.MEDIA_ROOT)
        
        for root, dirs, files in os.walk(media_root, topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    if not any(dir_path.iterdir()):  # Directory is empty
                        dir_path.rmdir()
                        self.stdout.write(f'Removed empty directory: {dir_path}')
                except (OSError, PermissionError):
                    pass  # Directory not empty or permission denied

    def format_size(self, size_bytes):
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"