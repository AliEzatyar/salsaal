from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class Command(BaseCommand):
    help = "Make users in specific groups staff members"

    def add_arguments(self, parser):
        parser.add_argument(
            '--group',
            type=str,
            help='Group name whose members should become staff',
        )
        parser.add_argument(
            '--all-groups',
            action='store_true',
            help='Make all users in all groups staff members',
        )

    def handle(self, *args, **options):
        if options['all_groups']:
            # Make all users in any group staff
            groups = Group.objects.all()
            total_made_staff = 0

            for group in groups:
                users = group.custom_user_set.filter(is_staff=False)
                count = users.update(is_staff=True)
                total_made_staff += count
                if count > 0:
                    self.stdout.write(f"Made {count} users in '{group.name}' staff")

            self.stdout.write(
                self.style.SUCCESS(f"Total users made staff: {total_made_staff}")
            )

        elif options['group']:
            try:
                group = Group.objects.get(name=options['group'])
                users = group.custom_user_set.filter(is_staff=False)
                count = users.update(is_staff=True)

                self.stdout.write(
                    self.style.SUCCESS(f"Made {count} users in '{options['group']}' staff")
                )
            except Group.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Group '{options['group']}' not found")
                )
        else:
            self.stdout.write(
                self.style.ERROR("Please specify --group or --all-groups")
            )