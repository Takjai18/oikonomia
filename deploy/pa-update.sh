#!/bin/bash
# Run on PythonAnywhere Bash console after code is pushed to GitHub.
# Production: https://takjai.pythonanywhere.com

set -e
cd ~/oikonomia
git pull origin main
echo ""
echo "Code updated. Now: Web tab → Reload takjai.pythonanywhere.com"