from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

Lang = Literal["he", "en"]

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class UserInfo(BaseModel):
    firstName: str = ""
    lastName: str = ""
    id: str = ""               # 9 digits
    gender: str = ""
    age: int = 0               # 0..120
    hmo: str = ""              # מכבי | מאוחדת | כללית | Maccabi | Meuhedet | Clalit
    hmoCard: str = ""          # 9 digits
    tier: str = ""             # זהב | כסף | ארד | Gold | Silver | Bronze

    @field_validator("id")
    @classmethod
    def id_9digits(cls, v: str) -> str:
        digits = "".join([c for c in v if c.isdigit()])
        return digits if len(digits) == 9 else v

    @field_validator("hmoCard")
    @classmethod
    def card_9digits(cls, v: str) -> str:
        digits = "".join([c for c in v if c.isdigit()])
        return digits if len(digits) == 9 else v

    @field_validator("age")
    @classmethod
    def age_range(cls, v: int) -> int:
        try:
            iv = int(v)
        except Exception:
            return 0
        return iv if 0 <= iv <= 120 else iv

class CollectRequest(BaseModel):
    history: List[Message] = Field(default_factory=list)
    user_info: UserInfo = Field(default_factory=UserInfo)
    lang: Lang = "he"

class CollectResponse(BaseModel):
    phase: Literal["ASK","CONFIRM","DONE"]
    message: str
    missing: List[str]
    userinfo: UserInfo
    lang: Lang

class ChatRequest(BaseModel):
    history: List[Message] = Field(default_factory=list)
    user_info: UserInfo
    question: str
    lang: Lang = "he"

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
