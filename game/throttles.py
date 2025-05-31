from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class GameActionThrottle(UserRateThrottle):
    rate = '10/minute'


class GameCreateThrottle(UserRateThrottle):
    rate = '5/hour'


class ApiDefaultThrottle(UserRateThrottle):
    rate = '60/minute'


class ApiAnonThrottle(AnonRateThrottle):
    rate = '30/minute'
