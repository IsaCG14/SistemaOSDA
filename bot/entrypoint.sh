#!/bin/bash
# Entrypoint script for telegram-bot
# Sets up Python path and runs main()

set -e

cd /app

# Run everything in a single Python process with proper path setup
exec python -c "
import sys
import os

# Ensure /app is FIRST in Python path
sys.path.insert(0, '/app')

# Register bot module
import importlib.util
spec = importlib.util.spec_from_file_location('bot', '/app/__init__.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules['bot'] = module

# Now run the main module's main() function
import bot.main
import asyncio

asyncio.run(bot.main.main())
"