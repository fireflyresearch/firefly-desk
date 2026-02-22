# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Authentication and authorization for Firefly Desk."""

from flydek.auth.middleware import AuthMiddleware
from flydek.auth.models import UserSession

__all__ = ["AuthMiddleware", "UserSession"]
