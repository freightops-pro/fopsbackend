from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func, Integer, Text, JSON
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.config.db import Base
import uuid


class Team(Base):
    """Teams for Enterprise internal messaging"""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    
    # Team Information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Team Settings
    is_private = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Team Metadata
    member_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(36), nullable=False)  # User ID who created the team
    created_by_type = Column(String(10), nullable=False, default="user")  # 'user' or 'driver'
    
    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    conversations = relationship("Conversation", foreign_keys="[Conversation.team_id]", backref="team")
    company = relationship("Companies", backref="teams")


class TeamMember(Base):
    """Team membership for Enterprise teams"""
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    
    # Member Information
    member_id = Column(String(36), nullable=False)  # Generic ID (user or driver)
    member_type = Column(String(10), nullable=False)  # 'user' or 'driver'
    
    # Member Role in Team
    role = Column(String(20), nullable=False, default="member")  # 'admin', 'member'
    
    # Membership Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    joined_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="members")


# Pydantic Models for API

class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_private: bool = False


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_private: Optional[bool] = None
    is_active: Optional[bool] = None


class TeamResponse(TeamBase):
    id: str
    company_id: str
    is_active: bool
    member_count: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_by_type: str
    
    model_config = ConfigDict(from_attributes=True)


class TeamMemberBase(BaseModel):
    member_id: str
    member_type: str
    role: str = "member"


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberResponse(TeamMemberBase):
    id: str
    team_id: str
    is_active: bool
    joined_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TeamWithMembers(TeamResponse):
    members: List[TeamMemberResponse] = []
