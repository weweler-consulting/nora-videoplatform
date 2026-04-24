import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


IconType = Literal["book", "video", "wa", "cal", "link"]
HeroVariant = Literal["berry", "dark", "pale"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_url(v: str) -> str:
    if not v:
        return v
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    return v


class HubLinkSchema(BaseModel):
    id: Optional[str] = None
    icon_type: IconType
    label: str = Field(min_length=1)
    sublabel: str = ""
    url: str = ""
    sort_order: int = 0

    @field_validator("url")
    @classmethod
    def _v_url(cls, v: str) -> str:
        return _validate_url(v)


class HubLiveCallSchema(BaseModel):
    id: Optional[str] = None
    tag: str = ""
    title: str = Field(min_length=1)
    body: str = ""
    sort_order: int = 0


class HubProductSchema(BaseModel):
    id: Optional[str] = None
    label: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    cta_text: str = "Zum Shop"
    url: str = ""
    image_url: str = ""
    highlight: bool = False
    sort_order: int = 0

    @field_validator("url")
    @classmethod
    def _v_url(cls, v: str) -> str:
        return _validate_url(v)


class HubDownloadSchema(BaseModel):
    id: Optional[str] = None
    title: str = Field(min_length=1)
    description: str = ""
    file_path: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_size_kb: int = 0
    sort_order: int = 0


class HubPayload(BaseModel):
    # Hero
    hero_variant: HeroVariant = "berry"
    hero_eyebrow: str = ""
    hero_title_html: str = ""
    hero_body: str = ""

    # Contact
    contact_user_id: Optional[str] = None
    contact_name_override: str = ""
    contact_role: str = "Kursleitung & Ernährungsberaterin"
    contact_email_override: str = ""
    contact_whatsapp_url: str = ""
    contact_photo_url: str = ""

    # Visibility flags
    show_contact: bool = True
    show_live_calls: bool = True
    show_products: bool = True
    show_downloads: bool = True

    # Lists
    links: list[HubLinkSchema] = []
    live_calls: list[HubLiveCallSchema] = []
    products: list[HubProductSchema] = []
    downloads: list[HubDownloadSchema] = []

    @field_validator("contact_whatsapp_url")
    @classmethod
    def _v_whatsapp(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("contact_email_override")
    @classmethod
    def _v_email(cls, v: str) -> str:
        if not v:
            return v
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


class UploadImageResponse(BaseModel):
    url: str


class UploadPdfResponse(BaseModel):
    file_path: str
    file_name: str
    file_size_kb: int
