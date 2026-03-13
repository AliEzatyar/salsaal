from django.apps import AppConfig


class PaymentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payment'

    def ready(self):
    # register periodic celery-beat tasks after migrations
        from django.db.models.signals import post_migrate
        from django.dispatch import receiver
        from .register_tasks import register_periodic_tasks

        @receiver(post_migrate)
        def _register_tasks(sender, **kwargs):
            try:
                register_periodic_tasks()
            except Exception:
                # do not interrupt app ready if celery-beat not configured yet
                pass
