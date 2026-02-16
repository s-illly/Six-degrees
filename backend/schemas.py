from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    email: str 
    password: str 
    linkedin_slug: str 

class ConnectionsRequest(BaseModel):
    linkedin_slug: str 

class UserPublic(BaseModel):
    full_name: str 
    linkedin_slug: str 