from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class Command(BaseCommand):
    help = "Assign users to groups"

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            help='User phone number',
        )
        parser.add_argument(
            '--group',
            type=str,
            help='Group name to assign',
        )
        parser.add_argument(
            '--list-groups',
            action='store_true',
            help='List all available groups',
        )
        parser.add_argument(
            '--list-users',
            action='store_true',
            help='List all users',
        )

    def handle(self, *args, **options):
        if options['list_groups']:
            self.stdout.write("Available groups:")
            for group in Group.objects.all():
                self.stdout.write(f"  - {group.name}")
            return

        if options['list_users']:
            self.stdout.write("Users:")
            for user in User.objects.all():
                groups = user.groups.all()
                group_names = [g.name for g in groups]
                self.stdout.write(f"  - {user.phone_number} ({user.name}): {', '.join(group_names) if group_names else 'No groups'}")
            return

        if not options['phone'] or not options['group']:
            self.stdout.write(
                self.style.ERROR("Please provide both --phone and --group")
            )
            return

        try:
            user = User.objects.get(phone_number=options['phone'])
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"User with phone {options['phone']} not found")
            )
            return

        try:
            group = Group.objects.get(name=options['group'])
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Group '{options['group']}' not found")
            )
            return

        if user.groups.filter(name=options['group']).exists():
            self.stdout.write(
                self.style.WARNING(f"User {user.phone_number} is already in group '{options['group']}'")
            )
            return

        user.groups.add(group)
        self.stdout.write(
            self.style.SUCCESS(f"Added user {user.phone_number} to group '{options['group']}'")
        )