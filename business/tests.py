from django.test import TestCase, Client
from django.contrib.auth.models import User
from users.models import Profile
from business.models import Category, Attribute, Item, ProductAttributeValue, ItemMedia
from business.forms import ItemForm


class FlexibleAttributesAndSellingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="seller1",
            email="seller1@udsm.ac.tz",
            password="testpassword123",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            phone_number="0712345678",
            is_email_verified=True,
        )
        self.client = Client()
        self.client.login(username="seller1", password="testpassword123")

        # Category and Storage attribute
        self.cat = Category.objects.create(name="Laptops", slug="laptops")
        self.storage_attr = Attribute.objects.create(
            name="Storage / SSD (GB/TB)",
            options="128 GB SSD, 256 GB SSD, 512 GB SSD",
        )
        self.storage_attr.categories.add(self.cat)

    def test_custom_storage_attribute_accepted_without_error(self):
        """User can enter custom storage (e.g. 500 GB HDD or 160 GB HDD) without form rejection."""
        data = {
            "title": "Dell Latitude 5400",
            "condition": "used",
            "price": "350000",
            "stock_quantity": "1",
            "description": "Good battery life, clean laptop.",
            "campus_location": "CoICT",
            "contact_method": "phone",
            "contact_phone": "0712345678",
            "contact_email": "seller1@udsm.ac.tz",
            f"attr_{self.storage_attr.id}": "500 GB HDD",  # Custom value outside options!
        }
        form = ItemForm(data=data, category=self.cat)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        form.instance.seller = self.user
        item = form.save()

        # Check attribute value in DB
        pav = ProductAttributeValue.objects.get(product=item, attribute=self.storage_attr)
        self.assertEqual(pav.value, "500 GB HDD")

    def test_post_item_view_prefills_registered_contact(self):
        """Post item view pre-populates registered phone and email."""
        from django.urls import reverse
        url = reverse("business:post_item")
        resp = self.client.get(f"{url}?category={self.cat.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["registered_phone"], "0712345678")
        self.assertEqual(resp.context["registered_email"], "seller1@udsm.ac.tz")
        self.assertEqual(resp.context["form"]["contact_phone"].value(), "0712345678")
        self.assertEqual(resp.context["form"]["contact_email"].value(), "seller1@udsm.ac.tz")
