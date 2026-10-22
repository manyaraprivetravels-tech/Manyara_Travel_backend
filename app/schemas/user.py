from datetime import datetime
from enum import Enum

from app.models.user import RoleEnum

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr

    password: str = Field(min_length=6, max_length=72)
    confirm_password: str = Field(min_length=6, max_length=72)

    role: RoleEnum = RoleEnum.creator

    # Required only when creating another admin
    admin_verification_password: str | None = Field(
        default=None,
        min_length=6,
        max_length=72,
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: RoleEnum
    is_active: bool
    created_at: datetime | None=None 
    last_activity_at: datetime | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdateStatus(BaseModel):
    is_active: bool
