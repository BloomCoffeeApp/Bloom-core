"""What the vendor's signed remote config says for this installation (banner + Acerca de)."""

from fastapi import APIRouter

from app import remote_config
from app.auth import CurrentUser
from app.models import User
from app.services import updates

router = APIRouter(prefix="/api/remote-config", tags=["remote-config"])


@router.get("")
def get_remote_config(_: User = CurrentUser) -> dict:
    return {
        "announcements": remote_config.announcements(),
        "support": remote_config.support(),
        **updates.support_status(),
    }
