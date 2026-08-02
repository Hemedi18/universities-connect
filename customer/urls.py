from django.urls import path

from . import views

app_name = "customer"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/search-suggest/", views.search_suggest, name="search_suggest"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("documentation/", views.documentation, name="documentation"),
    path("item/<int:item_id>/", views.item_detail, name="item_detail"),
    path(
        "item/<int:item_id>/whatsapp/",
        views.whatsapp_share,
        name="whatsapp_share",
    ),
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/add/<int:item_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:item_id>/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.my_orders, name="my_orders"),
    path("orders/seller/", views.seller_orders, name="seller_orders"),
    path(
        "orders/seller/<int:order_id>/",
        views.seller_order_detail,
        name="seller_order_detail",
    ),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path(
        "orders/<int:order_id>/success/",
        views.order_success,
        name="order_success",
    ),
    path(
        "orders/<int:order_id>/invoice/",
        views.order_invoice,
        name="order_invoice",
    ),
    path(
        "orders/<int:order_id>/payment-reference/",
        views.submit_payment_reference,
        name="submit_payment_reference",
    ),
    path(
        "orders/<int:order_id>/cancel/",
        views.cancel_my_order,
        name="cancel_order",
    ),
]
