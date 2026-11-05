from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM

ROLE_PATTERN = r"^(admin|encargado|cajero|barista)$"


class UserPublic(ORM):
    id: int
    name: str
    role: str
    color: str
    # Free plan: this user can't log in (services/free_plan.py).
    locked: bool = False


class UserOut(UserPublic):
    active: bool
    last_login_at: datetime | None


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


class LoginOut(BaseModel):
    token: str
    user: UserPublic


class SetupIn(BaseModel):
    business_name: str = Field(min_length=1)
    admin_name: str = Field(min_length=1)
    admin_pin: str = Field(pattern=r"^\d{4,6}$")
    load_demo: bool = True
    # Business type chosen in the setup wizard (services/business_profile.py) and its module overrides.
    profile: str | None = None
    modules: dict[str, bool] = {}
