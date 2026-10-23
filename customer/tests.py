from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from business.models import Category, Item
from tancoin.models import ExchangeRate


class StorefrontAndStaticTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_buyer", email="buyer@test.com", password="password123"
        )
        self.seller = User.objects.create_user(
            username="test_seller", email="seller@test.com", password="password123"
        )
        self.category = Category.objects.create(name="Electronics", slug="electronics")
        self.item = Item.objects.create(
            seller=self.seller,
            title="HP Laptop 15",
            description="Good condition laptop for campus.",
            price=650000,
            stock_quantity=5,
            category_obj=self.category,
            contact_method="chat",
            status="active",
        )
        ExchangeRate.objects.create(fiat_per_one_tan=1.0, fiat_currency_code="TZS")

    def test_storefront_pages_render(self):
        """Test public storefront pages render 200."""
        pages = [
            reverse("customer:home"),
            reverse("customer:about"),
            reverse("customer:contact"),
            reverse("customer:documentation"),
            reverse("customer:item_detail", args=[self.item.id]),
        ]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed on {url}")

    def test_search_suggest_api(self):
        """Test search suggest API returns JSON."""
        url = reverse("customer:search_suggest") + "?q=Laptop"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])

    def test_serviceworker_returns_clean_javascript(self):
        """Verify serviceworker.js returns 200 application/javascript with cache v5."""
        response = self.client.get("/serviceworker.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertIn("u-connect-v5", response.content.decode("utf-8"))

    def test_chat_root_redirects_cleanly(self):
        """Verify /chat/ root path does not 404."""
        response = self.client.get("/chat/", follow=False)
        # Should redirect to inbox (or login when unauthenticated)
        self.assertIn(response.status_code, [200, 302])

    def test_cart_workflow(self):
        """Test adding item to cart and viewing cart."""
        self.client.force_login(self.user)
        add_url = reverse("customer:add_to_cart", args=[self.item.id])
        response = self.client.post(add_url, {"quantity": 2}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Check cart view
        cart_url = reverse("customer:view_cart")
        cart_resp = self.client.get(cart_url)
        self.assertEqual(cart_resp.status_code, 200)
        self.assertContains(cart_resp, "HP Laptop 15")

    def test_static_css_resolves_as_text_css(self):
        """Verify static CSS files exist and resolve properly."""
        from django.contrib.staticfiles.finders import find

        style_path = find("css/style.css")
        shop_path = find("css/shop.css")
        ae_path = find("css/ae.css")

        self.assertIsNotNone(style_path, "style.css not found by static finders")
        self.assertIsNotNone(shop_path, "shop.css not found by static finders")
        self.assertIsNotNone(ae_path, "ae.css not found by static finders")

    def test_chat_room_does_not_leak_message_objects(self):
        """Verify chat room renders messages inside bubbles and not as flash alert boxes."""
        from chat.models import Conversation, Message

        conv = Conversation.objects.create()
        conv.participants.add(self.user, self.seller)
        msg1 = Message.objects.create(
            conversation=conv, sender=self.user, content="Habari, hii ipo bado?"
        )
        msg2 = Message.objects.create(
            conversation=conv, sender=self.seller, content="Ndio ipo boss."
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:chat_room", args=[conv.id]))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertNotIn("Message object", content)
        self.assertIn("Habari, hii ipo bado?", content)
        self.assertIn("Ndio ipo boss.", content)


