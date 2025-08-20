import httpx
from fastapi import HTTPException
from datetime import datetime, timezone
from db.supabase import supabase
from services.test_evaluator import evaluate_test


HR_API_URL = "http://localhost:5000/get-filteredCandidateByEmail"


async def candidate_login_controller(email: str):
    """
    Fetches candidate {email, candidate_id, name} from external HR API.
    Ensures a single row exists in test_results with status='Not Started'.
    If row already exists, returns the existing row.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(HR_API_URL, params={"email": email})
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Candidate not found from HR API")

        candidate = resp.json()  # expected: { "email": "...", "candidate_id": "...", "name": "..." }

    # Basic validation
    for key in ("email", "candidate_id", "name"):
        if key not in candidate or not candidate[key]:
            raise HTTPException(status_code=400, detail=f"HR API missing field: {key}")

    candidate_id = str(candidate["candidate_id"])

    # Check if candidate already exists
    existing = (
        supabase.table("test_results")
        .select("*")
        .eq("candidate_id", candidate_id)
        .execute()
    )

    if existing.data:
        # If exists but missing email/name, backfill
        row = existing.data[0]
        patch = {}
        if not row.get("email"):
            patch["email"] = candidate["email"]
        if not row.get("name"):
            patch["name"] = candidate["name"]
        if patch:
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated = (
                supabase.table("test_results")
                .update(patch)
                .eq("candidate_id", candidate_id)
                .execute()
            )
            if updated.data:
                row = updated.data[0]
        return {"message": "Candidate already exists", "data": row}

    # Insert new candidate with "Not Started"
    new_entry = {
        "candidate_id": candidate_id,
        "email": candidate["email"],
        "name": candidate["name"],
        "status": "Not Started",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    result = supabase.table("test_results").insert(new_entry).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert candidate row")

    return {"message": "Candidate added", "data": result.data[0]}


async def submit_test_controller(submission):
    """
    Evaluates answers & updates test_results row instead of inserting new.
    The row is located by candidate_id. Also stamps updated_at and completed_at.
    """
    # Evaluate
    result = await evaluate_test(submission)

    # Duration conversions
    duration_used_minutes = None
    if getattr(submission, "duration_used", None):
        duration_used_minutes = round(submission.duration_used / 60, 2)

    # Ensure candidate_id present
    if not getattr(submission, "candidate_id", None):
        raise HTTPException(status_code=400, detail="candidate_id is required")

    candidate_id = str(submission.candidate_id)

    # Ensure row exists
    existing = (
        supabase.table("test_results")
        .select("*")
        .eq("candidate_id", candidate_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Candidate not found in test_results")

    # Prepare update payload
    update_data = {
        "question_set_id": str(submission.question_set_id),
        "score": result.get("score", 0),
        "max_score": result.get("max_score", len(submission.questions) * 10),
        "percentage": result.get("percentage", 0.0),
        "status": result.get("status", "Completed") or "Completed",
        "total_questions": len(submission.questions),
        "raw_feedback": result.get("raw_feedback", ""),
        "duration_used_seconds": getattr(submission, "duration_used", None),
        "duration_used_minutes": duration_used_minutes,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    db_result = (
        supabase.table("test_results")
        .update(update_data)
        .eq("candidate_id", candidate_id)
        .execute()
    )

    if not db_result.data:
        raise HTTPException(status_code=500, detail="Failed to update test results")

    # return concise response for frontend
    return {
        "score": update_data["score"],
        "max_score": update_data["max_score"],
        "percentage": update_data["percentage"],
        "status": update_data["status"],
        "raw_feedback": update_data["raw_feedback"],
        "result_id": db_result.data[0].get("id"),
        "duration_used": duration_used_minutes,
    }
