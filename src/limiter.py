import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "20/minute")
RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "10/minute")
RATE_LIMIT_WEATHER = os.getenv("RATE_LIMIT_WEATHER", "60/minute")
RATE_LIMIT_SHADOW = os.getenv("RATE_LIMIT_SHADOW", "30/minute")
