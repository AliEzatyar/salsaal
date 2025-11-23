from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


GROUPS = {
    "Site Admin": {
        "*": ["add", "change", "delete", "view"],  # Full access
    },
    "Accounts Manager": {
        "accounts": [
            "change_user",
            "view_user",
            "change_userprofile",
            "view_userprofile",
        ],
        "vendor": ["view_vendor"],
    },
    "Vendor Manager": {
        "vendor": [
            "change_vendor",
            "view_vendor",
            "add_promotion",
            "change_promotion",
            "view_promotion",
        ],
        "marketplace": [
            "change_food",
            "delete_food",
            "view_food",
            "add_category",
            "change_category",
            "view_category",
        ],
        "qoraa": [
            "change_qoraa",
            "view_qoraa",
            "delete_qoraa",
            "add_qoraa",
            "add_qoraa_vendor",
            "change_qoraa_vendor",
            "view_qoraa_vendor",
            "delete_qoraa_vendor",
        ],
    },
    "Order Manager": {
        "order": ["change_order", "view_order"],
        "carrier": ["change_carrier", "delete_carrier", "view_carrier"],
    },
    "Support Staff": {
        "order": ["view_order"],
        "vendor": ["view_vendor"],
        "accounts": ["view_user"],
        "marketplace": ["view_food"],
        "carrier": ["view_carrier"],
    },
    "Developer": {
        "*": ["view"],  # Read-only for all models
    },
}


class Command(BaseCommand):
    help = "Creates default system groups and permissions"

    def handle(self, *args, **kwargs):
        for group_name, app_perms in GROUPS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))

            # Special Developer group logic
            if group_name == "Developer":
                for perm in Permission.objects.filter(codename__startswith="view_"):
                    group.permissions.add(perm)
                continue

            for app_label, perms in app_perms.items():
                if app_label == "*":
                    continue

                for perm_codename in perms:
                    try:
                        perm = Permission.objects.get(codename=perm_codename)
                        group.permissions.add(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f"Permission not found: {perm_codename}")
                        )

        self.stdout.write(
            self.style.SUCCESS("All groups and permissions created successfully!")
        )
