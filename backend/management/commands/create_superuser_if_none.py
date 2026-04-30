from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        superuser_username = os.getenv("SUPERUSER_USERNAME", "admin")
        superuser_password = os.getenv("SUPERUSER_PASSWORD", "password")
        superuser_email = os.getenv("SUPERUSER_EMAIL", "admin@example.com")
        if not User.objects.filter(username=superuser_username).exists():
            User.objects.create_superuser(
                superuser_username, superuser_email, superuser_password
            )
            self.stdout.write("Superuser created.")
        else:
            self.stdout.write("Superuser already exists.")
