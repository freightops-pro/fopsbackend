from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.config.db import get_db
from app.services.feature_service import FeatureService, get_feature_service
from app.middleware.feature_middleware import require_enterprise_only
from app.models.team import Team, TeamMember
from app.models.chat import Conversation, Message, ConversationType
from app.models.userModels import Users, Driver, Companies
from app.routes.user import get_current_user
from app.schema.teamSchema import (
    TeamCreate, TeamUpdate, TeamResponse, TeamWithMembers,
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse
)
from app.schema.chatSchema import (
    ConversationCreateRequest, ConversationResponse,
    MessageCreateRequest, MessageResponse
)

router = APIRouter(prefix="/api/teams", tags=["Team Messaging"])


@router.post("/", response_model=TeamResponse)
def create_team(
    team_data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Create a new team (Enterprise only)"""
    company_id = current_user.companyid
    user_id = current_user.id
    
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'team_messaging')
    
    # Verify user exists and belongs to company
    if not current_user.isactive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active"
        )
    
    # Create team
    team = Team(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=team_data.name,
        description=team_data.description,
        is_private=team_data.is_private,
        created_by=user_id,
        created_by_type="user"
    )
    
    db.add(team)
    db.flush()  # Get the team ID
    
    # Add creator as admin
    team_member = TeamMember(
        id=str(uuid.uuid4()),
        team_id=team.id,
        member_id=user_id,
        member_type="user",
        role="admin"
    )
    
    db.add(team_member)
    
    # Update member count
    team.member_count = 1
    
    db.commit()
    db.refresh(team)
    
    return TeamResponse.from_orm(team)


@router.get("/", response_model=List[TeamResponse])
def list_company_teams(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """List all teams for a company (Enterprise only)"""
    company_id = current_user.companyid
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'team_messaging')
    
    teams = db.query(Team).filter(
        Team.company_id == company_id,
        Team.is_active == True
    ).all()
    
    return [TeamResponse.from_orm(team) for team in teams]


@router.get("/{team_id}", response_model=TeamWithMembers)
def get_team(
    team_id: str = Path(..., description="Team ID"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Get team details with members (Enterprise only)"""
    company_id = current_user.companyid
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'team_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return TeamWithMembers.from_orm(team)


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: str = Path(..., description="Team ID"),
    team_data: TeamUpdate = None,
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Update team (Enterprise only, admin required)"""
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'internal_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user is admin of the team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == user_id,
        TeamMember.role == "admin",
        TeamMember.is_active == True
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team admins can update team details"
        )
    
    # Update team fields
    if team_data.name is not None:
        team.name = team_data.name
    if team_data.description is not None:
        team.description = team_data.description
    if team_data.is_private is not None:
        team.is_private = team_data.is_private
    if team_data.is_active is not None:
        team.is_active = team_data.is_active
    
    db.commit()
    db.refresh(team)
    
    return TeamResponse.from_orm(team)


@router.post("/{team_id}/members", response_model=TeamMemberResponse)
def add_team_member(
    team_id: str = Path(..., description="Team ID"),
    member_data: TeamMemberCreate = None,
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID adding the member"),
    db: Session = Depends(get_db),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Add member to team (Enterprise only, admin required)"""
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'internal_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user is admin of the team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == user_id,
        TeamMember.role == "admin",
        TeamMember.is_active == True
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team admins can add members"
        )
    
    # Verify the member exists and belongs to company
    if member_data.member_type == "user":
        member = db.query(Users).filter(
            Users.id == member_data.member_id,
            Users.companyid == company_id,
            Users.isactive == True
        ).first()
    elif member_data.member_type == "driver":
        member = db.query(Driver).filter(
            Driver.id == member_data.member_id,
            Driver.companyId == company_id,
            Driver.status == "available"
        ).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid member type"
        )
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found or not active in company"
        )
    
    # Check if member is already in team
    existing_membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == member_data.member_id,
        TeamMember.is_active == True
    ).first()
    
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member is already in the team"
        )
    
    # Add member to team
    team_member = TeamMember(
        id=str(uuid.uuid4()),
        team_id=team_id,
        member_id=member_data.member_id,
        member_type=member_data.member_type,
        role=member_data.role
    )
    
    db.add(team_member)
    
    # Update member count
    team.member_count += 1
    
    db.commit()
    db.refresh(team_member)
    
    return TeamMemberResponse.from_orm(team_member)


@router.delete("/{team_id}/members/{member_id}")
def remove_team_member(
    team_id: str = Path(..., description="Team ID"),
    member_id: str = Path(..., description="Member ID to remove"),
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID removing the member"),
    db: Session = Depends(get_db),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Remove member from team (Enterprise only, admin required)"""
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'internal_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user is admin of the team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == user_id,
        TeamMember.role == "admin",
        TeamMember.is_active == True
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team admins can remove members"
        )
    
    # Find the membership to remove
    member_to_remove = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == member_id,
        TeamMember.is_active == True
    ).first()
    
    if not member_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in team"
        )
    
    # Deactivate membership
    member_to_remove.is_active = False
    
    # Update member count
    team.member_count -= 1
    
    db.commit()
    
    return {"message": "Member removed from team successfully"}


@router.post("/{team_id}/conversation", response_model=ConversationResponse)
def create_team_conversation(
    team_id: str = Path(..., description="Team ID"),
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID creating conversation"),
    db: Session = Depends(get_db),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Create team conversation (Enterprise only)"""
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'internal_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user is member of the team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == user_id,
        TeamMember.is_active == True
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team members can create team conversations"
        )
    
    # Check if team conversation already exists
    existing_conversation = db.query(Conversation).filter(
        Conversation.team_id == team_id,
        Conversation.conversation_type == ConversationType.TEAM,
        Conversation.company_id == company_id
    ).first()
    
    if existing_conversation:
        return ConversationResponse.from_orm(existing_conversation)
    
    # Create team conversation
    conversation = Conversation(
        id=str(uuid.uuid4()),
        company_id=company_id,
        conversation_type=ConversationType.TEAM,
        team_id=team_id,
        team_name=team.name,
        created_by=user_id,
        created_by_type="user"
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return ConversationResponse.from_orm(conversation)


@router.get("/{team_id}/conversation", response_model=ConversationResponse)
def get_team_conversation(
    team_id: str = Path(..., description="Team ID"),
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    feature_service: FeatureService = Depends(get_feature_service)
):
    """Get team conversation (Enterprise only)"""
    # Check if company has Enterprise tier
    feature_service.require_feature_access(company_id, 'internal_messaging')
    
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.company_id == company_id,
        Team.is_active == True
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user is member of the team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.member_id == user_id,
        TeamMember.is_active == True
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team members can access team conversations"
        )
    
    conversation = db.query(Conversation).filter(
        Conversation.team_id == team_id,
        Conversation.conversation_type == ConversationType.TEAM,
        Conversation.company_id == company_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team conversation not found"
        )
    
    return ConversationResponse.from_orm(conversation)
