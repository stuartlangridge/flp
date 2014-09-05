from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

class Command(BaseCommand):
    args = ''
    help = 'Make a user called sil a superuser'

    def handle(self, *args, **options):
        try:
            u = User.objects.get(username="sil")
        except:
            self.stdout.write("No such user")
            return

        u.is_staff = True
        u.is_superuser = True
        u.save()
