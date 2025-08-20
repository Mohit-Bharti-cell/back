from pydantic import BaseModel, EmailStr
from typing import List, Optional
from uuid import UUID


class Question(BaseModel):
    question: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None  # expected correct answer (server-side)


class TestRequest(BaseModel):
    topic: str
    difficulty: str
    num_questions: int
    question_type: Optional[str] = "mcq"
    mcq_count: Optional[int] = 0
    coding_count: Optional[int] = 0


class TestFinalizeRequest(BaseModel):
    questions: List[Question]
    duration: Optional[int] = 20  # minutes


class TestSubmission(BaseModel):
    candidate_id: UUID
    question_set_id: UUID
    questions: List[Question]          # for transparency/score calc
    answers: List[str]
    languages: Optional[List[str]] = None
    duration_used: Optional[int] = None  # seconds


class TestResponse(BaseModel):
    test_link: str
    test_id: str
    duration: int
    message: str


class CandidateLogin(BaseModel):
    email: EmailStr
