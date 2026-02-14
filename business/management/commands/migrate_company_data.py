from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Manually migrates data from business app to company app tables to resolve migration conflicts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-all',
            action='store_true',
            help='Delete all company data from both source and target tables',
        )

    def handle(self, *args, **kwargs):
        if kwargs['delete_all']:
            self.stdout.write("Deleting ALL company data from source and target tables...")
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys = OFF;")
                cursor.execute("DELETE FROM company_review;")
                cursor.execute("DELETE FROM company_report;")
                cursor.execute("DELETE FROM company_company_followers;")
                cursor.execute("DELETE FROM company_company;")
                cursor.execute("DELETE FROM business_review;")
                cursor.execute("DELETE FROM business_report;")
                cursor.execute("DELETE FROM business_company_followers;")
                cursor.execute("DELETE FROM business_company;")
                cursor.execute("PRAGMA foreign_keys = ON;")
            self.stdout.write(self.style.SUCCESS("All company data deleted."))
            return

        self.stdout.write("Starting manual data migration...")
        
        tables_map = [
            ('business_region', 'company_region'),
            ('business_district', 'company_district'),
            ('business_company', 'company_company'),
            ('business_review', 'company_review'),
            ('business_report', 'company_report'),
        ]

        with connection.cursor() as cursor:
            # Disable foreign keys to prevent constraint errors during insertion
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            for source, target in tables_map:
                try:
                    # Check if source table exists
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{source}';")
                    if not cursor.fetchone():
                        self.stdout.write(self.style.WARNING(f"Source table {source} does not exist. Skipping."))
                        continue

                    # Check if target table exists
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{target}';")
                    if not cursor.fetchone():
                        self.stdout.write(self.style.WARNING(f"Target table {target} does not exist. Skipping."))
                        continue

                    # Clear target table first to ensure clean state and avoid duplicates
                    self.stdout.write(f"Clearing target table {target}...")
                    cursor.execute(f"DELETE FROM {target}")

                    self.stdout.write(f"Copying data from {source} to {target}...")
                    
                    if target == 'company_company':
                        # Only copy companies where the user actually exists
                        cursor.execute(f"INSERT INTO {target} SELECT * FROM {source} WHERE user_id IN (SELECT id FROM auth_user)")
                    elif target in ['company_review', 'company_report']:
                        # Only copy reviews/reports where both user and company exist
                        cursor.execute(f"INSERT INTO {target} SELECT * FROM {source} WHERE user_id IN (SELECT id FROM auth_user) AND company_id IN (SELECT id FROM company_company)")
                    else:
                        cursor.execute(f"INSERT INTO {target} SELECT * FROM {source}")

                    # Fix empty strings in foreign keys which cause IntegrityError
                    if target == 'company_company':
                        self.stdout.write("Fixing empty strings in foreign keys for company_company...")
                        cursor.execute(f"UPDATE {target} SET region_id = NULL WHERE region_id = '';")
                        cursor.execute(f"UPDATE {target} SET district_id = NULL WHERE district_id = '';")

                        # Ensure no orphaned companies exist (fixes IntegrityError on user_id)
                        self.stdout.write("Removing orphaned company records...")
                        cursor.execute(f"DELETE FROM {target} WHERE user_id NOT IN (SELECT id FROM auth_user)")

                    if target in ['company_review', 'company_report']:
                        self.stdout.write(f"Removing orphaned {target} records...")
                        cursor.execute(f"DELETE FROM {target} WHERE company_id NOT IN (SELECT id FROM company_company)")

                    self.stdout.write(self.style.SUCCESS(f"Successfully copied data to {target}."))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error copying {source} to {target}: {e}"))

            # Handle M2M Followers table separately due to potential column differences or naming
            try:
                source = 'business_company_followers'
                target = 'company_company_followers'
                
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{source}';")
                src_exists = cursor.fetchone()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{target}';")
                tgt_exists = cursor.fetchone()

                if src_exists and tgt_exists:
                    self.stdout.write(f"Clearing target table {target}...")
                    cursor.execute(f"DELETE FROM {target}")
                    
                    self.stdout.write(f"Copying data from {source} to {target}...")
                    cursor.execute(f"INSERT INTO {target} (company_id, user_id) SELECT company_id, user_id FROM {source} WHERE company_id IN (SELECT id FROM company_company) AND user_id IN (SELECT id FROM auth_user)")
                    self.stdout.write(self.style.SUCCESS(f"Successfully copied data to {target}."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error copying followers: {e}"))

            cursor.execute("PRAGMA foreign_keys = ON;")
            
        self.stdout.write(self.style.SUCCESS("Manual data migration finished. You can now run 'python manage.py migrate'."))