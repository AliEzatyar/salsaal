from django.forms import ModelForm
from .models import Order, OrderItem

class OrderForm(ModelForm):
    class Meta:
        model = Order
        exclude = ["status","user","created","updated","payment_id","total_price"]        
