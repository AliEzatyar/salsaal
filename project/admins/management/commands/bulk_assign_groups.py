from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class Command(BaseCommand):
    help = "Bulk assign users to groups based on their role"

    def handle(self, *args, **kwargs):
        # Define role to group mappings
        role_group_mapping = {
            0: 'Site Admin',      # ADMIN
            1: 'Vendor Manager',  # REST (Restaurant)
            2: 'Support Staff',   # CUSTOMER
            3: 'Order Manager',   # CARRIER
        }

        assigned_count = 0

        for user in User.objects.all():
            group_name = role_group_mapping.get(user.role)
            if group_name:
                try:
                    group = Group.objects.get(name=group_name)
                    if not user.groups.filter(name=group_name).exists():
                        user.groups.add(group)
                        assigned_count += 1
                        self.stdout.write(
                            f"Assigned {user.phone_number} ({user.name}) to {group_name}"
                        )
                except Group.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"Group '{group_name}' not found")
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Assigned {assigned_count} users to groups based on their roles")
        )