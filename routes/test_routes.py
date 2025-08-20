from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Optional

from db.supabase import supabase
from schemas.test_schemas import CandidateLogin, TestSubmission
from controller import candidate_login_controller, submit_test_controller  # controller.py at project root

router = APIRouter()


@router.post("/candidate-login")
async def candidate_login(payload: CandidateLogin):
    """
    Initializes/ensures a single candidate row exists in test_results
    with status='Not Started'. Data comes from the external HR API.
    """
    return await candidate_login_controller(payload.email)


@router.get("/{question_set_id}")
async def fetch_test(question_set_id: str):
    """
    Returns the questions + duration for a given question_set_id.
    Enforces expiry based on question_sets.expires_at (timestamptz).
    """
    # Fetch question set
    res = supabase.table("question_sets").select("*").eq("id", question_set_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Test not found")

    test_info = res.data[0]
    expires_at: Optional[str] = test_info.get("expires_at")
    duration = test_info.get("duration", 20)  # minutes

    # Expiry check
    if expires_at:
        # robust ISO parsing including Z suffix
        try:
            expires_dt = (
                datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if isinstance(expires_at, str)
                else expires_at
            )
        except Exception:
            raise HTTPException(status_code=500, detail="Invalid expires_at format in DB")

        now = datetime.now(timezone.utc)
        if now > expires_dt:
            raise HTTPException(status_code=410, detail="Test expired")

    # Fetch questions
    q_res = (
        supabase.table("questions")
        .select("question, options")
        .eq("question_set_id", question_set_id)
        .execute()
    )
    if not q_res.data:
        raise HTTPException(status_code=404, detail="No questions found")

    return {
        "questions": q_res.data,
        "duration": duration,
        "test_id": question_set_id,
    }


@router.post("/submit")
async def submit_test(submission: TestSubmission):
    """
    Evaluates answers and UPDATES the existing candidate row in test_results
    (matched by candidate_id). Does NOT insert a new row.
    """
    return await submit_test_controller(submission)
