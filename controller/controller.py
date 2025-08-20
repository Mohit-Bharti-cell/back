import httpx
from fastapi import HTTPException
from db.supabase import supabase
from services.test_evaluator import evaluate_test


async def candidate_login_controller(email: str):
    """Fetch candidate details from external API and insert into test_results if new."""

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "http://localhost:5000/get-filteredCandidateByEmail",
            params={"email": email}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Candidate not found")

        candidate = resp.json()  # { email, candidate_id, name }

    # Check if candidate already exists
    existing = supabase.table("test_results") \
        .select("*") \
        .eq("candidate_id", candidate["candidate_id"]) \
        .execute()

    if existing.data:
        return {"message": "Candidate already exists", "data": existing.data[0]}

    # Insert new candidate with "Not Started"
    new_entry = {
        "candidate_id": candidate["candidate_id"],
        "email": candidate["email"],
        "name": candidate["name"],
        "status": "Not Started"
    }
    result = supabase.table("test_results").insert(new_entry).execute()
    return {"message": "Candidate added", "data": result.data[0]}


async def submit_test_controller(submission):
    """Evaluate answers & update test_results row instead of inserting new row."""

    # Evaluate test
    result = await evaluate_test(submission)

    # Calculate duration in minutes
    duration_used_minutes = None
    if submission.duration_used:
        duration_used_minutes = round(submission.duration_used / 60, 2)

    # Ensure candidate_id is present
    if not submission.candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")

    # Check if candidate exists
    existing = supabase.table("test_results") \
        .select("*") \
        .eq("candidate_id", submission.candidate_id) \
        .execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Candidate not found in test_results")

    update_data = {
        "question_set_id": str(submission.question_set_id),
        "score": result.get("score", 0),
        "max_score": result.get("max_score", len(submission.questions) * 10),
        "percentage": result.get("percentage", 0.0),
        "status": "Completed",
        "total_questions": len(submission.questions),
        "raw_feedback": result.get("raw_feedback", ""),
        "duration_used_seconds": submission.duration_used,
        "duration_used_minutes": duration_used_minutes
    }

    # Update instead of insert
    db_result = supabase.table("test_results") \
        .update(update_data) \
        .eq("candidate_id", submission.candidate_id) \
        .execute()

    if not db_result.data:
        raise HTTPException(status_code=500, detail="Failed to update test results")

    return {
        "score": result.get("score", 0),
        "max_score": result.get("max_score", len(submission.questions) * 10),
        "percentage": result.get("percentage", 0.0),
        "status": "Completed",
        "raw_feedback": result.get("raw_feedback", ""),
        "result_id": db_result.data[0].get("id"),
        "duration_used": duration_used_minutes
    }
