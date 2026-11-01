"""Licensing: Free vs Pro.

A license is a token signed with the vendor's Ed25519 private key (kept in the private
license server). The app only holds the public key, so it can verify a license offline
but never forge one. Tokens are bound to this machine and carry the paid-through date;
after it, a grace period keeps everything working while the app can't reach the server.

Nothing here ever blocks access to the business' own day-to-day operation: when a
license lapses only Pro features turn off.
"""

from app.licensing.features import PRO_FEATURES, check_free_limit, free_limits, has_feature, require_feature
from app.licensing.status import LicenseStatus, current_status

__all__ = [
    "check_free_limit",
    "free_limits",
    "PRO_FEATURES",
    "LicenseStatus",
    "current_status",
    "has_feature",
    "require_feature",
]
