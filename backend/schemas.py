from pydantic import BaseModel

class ConnectionsRequest(BaseModel):
    full_name: str
    linkedin_slug: str 

class UserPublic(BaseModel):
    full_name: str 
    linkedin_slug: str 

class ClaimSlugRequest(BaseModel):
    linkedin_slug: str