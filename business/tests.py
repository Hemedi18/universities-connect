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


class MultiLanguageTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_default_language_is_english(self):
        """Web pages default to English and LTR layout."""
        from django.conf import settings
        self.assertEqual(settings.LANGUAGE_CODE, "en")
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'lang="en"')
        self.assertContains(resp, 'dir="ltr"')

    def test_switch_language_to_swahili(self):
        """Direct switcher /set-language/sw/ sets cookie and renders Swahili text."""
        resp = self.client.get("/set-language/sw/?next=/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.cookies["django_language"].value, "sw")

        # Request homepage with Swahili cookie
        resp_sw = self.client.get("/", headers={"cookie": "django_language=sw"})
        self.assertContains(resp_sw, 'lang="sw"')
        self.assertContains(resp_sw, 'dir="ltr"')
        self.assertContains(resp_sw, "Nyumbani")
        self.assertContains(resp_sw, "Duka")

    def test_switch_language_to_arabic_with_rtl(self):
        """Direct switcher /set-language/ar/ activates Arabic and renders dir='rtl'."""
        resp = self.client.get("/set-language/ar/?next=/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.cookies["django_language"].value, "ar")

        # Request homepage with Arabic cookie
        resp_ar = self.client.get("/", headers={"cookie": "django_language=ar"})
        self.assertContains(resp_ar, 'lang="ar"')
        self.assertContains(resp_ar, 'dir="rtl"')
        self.assertContains(resp_ar, "الرئيسية")
        self.assertContains(resp_ar, "المتجر")

    def test_invalid_language_falls_back_to_english(self):
        """Non-supported language codes fall back safely to English."""
        resp = self.client.get("/set-language/invalid_lang/?next=/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.cookies["django_language"].value, "en")
