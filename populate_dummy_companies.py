from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from company.models import Company, Region, District
from business.models import Category, Item
import random
from datetime import time

class Command(BaseCommand):
    help = 'Populates the database with dummy company data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating dummy companies...')

        password = 'hemy@2004'
        credentials = []

        # Ensure we have regions
        regions = Region.objects.all()
        if not regions.exists():
            self.stdout.write(self.style.WARNING('No regions found. Please run "python manage.py populate_locations" first.'))
            return

        # Dummy images (assuming these exist in media/item_images/ based on project structure)
        # Using generic names that likely exist or will fallback gracefully if handled in templates
        dummy_images = [
            'item_images/Gemini_Generated_Image_tej9s0tej9s0tej9.png',
            'item_images/pexels-roacunha-2531709.jpg',
            'item_images/pexels-rpnickson-2647990.jpg',
            'item_images/pexels-sohi-807598.jpg',
            'item_images/pexels-souvenirpixels-1534057.jpg'
        ]

        # Sample Data
        companies_data = [
            {
                'name': 'Tech Hub Tanzania',
                'desc': 'Your one-stop shop for all latest gadgets and accessories.',
                'cat_keyword': 'Electronics',
                'username': 'tech_hub_admin',
                'products': [
                    {'title': 'iPhone 15 Pro Max 256GB', 'desc': 'Brand new Apple iPhone 15 Pro Max. Natural Titanium finish. 1 year Apple warranty included.', 'price': 3500000},
                    {'title': 'Samsung Galaxy S24 Ultra', 'desc': 'Experience Galaxy AI. 512GB Storage, 12GB RAM. Titanium Gray. S-Pen included.', 'price': 3200000},
                    {'title': 'HP Pavilion 15 Laptop', 'desc': 'Core i5 12th Gen, 16GB RAM, 512GB SSD. Perfect for students and programming.', 'price': 1200000},
                    {'title': 'Sony WH-1000XM5 Headphones', 'desc': 'Best in class noise cancellation. 30-hour battery life. Comfortable for long study sessions.', 'price': 850000},
                    {'title': 'Anker PowerBank 20000mAh', 'desc': 'Fast charging power bank. Can charge your phone up to 5 times. Essential for campus life.', 'price': 150000}
                ]
            },
            {
                'name': 'Campus Fashion',
                'desc': 'Trendy and affordable clothing for students.',
                'cat_keyword': 'Fashion',
                'username': 'fashion_admin',
                'products': [
                    {'title': 'Vintage Denim Jacket', 'desc': 'Classic oversized denim jacket. Unisex. Available in sizes M, L, XL.', 'price': 45000},
                    {'title': 'Graphic Print T-Shirt', 'desc': '100% Cotton t-shirt with cool graphic prints. Various designs available.', 'price': 25000},
                    {'title': 'High Waist Mom Jeans', 'desc': 'Stylish and comfortable high waist jeans. Blue and Black wash available.', 'price': 35000},
                    {'title': 'Canvas Sneakers White', 'desc': 'Casual white sneakers. Durable and goes with every outfit.', 'price': 40000},
                    {'title': 'Varsity Hoodie', 'desc': 'Warm and cozy hoodie with university style lettering.', 'price': 55000}
                ]
            },
            {
                'name': 'Mama Lishe Delights',
                'desc': 'Home cooked meals delivered to your hostel.',
                'cat_keyword': 'Food',
                'username': 'mama_lishe',
                'products': [
                    {'title': 'Pilau & Kuku Lunch Box', 'desc': 'Spiced rice with fried chicken and kachumbari. Delicious and filling.', 'price': 8000},
                    {'title': 'Chapati & Beans Combo', 'desc': '3 soft chapatis with tasty coconut beans stew.', 'price': 5000},
                    {'title': 'Fresh Passion Juice (500ml)', 'desc': 'Freshly squeezed passion fruit juice. No added sugar options available.', 'price': 2000},
                    {'title': 'Vegetable Samosas (5pcs)', 'desc': 'Crispy samosas filled with spiced vegetables. Great snack.', 'price': 3000},
                    {'title': 'Chips Mayai Special', 'desc': 'Chips omelette with salad and sauce.', 'price': 4000}
                ]
            },
            {
                'name': 'Quick Wheels',
                'desc': 'Reliable transport and car hire services.',
                'cat_keyword': 'Transportation',
                'username': 'quick_wheels',
                'products': [
                    {'title': 'Toyota Ist for Rent (Daily)', 'desc': 'Fuel efficient Toyota Ist available for daily rental. Valid license required.', 'price': 60000},
                    {'title': 'Bajaj Boxer 150 (Used)', 'desc': 'Well maintained motorcycle. Good for campus commute. 15000km mileage.', 'price': 1800000},
                    {'title': 'Mountain Bike', 'desc': 'Sturdy mountain bike. 21 gears. Helmet included.', 'price': 350000},
                    {'title': 'Airport Transfer Service', 'desc': 'Reliable drop-off or pick-up from the airport. Any time of day.', 'price': 50000}
                ]
            },
            {
                'name': 'Study Smart Books',
                'desc': 'New and used textbooks for all courses.',
                'cat_keyword': 'Books',
                'username': 'book_seller',
                'products': [
                    {'title': 'Introduction to Java Programming', 'desc': 'Comprehensive guide to Java. 10th Edition. Like new.', 'price': 45000},
                    {'title': 'Financial Accounting Vol 1', 'desc': 'Essential for business students. Hardcover.', 'price': 60000},
                    {'title': 'Law of Contract in Tanzania', 'desc': 'Standard text for law students. Detailed case studies.', 'price': 55000},
                    {'title': 'Medical Physiology (Guyton)', 'desc': 'The bible of physiology. International edition.', 'price': 80000},
                    {'title': 'Advanced Engineering Mathematics', 'desc': 'Covers all engineering math topics. Used but clean.', 'price': 40000}
                ]
            }
        ]

        self.stdout.write("Creating Companies and Products...")
        total_items_created = 0
        for data in companies_data:
            username = data['username']
            email = f'{username}@test.com'
            
            # Create User
            user, created = User.objects.get_or_create(username=username, email=email)
            user.set_password(password)
            user.save()
            
            credentials.append({'type': 'Company Owner', 'username': username, 'password': password, 'company': data['name']})
            
            # Create Company
            if not hasattr(user, 'company_profile'):
                region = random.choice(list(regions)) if regions else None
                districts = region.districts.all() if region else []
                district = random.choice(districts) if districts else None
                
                company = Company.objects.create(
                    user=user,
                    name=data['name'],
                    description=data['desc'],
                    region=region,
                    district=district,
                    address=f"Plot {random.randint(1, 100)}, {district.name if district else (region.name if region else 'City Center')}",
                    whatsapp_number=f"2557{random.randint(10000000, 99999999)}",
                    is_verified=random.choice([True, False]),
                    opening_time=time(8, 0),
                    closing_time=time(18, 0)
                )
                self.stdout.write(self.style.SUCCESS(f'Created company: {company.name}'))
                
            else:
                # If company exists, ensure we still add items if needed or just log it
                company = user.company_profile
                self.stdout.write(f'Company {company.name} already exists.')

            # Create Items
            category = Category.objects.filter(name__icontains=data['cat_keyword']).first()
            if not category:
                # Fallback: Create a general category if not found
                category, _ = Category.objects.get_or_create(name=data['cat_keyword'], defaults={'slug': data['cat_keyword'].lower()})
            
            for prod in data['products']:
                # Check if item already exists to avoid duplicates on re-run
                if not Item.objects.filter(seller=user, title=prod['title']).exists():
                    image_path = random.choice(dummy_images)
                    Item.objects.create(
                        seller=user,
                        company=company,
                        title=prod['title'],
                        description=prod['desc'],
                        price=prod['price'],
                        stock_quantity=random.randint(5, 50),
                        category_obj=category,
                        condition='new',
                        contact_method='chat',
                        status='active',
                        image=image_path
                    )
                    total_items_created += 1
            self.stdout.write(f' - Added products for {company.name}')

        # 2. Create Personal Business Users (No Company)
        personal_users_data = [
            {
                'username': 'student_seller_1', 
                'cat_keyword': 'Electronics',
                'products': [
                    {'title': 'Used PlayStation 4 Slim', 'desc': 'PS4 Slim 500GB with 1 controller and FIFA 23. Good condition.', 'price': 450000},
                    {'title': 'Scientific Calculator Casio fx-991EX', 'desc': 'Original Casio calculator. Solar powered. Essential for engineering.', 'price': 35000}
                ]
            },
            {
                'username': 'student_seller_2', 
                'cat_keyword': 'Books',
                'products': [
                    {'title': 'Used Novels Bundle', 'desc': 'Collection of 5 thriller novels. Great for leisure reading.', 'price': 20000},
                    {'title': 'Study Desk Lamp', 'desc': 'Rechargeable LED desk lamp. 3 brightness levels.', 'price': 15000}
                ]
            },
            {
                'username': 'student_seller_3', 
                'cat_keyword': 'Fashion',
                'products': [
                    {'title': 'Pre-loved Nike Air Force 1', 'desc': 'Size 42. Slightly used but clean. White color.', 'price': 50000},
                    {'title': 'Electric Kettle', 'desc': '1.5L Electric Kettle. Boils water fast. Moving out sale.', 'price': 18000}
                ]
            },
        ]

        self.stdout.write("Creating Personal Sellers...")
        for data in personal_users_data:
            username = data['username']
            email = f'{username}@test.com'
            
            user, created = User.objects.get_or_create(username=username, email=email)
            user.set_password(password)
            user.save()
            
            credentials.append({'type': 'Personal Seller', 'username': username, 'password': password, 'company': 'N/A'})

            # Create Items for Personal User
            category = Category.objects.filter(name__icontains=data['cat_keyword']).first()
            if not category:
                category, _ = Category.objects.get_or_create(name=data['cat_keyword'], defaults={'slug': data['cat_keyword'].lower()})

            for prod in data['products']:
                if not Item.objects.filter(seller=user, title=prod['title']).exists():
                    image_path = random.choice(dummy_images)
                    Item.objects.create(
                        seller=user,
                        company=None, # Personal item
                        title=prod['title'],
                        description=prod['desc'],
                        price=prod['price'],
                        stock_quantity=1,
                        category_obj=category,
                        condition='used',
                        contact_method='chat',
                        status='active',
                        image=image_path,
                        campus_location=f"Hall {random.randint(1, 7)}"
                    )
                    total_items_created += 1
            self.stdout.write(f' - Added products for {username}')

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully populated dummy data. Created {total_items_created} new items.'))
        self.stdout.write('\n--- CREDENTIALS ---')
        self.stdout.write(f"{'Type':<20} | {'Username':<20} | {'Password':<15} | {'Company'}")
        self.stdout.write('-' * 80)
        for cred in credentials:
            self.stdout.write(f"{cred['type']:<20} | {cred['username']:<20} | {cred['password']:<15} | {cred['company']}")