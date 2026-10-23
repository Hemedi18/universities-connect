"""
passenger_wsgi.py - Phusion Passenger entrypoint for cPanel / CloudLinux.
Connects incoming web requests on uconnect.edusphere.co.tz to the U-Connect Django WSGI application.
"""

import os
import sys

# Ensure current project directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "u_connect.settings")

# Expose WSGI callable for Passenger
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
