"""Customer utility functions for managing customer selection and data access."""

import os
import json
import asyncio
from typing import Optional


def get_selected_customer_id() -> str:
    """Get the currently selected customer ID from config file."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'customer_config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get('selected_customer_id', 'CUST_001')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 'CUST_001'


def run_async(coro):
    """Helper function to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, we can't use run_until_complete
            # This is typically the case in Jupyter notebooks or some web frameworks
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop in current thread, create a new one
        return asyncio.run(coro)