import hashlib

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class TableSessionThrottle(ScopedRateThrottle):
    """টেবিল-সেশন টোকেন ধরে রেট-লিমিট (একই ওয়াইফাইয়ের সবাই এক IP হলেও আলাদা গোনা হবে)।"""

    def get_cache_key(self, request, view):
        token = request.headers.get("X-Table-Session", "")
        ident = hashlib.sha1(token.encode()).hexdigest() if token else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class IpThrottle(SimpleRateThrottle):
    """টোকেন বদলে বদলে স্প্যাম ঠেকাতে উদার IP-লিমিট।"""

    scope = "customer_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RegisterThrottle(SimpleRateThrottle):
    scope = "register"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
