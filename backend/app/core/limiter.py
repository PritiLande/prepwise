"""
Shared rate-limiter instance.

WHY a separate module?
  Both main.py (which registers the exception handler and attaches the limiter
  to app.state) and analyze.py (which decorates the route) need the same
  Limiter object.  Defining it here breaks the circular import that would
  occur if analyze.py imported from main.py.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address reads the client IP from the request.
# Each unique IP gets its own counter — so one user can't burn
# another user's quota.
limiter = Limiter(key_func=get_remote_address)
