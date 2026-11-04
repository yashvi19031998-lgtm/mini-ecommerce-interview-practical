"""
Email address checks before auto-outreach (fewer bounces = Gmail account stays healthy).

can_receive_mail(email) is True when the email's domain has a mail server:
  - an MX record, or
  - no MX but an A/AAAA record (RFC 5321 "implicit MX").
Results are cached per domain for the whole run. If DNS itself is unavailable (no internet,
dnspython missing) the check returns True so outreach is not blocked by our own problem.
"""

import re
from functools import lru_cache

try:
    import dns.exception
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,})$")
DNS_TIMEOUT = 6.0


@lru_cache(maxsize=2048)
def domain_accepts_mail(domain: str) -> bool:
    if not DNS_AVAILABLE:
        return True
    domain = domain.lower().strip(".")
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=DNS_TIMEOUT)
        # A "null MX" (RFC 7505: preference 0, exchange ".") means the domain accepts no mail
        return any(str(r.exchange) not in (".", "") for r in answers)
    except dns.resolver.NXDOMAIN:
        return False  # domain does not exist
    except dns.resolver.NoAnswer:
        pass  # no MX: fall back to implicit MX (A/AAAA)
    except (dns.resolver.NoNameservers, dns.exception.Timeout):
        return True  # our DNS problem, not proof the address is bad
    for rtype in ("A", "AAAA"):
        try:
            dns.resolver.resolve(domain, rtype, lifetime=DNS_TIMEOUT)
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            continue
        except (dns.resolver.NoNameservers, dns.exception.Timeout):
            return True
    return False


def can_receive_mail(email: str) -> bool:
    m = EMAIL_RE.match((email or "").strip())
    return bool(m) and domain_accepts_mail(m.group(1))
