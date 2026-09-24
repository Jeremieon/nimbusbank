from datetime import datetime

from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    subject: str = Field(max_length=200)
    body: str = Field(max_length=5000)


class PostMessageRequest(BaseModel):
    # sender is trusted from the client with no verification — a "customer" can
    # post as an "agent" and vice versa. body is stored verbatim (see the XSS
    # comment in models.py).
    sender: str = Field(default="customer", max_length=20)
    body: str = Field(max_length=5000)


class MessageOut(BaseModel):
    id: int
    ticket_id: int
    sender: str
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: int
    user_id: str
    subject: str
    status: str
    created_at: datetime


class TicketDetailOut(TicketOut):
    messages: list[MessageOut]
