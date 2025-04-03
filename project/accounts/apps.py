from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    def ready(self):
        from .signals import set_default_photos, create_full_prof,delete_cart
        return super().ready()
