from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class GameActionThrottle(UserRateThrottle):
    """Limits game actions like guessing to 10 per minute"""
    rate = '10/minute'


class GameCreateThrottle(UserRateThrottle):
    """Limits game creation to 5 per hour"""
    rate = '5/hour'


class ApiDefaultThrottle(UserRateThrottle):
    """Default rate limit for authenticated users"""
    rate = '60/minute'


class ApiAnonThrottle(AnonRateThrottle):
    """Default rate limit for anonymous users"""
    rate = '30/minute'
