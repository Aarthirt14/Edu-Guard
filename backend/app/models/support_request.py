from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class SupportRequest(Base):
    __tablename__ = 'support_requests'
    __table_args__ = (UniqueConstraint('student_id', 'submission_key'),)
    id = Column(Integer, primary_key=True)
    student_id = Column(String, ForeignKey('students.id'), nullable=False, index=True)
    submission_key = Column(String, nullable=False)
    category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default='Open')
    owner_id = Column(String, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    replies = relationship('SupportReply', cascade='all, delete-orphan', order_by='SupportReply.id')


class SupportReply(Base):
    __tablename__ = 'support_replies'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('support_requests.id'), nullable=False)
    author_id = Column(String, ForeignKey('users.id'), nullable=False)
    author_name = Column(String, nullable=False)
    author_role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
