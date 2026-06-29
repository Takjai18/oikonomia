# Paste this ENTIRE file into PythonAnywhere Web tab -> WSGI configuration file.
# Then set Virtualenv path to: /home/takjai/oikonomia/venv
# Then click Reload.

import sys

sys.path.insert(0, "/home/takjai/oikonomia")

from wsgi import application