import subprocess
import os
import signal
import time
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Start or reload the Nginx server (from BASE_DIR/nginx). Press Ctrl+C to stop Nginx.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reload',
            action='store_true',
            help='Reload Nginx instead of starting it fresh.',
        )

    def handle(self, *args, **options):
        nginx_dir = os.path.join(settings.BASE_DIR, 'nginx')
        nginx_exe = os.path.join(nginx_dir, 'nginx.exe')

        if not os.path.exists(nginx_exe):
            self.stderr.write(self.style.ERROR(f"[ERROR] nginx.exe not found at: {nginx_exe}"))
            return

        try:
            if options['reload']:
                subprocess.run([nginx_exe, "-s", "reload"], cwd=nginx_dir, check=True)
                self.stdout.write(self.style.SUCCESS("[Nginx] Reloaded successfully."))
                return

            # Start nginx
            subprocess.run([nginx_exe], cwd=nginx_dir, check=True)
            self.stdout.write(self.style.SUCCESS("[Nginx] Started successfully."))

            # Wait indefinitely until user presses Ctrl+C
            self.stdout.write(self.style.WARNING("[INFO] Press Ctrl+C to stop Nginx."))

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("[INFO] Ctrl+C detected. Shutting down Nginx..."))
            try:
                subprocess.run([nginx_exe, "-s", "stop"], cwd=nginx_dir, check=True)
                self.stdout.write(self.style.SUCCESS("[Nginx] Stopped successfully."))
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f"[Nginx] Failed to stop: {e}"))

        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"[Nginx] Failed: {e}"))
 