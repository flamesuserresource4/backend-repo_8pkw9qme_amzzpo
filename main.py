import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

from database import create_document, get_documents, db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Answer(BaseModel):
    question_id: int
    choice: str  # "A" or "B"

class AssessmentRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    answers: List[Answer]

# RIASEC questions (simple 12 Q demo, 2 per type)
QUESTIONS = [
    {"id": 1, "text": "I enjoy building or fixing things with my hands.", "A": "Agree", "B": "Disagree", "type": "R"},
    {"id": 2, "text": "I like working with tools or machines.", "A": "Agree", "B": "Disagree", "type": "R"},
    {"id": 3, "text": "I enjoy solving math or science problems.", "A": "Agree", "B": "Disagree", "type": "I"},
    {"id": 4, "text": "I like analyzing data and figuring out how things work.", "A": "Agree", "B": "Disagree", "type": "I"},
    {"id": 5, "text": "I like to create art, music, or write.", "A": "Agree", "B": "Disagree", "type": "A"},
    {"id": 6, "text": "I prefer unstructured tasks where I can be original.", "A": "Agree", "B": "Disagree", "type": "A"},
    {"id": 7, "text": "I enjoy helping people and improving their lives.", "A": "Agree", "B": "Disagree", "type": "S"},
    {"id": 8, "text": "I like teaching, counseling, or caring roles.", "A": "Agree", "B": "Disagree", "type": "S"},
    {"id": 9, "text": "I like leading projects and persuading others.", "A": "Agree", "B": "Disagree", "type": "E"},
    {"id": 10, "text": "I enjoy business, sales, or entrepreneurship.", "A": "Agree", "B": "Disagree", "type": "E"},
    {"id": 11, "text": "I prefer organizing information and keeping things orderly.", "A": "Agree", "B": "Disagree", "type": "C"},
    {"id": 12, "text": "I enjoy working with data, records, and details.", "A": "Agree", "B": "Disagree", "type": "C"},
]

CAREER_MAP: Dict[str, List[str]] = {
    "R": ["Mechanical Engineer", "Electrician", "Carpenter", "Automotive Technician"],
    "I": ["Data Scientist", "Research Analyst", "Software Developer", "Biologist"],
    "A": ["Graphic Designer", "Writer", "Musician", "UX Designer"],
    "S": ["Teacher", "Nurse", "Social Worker", "Therapist"],
    "E": ["Marketing Manager", "Sales Representative", "Entrepreneur", "Product Manager"],
    "C": ["Accountant", "Operations Coordinator", "Data Entry Specialist", "Admin Assistant"],
}

SUMMARY_BLURBS: Dict[str, str] = {
    "R": "Hands-on, practical, and mechanical. You enjoy building, fixing, and working with tools.",
    "I": "Analytical and curious. You enjoy research, problem-solving, and understanding how things work.",
    "A": "Creative and expressive. You value originality and enjoy artistic or design-focused tasks.",
    "S": "Supportive and people-oriented. You find meaning in helping and teaching others.",
    "E": "Persuasive and leadership-driven. You thrive in business, sales, and leading initiatives.",
    "C": "Organized and detail-focused. You keep systems running smoothly and accurately.",
}

@app.get("/")
def read_root():
    return {"message": "Career Pathfinder API is running"}

@app.get("/api/questions")
def get_questions():
    # Minimal payload without revealing types to the client (but we'll include id/text/options)
    return [{"id": q["id"], "text": q["text"], "options": {"A": q["A"], "B": q["B"]}} for q in QUESTIONS]

@app.post("/api/assess")
def assess(req: AssessmentRequest):
    # Tally RIASEC scores based on answers where "A" means agree -> +1 for that question's type
    scores: Dict[str, int] = {k: 0 for k in ["R", "I", "A", "S", "E", "C"]}
    q_index = {q["id"]: q for q in QUESTIONS}

    for ans in req.answers:
        q = q_index.get(ans.question_id)
        if not q:
            raise HTTPException(status_code=400, detail=f"Invalid question id: {ans.question_id}")
        if ans.choice not in ("A", "B"):
            raise HTTPException(status_code=400, detail="Choice must be 'A' or 'B'")
        if ans.choice == "A":
            scores[q["type"]] += 1

    # Determine top types
    sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    max_score = sorted_types[0][1]
    top_types = [t for t, s in sorted_types if s == max_score and s > 0][:2] or [sorted_types[0][0]]

    # Aggregate careers and summary
    suggested = []
    for t in top_types:
        for c in CAREER_MAP.get(t, [])[:3]:
            if c not in suggested:
                suggested.append(c)

    summary_parts = [SUMMARY_BLURBS[t] for t in top_types]
    summary = " ".join(summary_parts)

    # Persist result
    try:
        doc_id = create_document(
            "assessmentresult",
            {
                "name": req.name,
                "email": req.email,
                "scores": scores,
                "top_types": top_types,
                "careers": suggested,
                "summary": summary,
            },
        )
    except Exception as e:
        # If DB not available, continue without failing the assessment
        doc_id = None

    return {
        "id": doc_id,
        "scores": scores,
        "top_types": top_types,
        "careers": suggested,
        "summary": summary,
    }

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
