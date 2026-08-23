from pydantic import BaseModel


class User(BaseModel):
    """Usuario do sistema Orus (dono ou operador)."""
    user_id: str
    email: str
    name: str
    is_active: bool = True
