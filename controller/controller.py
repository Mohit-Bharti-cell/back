from fastapi import APIRouter, HTTPException
import httpx
from datetime import datetime, timezone
from db.supabase import supabase
from schemas.test_schemas import CandidateLoginRequest, CandidateLoginResponse
import os

router = APIRouter()

# Base URL for the external API
EXTERNAL_API_BASE_URL = "http://localhost:5000"

@router.post("/debug-external-api")
async def debug_external_api(request: CandidateLoginRequest):
    """
    Debug endpoint to see the raw response from external API
    """
    try:
        # Debug: Print the incoming request
        print(f"🔍 Incoming request: {request}")
        print(f"🔍 Request email: {request.email}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Debug: Print the payload being sent
            payload = {"email": request.email}
            print(f"🔍 Sending payload to external API: {payload}")
            response = await client.post(
                f"{EXTERNAL_API_BASE_URL}/api/jd/get-filteredCandidateByEmail",
                json=payload
            )
        print(f"🔍 External API status code: {response.status_code}")
        print(f"🔍 External API response text: {response.text}")
        response_data = response.json() if response.status_code == 200 else None
 
        # If successful, also show the mapped data
        mapped_data = None
        if response_data and "filteredResumes" in response_data and response_data["filteredResumes"]:
            candidate_info = response_data["filteredResumes"][0]
            mapped_data = {
                "email": candidate_info.get("email"),
                "candidate_id": candidate_info.get("_id"),
                "name": candidate_info.get("name", "Unknown")
            }
 
        return {
            "status_code": response.status_code,
            "raw_response": response_data,
            "mapped_candidate_data": mapped_data,
            "headers": dict(response.headers),
            "request_payload": payload
        }
 
    except Exception as e:
        print(f"❌ Error in debug endpoint: {str(e)}")
        return {
            "error": str(e),
            "external_api_url": f"{EXTERNAL_API_BASE_URL}/api/jd/get-filteredCandidateByEmail"
        }
@router.post("/login", response_model=CandidateLoginResponse)
async def candidate_login(request: CandidateLoginRequest):
    """
    Login candidate by email and store their details in test_results table
    """
    try:
        # Debug: Print the incoming request
        print(f"🔍 Login request received: {request}")
        print(f"🔍 Request email: {request.email}")
        # Validate email is not empty
        if not request.email or request.email.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="Email cannot be empty"
            )
 
        # Make API call to get candidate details - POST request with JSON body
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"email": request.email}
            print(f"🔍 Sending to external API: {payload}")
            response = await client.post(
                f"{EXTERNAL_API_BASE_URL}/api/jd/get-filteredCandidateByEmail",
                json=payload
            )
 
        print(f"🔍 External API Response Status: {response.status_code}")
        print(f"🔍 External API Response Text: {response.text}")
 
        if response.status_code != 200:
            print(f"❌ External API Error - Status: {response.status_code}, Response: {response.text}")
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"Failed to fetch candidate details. API returned: {response.status_code}"
            )
 
        candidate_data = response.json()
        print(f"🔍 Raw API Response: {candidate_data}")
 
        # Check if the response has the expected structure
        if "filteredResumes" not in candidate_data:
            print(f"❌ Missing 'filteredResumes' in response: {candidate_data}")
            raise HTTPException(
                status_code=422,
                detail="Invalid API response format: missing 'filteredResumes' field"
            )
 
        # Check if any candidates found
        if not candidate_data["filteredResumes"] or len(candidate_data["filteredResumes"]) == 0:
            print(f"❌ No candidates found for email: {request.email}")
            raise HTTPException(
                status_code=404,
                detail="No candidate found with this email"
            )
 
        # Get the first candidate from the filtered results
        candidate_info = candidate_data["filteredResumes"][0]
        print(f"🔍 Candidate info from API: {candidate_info}")
 
        # Map the API fields to our expected format
        mapped_candidate_data = {
            "email": candidate_info.get("email"),
            "candidate_id": candidate_info.get("_id"),  # Map _id to candidate_id
            "name": candidate_info.get("name", "Unknown")  # Default to "Unknown" if name is missing
        }
 
        print(f"🔍 Mapped candidate data: {mapped_candidate_data}")
 
        # Validate that we have the essential fields
        if not mapped_candidate_data["email"] or not mapped_candidate_data["candidate_id"]:
            print(f"❌ Missing essential fields in candidate info: {candidate_info}")
            raise HTTPException(
                status_code=422,
                detail=f"Missing essential fields. Got: {candidate_info}"
            )
 
        # Check if candidate already has an entry in test_results
        existing_entry = supabase.table("test_results").select("*").eq(
            "candidate_id", mapped_candidate_data["candidate_id"]
        ).execute()
 
        # If no existing entry, create a new one with candidate details
        if not existing_entry.data:
            candidate_entry = {
                "candidate_id": mapped_candidate_data["candidate_id"],
                "email": mapped_candidate_data["email"],
                "name": mapped_candidate_data["name"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "Logged In"  # Initial status
            }
 
            insert_result = supabase.table("test_results").insert(candidate_entry).execute()
 
            if not insert_result.data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store candidate details"
                )
 
            print(f"✅ New candidate logged in and stored: {mapped_candidate_data['name']} ({mapped_candidate_data['email']})")
        else:
            print(f"✅ Existing candidate logged in: {mapped_candidate_data['name']} ({mapped_candidate_data['email']})")
 
        return CandidateLoginResponse(
            email=mapped_candidate_data["email"],
            candidate_id=mapped_candidate_data["candidate_id"],
            name=mapped_candidate_data["name"],
            message="Login successful"
        )
 
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except httpx.RequestError as e:
        print(f"❌ API Connection Error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to external API: {str(e)}"
        )
    except httpx.TimeoutException:
        print("❌ API Timeout Error")
        raise HTTPException(
            status_code=504,
            detail="External API request timed out"
        )
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
@router.get("/details/{candidate_id}")
async def get_candidate_details(candidate_id: str):
    """
    Get candidate details by candidate_id
    """
    try:
        result = supabase.table("test_results").select("*").eq(
            "candidate_id", candidate_id
        ).execute()
 
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found"
            )
 
        return result.data[0]
 
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting candidate details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch candidate details: {str(e)}"
        )
@router.get("/results/{candidate_id}")
async def get_candidate_test_results(candidate_id: str):
    """
    Get test results for a candidate
    """
    try:
        result = supabase.table("test_results").select("*").eq(
            "candidate_id", candidate_id
        ).execute()
 
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="No test results found for this candidate"
            )
 
        return result.data[0]
 
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting test results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch test results: {str(e)}"
        )