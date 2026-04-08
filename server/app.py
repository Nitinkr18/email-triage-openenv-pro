"""Email Triage OpenEnv REST API exposing reset/step/state and grading."""

from fastapi import FastAPI, HTTPException
from typing import Dict

from email_triage_env.env import EmailTriageEnv
from email_triage_env.models import TriageAction
from email_triage_env.graders import EmailTriageGrader

# Global environment instances (keyed by session_id)
_sessions: Dict[str, EmailTriageEnv] = {}

app = FastAPI(
    title="Email Triage OpenEnv",
    description="Real-world email classification environment",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    """Ping endpoint for deployment validation."""
    return {"status": "pong"}


@app.post("/reset")
async def reset_env(task: str = "easy", session_id: str = "default", seed: int = None):
    """
    Reset environment for a new episode.
    
    Args:
        task: "easy", "medium", or "hard"
        session_id: Unique session identifier
        seed: Random seed for reproducibility
        
    Returns:
        Initial observation
    """
    try:
        # Create new environment instance for this session
        env = EmailTriageEnv()
        observation = env.reset(task=task, seed=seed)
        _sessions[session_id] = env
        
        return {
            "status": "reset",
            "task": task,
            "session_id": session_id,
            "observation": observation.model_dump()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step")
async def step_env(action: TriageAction, session_id: str = "default"):
    """
    Execute one step in the environment.
    
    Args:
        action: Email classification action
        session_id: Session identifier
        
    Returns:
        (observation, reward, done, info)
    """
    try:
        if session_id not in _sessions:
            raise HTTPException(
                status_code=400, 
                detail=f"Session '{session_id}' not found. Call /reset first."
            )
        
        env = _sessions[session_id]
        observation, reward, done, info = env.step(action)
        
        return {
            "status": "step",
            "observation": observation.model_dump(),
            "reward": reward.model_dump(),
            "done": done,
            "info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/state")
async def get_state(session_id: str = "default"):
    """
    Get current internal state (for evaluation/debugging).
    
    Args:
        session_id: Session identifier
        
    Returns:
        Current state object
    """
    try:
        if session_id not in _sessions:
            raise HTTPException(
                status_code=400,
                detail=f"Session '{session_id}' not found."
            )
        
        env = _sessions[session_id]
        state = env.state()
        
        return {
            "status": "state",
            "session_id": session_id,
            "episode_id": state.episode_id,
            "task_type": state.task_type,
            "current_email_idx": state.current_email_idx,
            "total_emails": len(state.emails_in_inbox),
            "correctly_classified": state.correctly_classified,
            "total_processed": state.total_processed,
            "cumulative_reward": state.cumulative_reward,
            "episode_done": state.episode_done
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/grade")
async def grade_session(session_id: str = "default"):
    """Return deterministic 0.0-1.0 score for current task state."""
    try:
        if session_id not in _sessions:
            raise HTTPException(
                status_code=400,
                detail=f"Session '{session_id}' not found."
            )

        env = _sessions[session_id]
        state = env.state()
        score = EmailTriageGrader.grade_task(state)

        return {
            "status": "graded",
            "session_id": session_id,
            "task": state.task_type,
            "score": score,
            "range": [0.0, 1.0],
            "emails_processed": state.total_processed,
            "episode_done": state.episode_done,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Welcome message."""
    return {
        "message": "Email Triage OpenEnv",
        "endpoints": {
            "GET /health": "Health check",
            "GET /ping": "Deployment ping",
            "POST /reset": "Initialize new episode",
            "POST /step": "Execute action",
            "GET /state": "Get current state",
            "GET /grade": "Get deterministic task score"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
