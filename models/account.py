from typing import Optional
from pydantic import BaseModel


class MLAccount(BaseModel):
    """Vinculo entre um usuario do sistema e uma conta ML (dados do seller no ML)."""
    orus_user_id: str
    ml_user_id: int
    ml_nickname: str
    ml_email: Optional[str] = None
    site_id: str = "MLB"
    is_active: bool = True


class MLTokens(BaseModel):
    """Tokens OAuth vinculados a uma MLAccount."""
    ml_user_id: int
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None
    expires_at: int
    obtained_at: int
