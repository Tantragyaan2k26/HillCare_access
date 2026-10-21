"""Authentication and role-based access control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from config import ENVIRONMENT


@dataclass
class AuthUser:
    id: str
    email: str
    role: str
    org_id: Optional[str] = None


ROLE_HIERARCHY = {
    "anonymous": 0,
    "planner": 1,
    "analyst": 2,
    "admin": 3,
}


async def get_current_user(
    x_user_role: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
) -> AuthUser:
    """Resolve identity from development headers only when explicitly enabled."""
    dev_auth_enabled = (
        ENVIRONMENT.lower() == "development"
        and os.getenv("HILLCARE_ENABLE_DEV_AUTH", "").strip().lower()
        in {"1", "true", "yes"}
    )
    if dev_auth_enabled and x_user_role:
        role = x_user_role.lower()
        if role not in ROLE_HIERARCHY:
            role = "anonymous"
        return AuthUser(
            id=x_user_id or f"dev_{role}_user",
            email=f"{role}@hillcare.org",
            role=role,
            org_id="uttarakhand_health_dept",
        )

    return AuthUser(id="anon", email="anon@public.org", role="anonymous")


def require_role(min_role: str):
    """Dependency factory checking that user role meets minimum required role level."""
    min_level = ROLE_HIERARCHY.get(min_role, 0)

    async def _role_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires at least '{min_role}' privileges (current: '{user.role}')",
            )
        return user

    return _role_checker
