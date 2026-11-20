"""Entry point for hosts that need a WSGI file (for example PythonAnywhere)."""
from sweetsbyanam import create_app

application = create_app()
