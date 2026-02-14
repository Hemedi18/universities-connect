from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fixes bad data in DecimalFields causing SQLite errors'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            self.stdout.write('Cleaning bad decimal data...')
            
            # Fix price (cannot be NULL, set to 0)
            cursor.execute("UPDATE business_item SET price = '0' WHERE price = '' OR price IS NULL")
            
            # Fix compare_at_price (set to NULL)
            cursor.execute("UPDATE business_item SET compare_at_price = NULL WHERE compare_at_price = ''")
            
            # Fix shipping_weight (set to NULL)
            cursor.execute("UPDATE business_item SET shipping_weight = NULL WHERE shipping_weight = ''")
            
        self.stdout.write(self.style.SUCCESS('Successfully cleaned item data.'))