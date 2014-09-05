from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
import flp.common

class Command(BaseCommand):
    args = '<username>'
    help = 'Updates UserMonthScore for a user'

    def handle(self, *args, **options):
        if len(args) != 1:
            raise Exception("Specify a username")
        user = User.objects.get(username=args[0])
        flp.common.update_user_month_score(user)
