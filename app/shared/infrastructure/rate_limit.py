"""Rate limiting infrastructure using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Export the key function for testing
get_key_func = get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
)
