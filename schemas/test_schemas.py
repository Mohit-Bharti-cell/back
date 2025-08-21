from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class Question(BaseModel):
    question: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None

class TestRequest(BaseModel):
    topic: str
    difficulty: str
    num_questions: int
    question_type: Optional[str] = "mcq"
    mcq_count: Optional[int] = 0
    coding_count: Optional[int] = 0
    jd_id: Optional[str] = None

class TestFinalizeRequest(BaseModel):
    questions: List[Question]
    duration: Optional[int] = 20
    jd_id: str

class TestSubmission(BaseModel):
    question_set_id: UUID
    candidate_id: str
    candidate_name:str
    candidate_email:str
    candidate_id: str
    questions: List[Question]
    answers: List[str]
    languages: Optional[List[str]] = None
    duration_used: Optional[int] = None

class TestResponse(BaseModel):
    test_link: str
    test_id: str
    duration: int
    message: str

class CandidateLoginRequest(BaseModel):
    email: str

class CandidateLoginResponse(BaseModel):
    email: str
    candidate_id: str
    name: str
    message: str
