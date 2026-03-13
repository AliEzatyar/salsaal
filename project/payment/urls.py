from django.urls import path
from .views import create_payment_intent
from .webhook import stripe_webhook

app_name = "payment"

urlpatterns = [
    path("create-payment-intent/", create_payment_intent),
    path("stripe-webhook/", stripe_webhook),
]
