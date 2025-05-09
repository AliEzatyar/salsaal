from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    def ready(self):
        from .signals import create_full_prof,delete_cart_carrier,delete_cart_vendor
        return super().ready()
