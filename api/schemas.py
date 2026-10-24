from pydantic import BaseModel,Field
from typing import Literal
class Message(BaseModel):
 role:Literal['system','user','assistant'];content:str=Field(min_length=1,max_length=100000)
class ChatRequest(BaseModel):
 model:str|None=None;messages:list[Message]=Field(min_length=1,max_length=100);temperature:float=Field(default=.7,ge=0,le=2);max_tokens:int=Field(default=1024,ge=1,le=32768);stream:bool=False;response_format:dict|None=None
