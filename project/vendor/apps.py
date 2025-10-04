from django.apps import AppConfig

class VendorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendor'

    def ready(self):
        from . import signals
        from django.db.models.signals import post_migrate
        from django.dispatch import receiver
        from .register_tasks import register_periodic_tasks

        @receiver(post_migrate)
        def create_daily_task(sender, **kwargs):
            return register_periodic_tasks()