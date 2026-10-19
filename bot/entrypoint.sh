#!/bin/bash
# Entrypoint script for telegram-bot
# Registers the bot module and runs main() in a single Python process

set -e

cd /app

# Run everything in a single Python process
exec python -c "
import sys
import importlib.util

# Manually load the bot module and register it
spec = importlib.util.spec_from_file_location('bot', '/app/__init__.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules['bot'] = module

# Now run the main module's main() function
import bot.main
import asyncio

asyncio.run(bot.main.main())
"