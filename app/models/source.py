from datetime import datetime
from typing import Any
from pydantic import BaseModel,Field,HttpUrl

class SourceDocument(BaseModel):
    """
        经标准化处理的研究来源
    """
    source_id:str
    title:str=Field(min_length=1)
    url:HttpUrl

    source_type:str
    published_at:datetime|None=None

    summary:str=""
    clean_content:str=""

    content_hash:str|None=None
    metadata:dict[str,Any]=Field(default_factory=dict)
