from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default='user', pattern='^(admin|user)$')


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime


class PasswordChangeRequest(BaseModel):
    username: str
    new_password: str = Field(min_length=8, max_length=128)


class ServiceActionRequest(BaseModel):
    service: str


class DriveFormatRequest(BaseModel):
    device: str
    fs_type: str = Field(pattern='^(ext4)$')
    confirmation: str


class MountRequest(BaseModel):
    device: str
    mountpoint: str


class FileActionRequest(BaseModel):
    path: str
    new_name: Optional[str] = None


class MkdirRequest(BaseModel):
    path: str
    name: str


class BulkDownloadRequest(BaseModel):
    paths: list[str]


class ShareCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    folder: str
    access: str = Field(pattern='^(everyone|specific)$')
    users: list[str] = Field(default_factory=list)


class ShareRemoveRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')


class UserUpdateRequest(BaseModel):
    role: str = Field(pattern='^(admin|user)$')
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class HostnameUpdateRequest(BaseModel):
    hostname: str = Field(min_length=2, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9-]*$')


class TimezoneUpdateRequest(BaseModel):
    timezone: str = Field(min_length=2, max_length=128)


class SelfPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DriveInfo(BaseModel):
    name: str
    device: str
    fstype: Optional[str]
    size: Optional[str]
    mountpoint: Optional[str]
    used_bytes: Optional[int]
    free_bytes: Optional[int]
    model: Optional[str]
    transport: Optional[str]
    smart_status: Optional[str] = None


class ApiResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[Any] = None


class NetworkConfigRequest(BaseModel):
    interface: str = Field(min_length=2, max_length=32)
    mode: str = Field(pattern='^(dhcp|static)$')
    address: Optional[str] = None
    gateway: Optional[str] = None
    dns: Optional[str] = None


class UsbShareRequest(BaseModel):
    device: str
    share_name: str = Field(min_length=2, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    mountpoint: Optional[str] = None
    format_before_mount: bool = False
    fs_type: Optional[str] = Field(default=None, pattern='^(ext4|exfat)$')
    wipe_repartition: bool = False
    wipe_confirmation: Optional[str] = None
