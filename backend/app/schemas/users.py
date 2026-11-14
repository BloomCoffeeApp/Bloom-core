from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM

# Built-in roles or a custom role key (validated against the roles table: services/roles.py).
ROLE_PATTERN = r"^[a-z0-9_]{1,20}$"


class UserPublic(ORM):
    id: int
    name: str
    role: str
    color: str
    # Free plan: this user can't log in (services/free_plan.py).
    locked: bool = False
    role_name: str | None = None


class UserMe(UserPublic):
    """The logged-in user: what the UI may show (permissions from services/roles.py)."""

    permissions: list[str] = []


class UserOut(UserPublic):
    active: bool
    last_login_at: datetime | None
    # Per-person exceptions over the role, and the resulting permissions (services/roles.py).
    perm_grants: list[str] = []
    perm_revokes: list[str] = []
    effective_permissions: list[str] = []


class UserPermissionsIn(BaseModel):
    grants: list[str] = []
    revokes: list[str] = []


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    pin: str = Field(pattern=r"^\d{4,6}$")
    role: str = Field(pattern=ROLE_PATTERN)
    color: str = "amber"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")
    role: str | None = Field(default=None, pattern=ROLE_PATTERN)
    color: str | None = None
    active: bool | None = None


class LoginIn(BaseModel):
    user_id: int
    pin: str
    # The staff phone app (`/equipo`) says so and shows the team code from the QR at the register.
    client: str | None = Field(default=None, pattern=r"^equipo$")
    team_key: str | None = Field(default=None, max_length=64)


class SessionOut(BaseModel):
    id: int
    client: str | None
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    current: bool = False


class LoginOut(BaseModel):
    token: str
    user: UserMe


class SetupIn(BaseModel):
    business_name: str = Field(min_length=1)
    admin_name: str = Field(min_length=1)
    admin_pin: str = Field(pattern=r"^\d{4,6}$")
    load_demo: bool = True
    # Business type chosen in the setup wizard (services/business_profile.py) and its module overrides.
    profile: str | None = None
    modules: dict[str, bool] = {}
