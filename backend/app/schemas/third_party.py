from pydantic import BaseModel


class ThirdPartyPackage(BaseModel):
    name: str
    version: str
    license: str
    source: str  # frontend | backend | runtime
    homepage: str = ""
    copyright: list[str] = []
    text: str = ""
    note: str = ""


class ThirdPartyNotices(BaseModel):
    available: bool
    generated_at: str | None = None
    packages: list[ThirdPartyPackage] = []
