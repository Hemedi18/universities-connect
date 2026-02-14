from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from company.models import Company, Region, District
from business.models import Category, Item
import random
from datetime import time
from django.core.files.base import ContentFile
import urllib.request
import urllib.parse
import ssl

class Command(BaseCommand):
    help = 'Populates the database with realistic electronic company data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting population script...')

        # 1. Ensure Regions exist
        region, _ = Region.objects.get_or_create(name="Dar es Salaam")
        district, _ = District.objects.get_or_create(name="Kinondoni", region=region)

        # 2. Define the Tech Company
        company_data = {
            'username': 'tech_galaxy_admin',
            'password': 'password123',
            'email': 'admin@techgalaxy.com',
            'name': 'Tech Galaxy Tanzania',
            'desc': 'The #1 Premium Electronics Retailer in Tanzania. Authentic products, warranty included.',
            'address': 'Mlimani City Mall, Shop 42',
            'whatsapp': '255712345678'
        }

        self.stdout.write(f"Creating company: {company_data['name']}...")

        # Create User
        user, created = User.objects.get_or_create(username=company_data['username'], email=company_data['email'])
        user.set_password(company_data['password'])
        user.save()

        # Create Company Profile
        company, created = Company.objects.get_or_create(
            user=user,
            defaults={
                'name': company_data['name'],
                'description': company_data['desc'],
                'region': region,
                'district': district,
                'address': company_data['address'],
                'whatsapp_number': company_data['whatsapp'],
                'is_verified': True,
                'opening_time': time(9, 0),
                'closing_time': time(21, 0)
            }
        )

        # CLEANUP: Delete existing items to force re-download of images
        self.stdout.write("Deleting existing items for fresh population...")
        Item.objects.filter(seller=user).delete()

        # 3. Define 50 Real Electronic Products
        products = [
            ("iPhone 15 Pro Max", "Apple flagship phone, Titanium, 256GB", 3500000, "Electronics"),
            ("Samsung Galaxy S24 Ultra", "AI Phone, 200MP Camera, S-Pen", 3200000, "Electronics"),
            ("MacBook Pro 16 M3 Max", "Space Black, 32GB RAM, 1TB SSD", 7500000, "Electronics"),
            ("Dell XPS 13 Plus", "OLED Touch, Core i7, 16GB RAM", 4500000, "Electronics"),
            ("Sony WH-1000XM5", "Noise Cancelling Wireless Headphones", 850000, "Electronics"),
            ("iPad Pro 12.9 M2", "Liquid Retina XDR, 256GB, WiFi", 3200000, "Electronics"),
            ("Canon EOS R5", "8K Video, 45MP Full Frame Mirrorless", 9000000, "Electronics"),
            ("Logitech MX Master 3S", "Performance Wireless Mouse", 250000, "Electronics"),
            ("Apple Watch Ultra 2", "Rugged Titanium Case, Alpine Loop", 2200000, "Electronics"),
            ("Samsung Odyssey G9", "49-inch Curved Gaming Monitor", 3800000, "Electronics"),
            ("JBL Flip 6", "Portable Waterproof Speaker", 280000, "Electronics"),
            ("PlayStation 5 Slim", "1TB SSD, Disc Edition, White", 1500000, "Electronics"),
            ("Xbox Series X", "1TB SSD, 4K Gaming Console", 1400000, "Electronics"),
            ("Nintendo Switch OLED", "7-inch Screen, White Joy-Cons", 950000, "Electronics"),
            ("GoPro Hero 12 Black", "Action Camera, 5.3K Video", 1100000, "Electronics"),
            ("DJI Mini 4 Pro", "4K HDR Video Drone, Fly More Combo", 2800000, "Electronics"),
            ("Kindle Paperwhite", "16GB, 6.8-inch Display, Waterproof", 450000, "Electronics"),
            ("Bose QuietComfort Ultra", "Spatial Audio Earbuds", 750000, "Electronics"),
            ("Google Pixel 8 Pro", "Android 14, 50MP Camera, Obsidian", 2500000, "Electronics"),
            ("Asus ROG Zephyrus G14", "Gaming Laptop, RTX 4060", 4200000, "Electronics"),
            ("HP Spectre x360", "2-in-1 Laptop, OLED Display", 3800000, "Electronics"),
            ("Lenovo ThinkPad X1 Carbon", "Business Ultrabook, Carbon Fiber", 4800000, "Electronics"),
            ("Surface Pro 9", "Tablet Laptop, Core i7, 16GB", 3500000, "Electronics"),
            ("Galaxy Tab S9 Ultra", "14.6-inch AMOLED Tablet", 3100000, "Electronics"),
            ("Sony Alpha a7 IV", "33MP Mirrorless Camera Body", 6500000, "Electronics"),
            ("Nikon Z8", "Professional Mirrorless Camera", 10500000, "Electronics"),
            ("Fujifilm X-T5", "Retro 40MP Mirrorless Camera", 4500000, "Electronics"),
            ("Razer DeathAdder V3 Pro", "Ultra-lightweight Gaming Mouse", 350000, "Electronics"),
            ("Keychron Q1 Pro", "Custom Mechanical Keyboard", 550000, "Electronics"),
            ("LG C3 OLED TV 55", "4K Smart TV, 120Hz", 3500000, "Electronics"),
            ("Samsung The Frame 65", "Art Mode 4K QLED TV", 4200000, "Electronics"),
            ("Sonos Arc Soundbar", "Dolby Atmos Smart Soundbar", 2500000, "Electronics"),
            ("AirPods Pro 2nd Gen", "USB-C MagSafe Case", 650000, "Electronics"),
            ("Galaxy Watch 6 Classic", "Rotating Bezel, 47mm", 950000, "Electronics"),
            ("Garmin Fenix 7X Solar", "Multisport GPS Watch", 2400000, "Electronics"),
            ("Fitbit Charge 6", "Health & Fitness Tracker", 450000, "Electronics"),
            ("Anker 737 Power Bank", "24000mAh, 140W Output", 450000, "Electronics"),
            ("SanDisk Extreme Pro 2TB", "Portable SSD, 2000MB/s", 850000, "Electronics"),
            ("WD Black SN850X 1TB", "NVMe SSD for PS5/PC", 350000, "Electronics"),
            ("Seagate IronWolf 8TB", "NAS Internal Hard Drive", 750000, "Electronics"),
            ("RTX 4090 Graphics Card", "24GB GDDR6X, ASUS ROG Strix", 5500000, "Electronics"),
            ("AMD Ryzen 9 7950X", "16-Core Desktop Processor", 1800000, "Electronics"),
            ("Intel Core i9-14900K", "24-Core Desktop Processor", 1900000, "Electronics"),
            ("Corsair Dominator 32GB", "DDR5 RGB RAM Kit", 650000, "Electronics"),
            ("NZXT Kraken Elite 360", "RGB Liquid CPU Cooler", 850000, "Electronics"),
            ("Lian Li O11 Dynamic", "Tempered Glass PC Case", 450000, "Electronics"),
            ("Secretlab Titan Evo", "Gaming Chair, SoftWeave", 1500000, "Electronics"),
            ("Elgato Stream Deck MK.2", "Studio Controller, 15 Keys", 450000, "Electronics"),
            ("Blue Yeti X", "Professional USB Microphone", 480000, "Electronics"),
            ("Logitech C920x Pro", "1080p HD Webcam", 220000, "Electronics")
        ]

        # 4. Create Items with Online Images
        cat_obj, _ = Category.objects.get_or_create(name="Electronics", defaults={'slug': 'electronics'})
        
        self.stdout.write(f"Adding {len(products)} items with real images (this may take a moment)...")

        # SSL Context for downloading images
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for title, desc, price, cat_name in products:
            if not Item.objects.filter(seller=user, title=title).exists():
                item = Item.objects.create(
                    seller=user,
                    company=company,
                    title=title,
                    description=desc,
                    price=price,
                    stock_quantity=random.randint(5, 50),
                    category_obj=cat_obj,
                    condition='new',
                    contact_method='chat',
                    status='active'
                )
                
                # Fetch Image
                try:
                    # Using LoremFlickr for more reliable keyword-based images
                    # Use first two words of title as keywords (e.g., "iPhone 15", "Samsung Galaxy")
                    keywords = ",".join(title.split()[:2])
                    safe_keywords = urllib.parse.quote(keywords)
                    img_url = f"https://loremflickr.com/600/400/{safe_keywords}?random={random.randint(1, 10000)}"
                    
                    # Set a timeout to avoid hanging
                    req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                        # Save image to the item
                        file_name = f"{title.lower().replace(' ', '_')}.jpg"
                        item.image.save(file_name, ContentFile(response.read()), save=True)
                        self.stdout.write(f" [OK] Added: {title}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f" [FAIL] Image for {title}: {e}"))
                    # Fallback to placeholder text image
                    try:
                        safe_title = urllib.parse.quote(title)
                        fallback_url = f"https://placehold.co/600x400/png?text={safe_title}"
                        req = urllib.request.Request(fallback_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                            file_name = f"{title.lower().replace(' ', '_')}.jpg"
                            item.image.save(file_name, ContentFile(response.read()), save=True)
                            self.stdout.write(f" [OK] Added fallback for: {title}")
                    except Exception as e2:
                        self.stdout.write(self.style.ERROR(f" [FAIL] Fallback also failed for {title}: {e2}"))
            else:
                self.stdout.write(f" [SKIP] Exists: {title}")

        self.stdout.write(self.style.SUCCESS('\n--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS(' POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS(f" Username: {company_data['username']}"))
        self.stdout.write(self.style.SUCCESS(f" Password: {company_data['password']}"))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
