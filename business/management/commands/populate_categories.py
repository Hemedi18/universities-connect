from django.core.management.base import BaseCommand
from business.models import Category, Attribute

class Command(BaseCommand):
    help = 'Populates categories and attributes from the specified list'

    def handle(self, *args, **kwargs):
        # Data: Category_ID, Parent_Category, Sub_Category, Specific_Requirements (Attributes), Major_Brands
        data = [
            ("CAT-01", "Electronics", "Smartphones", "Model, OS, Storage, RAM, Battery, Camera, Screen Size", "Apple, Samsung, Xiaomi, Oppo, Vivo, Huawei, Realme, Motorola, Google, OnePlus, Tecno, Infinix, Itel, Nokia, Sony, Honor, ZTE, Asus, Meizu"),
            ("CAT-02", "Electronics", "Laptops", "Model, Processor, RAM, SSD/HDD, GPU, Screen Size, OS", "Dell, HP, Lenovo, Apple, Acer, ASUS, MSI, Microsoft, Razer"),
            ("CAT-03", "Electronics", "Wearables/Audio", "Connectivity, Battery Life, Water Resistance", "Sony, Bose, JBL, Apple, Beats, Sennheiser, Jabra, Garmin, Fitbit"),
            ("CAT-04", "Transportation", "Cars", "Model, Year, Mileage, Transmission, Fuel Type, Engine, VIN", "Toyota, Nissan, Honda, Ford, BMW, Mercedes-Benz, Volkswagen, Hyundai, Kia, Tesla, Audi, Chevrolet, Mitsubishi, Land Rover"),
            ("CAT-05", "Transportation", "Motorcycles", "CC, Stroke, Start System, Braking", "Honda, Yamaha, Suzuki, Kawasaki, Bajaj, TVS, KTM, Harley-Davidson"),
            ("CAT-06", "Transportation", "Heavy Machinery", "Horsepower, Load Capacity, Fuel Type", "Caterpillar, Komatsu, John Deere, Volvo, Liebherr, JCB, Hitachi"),
            ("CAT-07", "Food & Beverages", "Packaged Foods", "Expiry Date, Weight, Ingredients, Diet Label", "Nestle, Unilever, PepsiCo, Coca-Cola, Kellogg's, Danone, Mars, Mondelez, Kraft Heinz"),
            ("CAT-08", "Food & Beverages", "Drinks & Spirits", "Volume, Alcohol%, Ingredients, Storage", "Coca-Cola, PepsiCo, Heineken, Diageo, Red Bull, Budweiser, Pernod Ricard"),
            ("CAT-09", "Fashion", "Clothing", "Size, Color, Material, Gender, Care Info", "Nike, Adidas, Zara, H&M, Gucci, Prada, Uniqlo, Levi's, Puma"),
            ("CAT-10", "Fashion", "Footwear", "Shoe Size, Material, Gender, Closure Type", "Reebok, Skechers, Converse, Vans, New Balance"),
            ("CAT-11", "Fashion", "Watches & Jewelry", "Movement, Case Material, Water Resistance", "Rolex, Omega, Cartier, Seiko, Casio, Tissot, Patek Philippe, Swarovski"),
            ("CAT-12", "Home & Kitchen", "Large Appliances", "Voltage, Energy Rating, Capacity, Warranty", "LG, Samsung, Whirlpool, Bosch, Panasonic, Haier, Philips, Miele"),
            ("CAT-13", "Home & Kitchen", "Furniture", "Dimensions, Material, Finish, Weight Capacity", "IKEA, Ashley Furniture, Wayfair, Herman Miller, Steelcase"),
            ("CAT-14", "Health & Beauty", "Skincare", "Skin Type, Active Ingredients, Volume, SPF", "L'Oreal, Nivea, Neutrogena, Dove, Estee Lauder, Clinique"),
            ("CAT-15", "Health & Beauty", "Pharmaceuticals", "Dosage, Count, Active Ingredients, Prescription Req", "Pfizer, Johnson & Johnson, Roche, Novartis, Bayer, GSK, Sanofi"),
            ("CAT-16", "Real Estate", "Property Agencies", "Area, Bedrooms, Location, Ownership Type", "RE/MAX, Century 21, Knight Frank, Coldwell Banker"),
            ("CAT-17", "Industrial", "Construction Materials", "Grade, Material, Dimensions, Weight", "LafargeHolcim, Saint-Gobain, Nippon Steel, ArcelorMittal"),
            ("CAT-18", "Industrial", "Power Tools", "Power Source, Voltage, RPM, Torque", "DeWalt, Makita, Bosch, Milwaukee, Black+Decker, Hilti"),
            ("CAT-19", "Media & Books", "Entertainment", "Format, Language, Genre", "Penguin Random House, Sony Pictures, Disney, Warner Bros, Universal"),
            ("CAT-20", "Services", "Digital Services", "Duration, Subscription Type, Delivery Time", "Google, Amazon Web Services, Netflix, Spotify, Meta"),
        ]

        self.stdout.write('Populating categories and attributes...')

        for code, parent_name, sub_name, attrs_str, brands_str in data:
            # Create/Get Parent Category
            parent, _ = Category.objects.get_or_create(name=parent_name, parent=None)
            
            # Create/Get Sub Category
            sub, created = Category.objects.get_or_create(name=sub_name, parent=parent)
            sub.code = code
            sub.save()

            # Process Attributes
            # 1. Add Company with options (Replaces Brand/Make/Provider)
            company_attr_name = "Company"
            
            # Remove any existing "Company" attributes from this subcategory to prevent incorrect options
            existing_attrs = sub.attributes.filter(name=company_attr_name)
            if existing_attrs.exists():
                sub.attributes.remove(*existing_attrs)

            # Get or Create a specific attribute for these options
            company_attr, _ = Attribute.objects.get_or_create(
                name=company_attr_name,
                options=brands_str
            )
            
            if not company_attr.categories.filter(id=sub.id).exists():
                company_attr.categories.add(sub)

            # 2. Other Attributes
            attr_names = [x.strip() for x in attrs_str.split(',')]
            for attr_name in attr_names:
                if not attr_name: continue
                
                # Get or create attribute
                attribute, _ = Attribute.objects.get_or_create(name=attr_name)
                
                # Link to sub-category if not already linked
                if not attribute.categories.filter(id=sub.id).exists():
                    attribute.categories.add(sub)

        self.stdout.write(self.style.SUCCESS('Successfully populated database.'))