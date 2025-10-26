from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from app.models.chat import Conversation, ConversationReadStatus, Message
from app.models.userModels import Users, Driver
from app.schema.chatSchema import (
    ConversationCreateRequest, ConversationResponse,
    MessageCreateRequest, MessageResponse,
    ConversationListResponse, MessageWithDetailsResponse
)

class ChatService:
    """Service class for chat operations"""
    
    def __init__(self, db: Session):
        self.db = db

    # Conversation Operations
    
    async def create_conversation(self, company_id: str, participant_id: str, participant_type: str,
                                conversation_data: ConversationCreateRequest) -> ConversationResponse:
        """Create a new 1-on-1 conversation between users and/or drivers"""
        
        # Validate that the other participant exists and belongs to the company
        other_participant = None
        if conversation_data.other_participant_type == "user":
            other_participant = self.db.query(Users).filter(
                and_(
                    Users.id == conversation_data.other_participant_id,
                    Users.companyid == company_id,
                    Users.isactive == True
                )
            ).first()
        elif conversation_data.other_participant_type == "driver":
            other_participant = self.db.query(Driver).filter(
                and_(
                    Driver.id == conversation_data.other_participant_id,
                    Driver.companyId == company_id,
                    Driver.status == "available"
                )
            ).first()
        
        if not other_participant:
            raise ValueError("Other participant not found or not in the same company")
        
        if other_participant.id == participant_id:
            raise ValueError("Cannot start a conversation with yourself")
        
        # Check if conversation already exists between these two participants
        existing_conversation = self.db.query(Conversation).filter(
            and_(
                Conversation.company_id == company_id,
                Conversation.is_active == True,
                or_(
                    and_(
                        Conversation.participant1_id == participant_id,
                        Conversation.participant1_type == participant_type,
                        Conversation.participant2_id == conversation_data.other_participant_id,
                        Conversation.participant2_type == conversation_data.other_participant_type
                    ),
                    and_(
                        Conversation.participant1_id == conversation_data.other_participant_id,
                        Conversation.participant1_type == conversation_data.other_participant_type,
                        Conversation.participant2_id == participant_id,
                        Conversation.participant2_type == participant_type
                    )
                )
            )
        ).first()
        
        if existing_conversation:
            return ConversationResponse.from_orm(existing_conversation)
        
        # Create new conversation
        conversation = Conversation(
            id=str(uuid.uuid4()),
            company_id=company_id,
            participant1_id=participant_id,
            participant1_type=participant_type,
            participant2_id=conversation_data.other_participant_id,
            participant2_type=conversation_data.other_participant_type,
            created_by=participant_id,
            created_by_type=participant_type,
            is_active=True
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        # Create read status entries for both participants
        participants = [
            (participant_id, participant_type),
            (conversation_data.other_participant_id, conversation_data.other_participant_type)
        ]
        
        for p_id, p_type in participants:
            read_status = ConversationReadStatus(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                participant_id=p_id,
                participant_type=p_type,
                company_id=company_id,
                unread_count=0
            )
            self.db.add(read_status)
        
        self.db.commit()
        
        return ConversationResponse.from_orm(conversation)

    async def get_conversation(self, conversation_id: str, company_id: str) -> Optional[ConversationResponse]:
        """Get a specific conversation"""
        conversation = self.db.query(Conversation).filter(
            and_(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
                Conversation.is_active == True
            )
        ).first()
        
        if not conversation:
            return None
        
        return ConversationResponse.from_orm(conversation)

    async def get_participant_conversations(self, participant_id: str, participant_type: str, company_id: str, 
                                   limit: int = 50, offset: int = 0) -> List[ConversationListResponse]:
        """Get conversations for a participant"""
        # Get conversations where participant is either participant1 or participant2
        conversations = self.db.query(Conversation).filter(
            and_(
                Conversation.company_id == company_id,
                Conversation.is_active == True,
                or_(
                    and_(Conversation.participant1_id == participant_id, Conversation.participant1_type == participant_type),
                    and_(Conversation.participant2_id == participant_id, Conversation.participant2_type == participant_type)
                )
            )
        ).order_by(desc(Conversation.last_message_at)).offset(offset).limit(limit).all()
        
        result = []
        for conv in conversations:
            # Determine the other participant
            if conv.participant1_id == participant_id and conv.participant1_type == participant_type:
                other_participant_id = conv.participant2_id
                other_participant_type = conv.participant2_type
            else:
                other_participant_id = conv.participant1_id
                other_participant_type = conv.participant1_type
            
            # Get other participant info
            if other_participant_type == 'user':
                other_participant = self.db.query(Users).filter(Users.id == other_participant_id).first()
                other_participant_name = f"{other_participant.firstname} {other_participant.lastname}" if other_participant else "Unknown User"
            else:  # driver
                other_participant = self.db.query(Driver).filter(Driver.id == other_participant_id).first()
                other_participant_name = f"{other_participant.firstName} {other_participant.lastName}" if other_participant else "Unknown Driver"
            
            # Get last message
            last_message = self.db.query(Message).filter(
                and_(
                    Message.conversation_id == conv.id,
                    Message.is_deleted == False
                )
            ).order_by(desc(Message.created_at)).first()
            
            # Get unread count
            read_status = self.db.query(ConversationReadStatus).filter(
                and_(
                    ConversationReadStatus.conversation_id == conv.id,
                    ConversationReadStatus.participant_id == participant_id,
                    ConversationReadStatus.participant_type == participant_type
                )
            ).first()
            
            unread_count = read_status.unread_count if read_status else 0
            
            result.append(ConversationListResponse(
                id=conv.id,
                other_participant_id=other_participant_id,
                other_participant_type=other_participant_type,
                other_participant_name=other_participant_name,
                last_message_content=last_message.content if last_message else None,
                last_message_at=last_message.created_at if last_message else None,
                unread_count=unread_count
            ))
        
        return result

    # Message Operations
    
    async def create_message(self, company_id: str, participant_id: str, participant_type: str,
                           message_data: MessageCreateRequest) -> MessageResponse:
        """Create a new message"""
        # Verify participant is part of the conversation
        conversation = self.db.query(Conversation).filter(
            and_(
                Conversation.id == message_data.conversation_id,
                Conversation.company_id == company_id,
                Conversation.is_active == True,
                or_(
                    and_(Conversation.participant1_id == participant_id, Conversation.participant1_type == participant_type),
                    and_(Conversation.participant2_id == participant_id, Conversation.participant2_type == participant_type)
                )
            )
        ).first()
        
        if not conversation:
            raise ValueError("Conversation not found or participant not authorized")
        
        # Create message
        message = Message(
            id=str(uuid.uuid4()),
            conversation_id=message_data.conversation_id,
            sender_id=participant_id,
            sender_type=participant_type,
            company_id=company_id,
            content=message_data.content,
            message_type=message_data.message_type,
            reply_to_message_id=message_data.reply_to_message_id,
            is_deleted=False
        )
        
        self.db.add(message)
        
        # Update conversation metadata
        conversation.last_message_at = datetime.utcnow()
        conversation.message_count += 1
        
        # Update unread counts for the other participant
        if conversation.participant1_id == participant_id and conversation.participant1_type == participant_type:
            other_participant_id = conversation.participant2_id
            other_participant_type = conversation.participant2_type
        else:
            other_participant_id = conversation.participant1_id
            other_participant_type = conversation.participant1_type
            
        read_status = self.db.query(ConversationReadStatus).filter(
            and_(
                ConversationReadStatus.conversation_id == message_data.conversation_id,
                ConversationReadStatus.participant_id == other_participant_id,
                ConversationReadStatus.participant_type == other_participant_type
            )
        ).first()
        
        if read_status:
            read_status.unread_count += 1
        
        self.db.commit()
        self.db.refresh(message)
        
        return MessageResponse.from_orm(message)

    async def get_conversation_messages(self, conversation_id: str, participant_id: str, participant_type: str, company_id: str,
                                      limit: int = 50, offset: int = 0) -> List[MessageWithDetailsResponse]:
        """Get messages for a conversation"""
        # Verify participant is part of the conversation
        conversation = self.db.query(Conversation).filter(
            and_(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
                Conversation.is_active == True,
                or_(
                    and_(Conversation.participant1_id == participant_id, Conversation.participant1_type == participant_type),
                    and_(Conversation.participant2_id == participant_id, Conversation.participant2_type == participant_type)
                )
            )
        ).first()
        
        if not conversation:
            raise ValueError("Conversation not found or participant not authorized")
        
        # Get messages
        messages = self.db.query(Message).filter(
            and_(
                Message.conversation_id == conversation_id,
                Message.is_deleted == False
            )
        ).order_by(desc(Message.created_at)).offset(offset).limit(limit).all()
        
        result = []
        for msg in messages:
            # Get sender info based on sender_type
            sender_info = None
            if msg.sender_type == 'user':
                sender = self.db.query(Users).filter(Users.id == msg.sender_id).first()
                sender_info = {
                    "id": sender.id,
                    "name": f"{sender.firstname} {sender.lastname}",
                    "email": sender.email
                } if sender else None
            else:  # driver
                sender = self.db.query(Driver).filter(Driver.id == msg.sender_id).first()
                sender_info = {
                    "id": sender.id,
                    "name": f"{sender.firstName} {sender.lastName}",
                    "email": sender.email
                } if sender else None
            
            # Get reply message if exists
            reply_to_message = None
            if msg.reply_to_message_id:
                reply_msg = self.db.query(Message).filter(Message.id == msg.reply_to_message_id).first()
                if reply_msg:
                    reply_to_message = MessageResponse.from_orm(reply_msg)
            
            result.append(MessageWithDetailsResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                sender_id=msg.sender_id,
                sender_type=msg.sender_type,
                company_id=msg.company_id,
                content=msg.content,
                message_type=msg.message_type,
                reply_to_message_id=msg.reply_to_message_id,
                is_deleted=msg.is_deleted,
                deleted_at=msg.deleted_at,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
                sender=sender_info,
                reply_to_message=reply_to_message
            ))
        
        return result