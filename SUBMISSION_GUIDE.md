# Email Triage OpenEnv - Submission Checklist & Guide

## Pre-Submission Validation Checklist

Before submitting to Hugging Face Spaces, verify ALL of the following:

### Code & Structure
- [ ] All files are present:
  - [ ] `email_triage_env/` directory with `.py` files
  - [ ] `openenv.yaml` (manifest file)
  - [ ] `inference.py` (baseline script)
  - [ ] `Dockerfile` (containerization)
  - [ ] `requirements.txt` (dependencies)
  - [ ] `README.md` (documentation)

### Local Testing
- [ ] Run `python test_setup.py` - environment imports correctly
- [ ] Run `python test_local.py` - all three tasks execute
  - [ ] Easy task: runs without errors
  - [ ] Medium task: runs without errors
  - [ ] Hard task: runs without errors
- [ ] Graders return scores between 0.0 and 1.0

### API Server Testing
- [ ] Start the API locally:
  ```bash
  python -m uvicorn email_triage_env.app:app --host 0.0.0.0 --port 8000
  ```
- [ ] Test endpoints:
  ```bash
  curl http://localhost:8000/health
  curl -X POST http://localhost:8000/reset?task=easy&session_id=test1
  curl -X POST http://localhost:8000/step -H "Content-Type: application/json" \
    -d '{"email_id": "...", "category": "urgent", "confidence": 0.8}' \
    -G --data-urlencode "session_id=test1"
  curl http://localhost:8000/state?session_id=test1
  curl http://localhost:8000/grade?session_id=test1
  ```

### Docker Validation
- [ ] Build the Docker image:
  ```bash
  docker build -t email-triage:latest .
  ```
- [ ] Run the Docker container:
  ```bash
  docker run -p 8000:8000 \
    -e API_BASE_URL=https://router.huggingface.co/v1 \
    -e MODEL_NAME=gpt-4 \
    -e HF_TOKEN=your_token \
    -e ENV_BASE_URL=http://localhost:8000 \
    email-triage:latest
  ```
- [ ] Verify the container starts (check logs)
- [ ] Verify the container responds to `/health` and `/ping` endpoints

### OpenEnv Spec Compliance
- [ ] `openenv.yaml` is valid YAML
- [ ] Environment implements `reset()` endpoint
- [ ] Environment implements `step()` endpoint  
- [ ] Environment implements `state()` endpoint (GET endpoint, not POST)
- [ ] All endpoints accept required parameters
- [ ] Response formats match OpenEnv spec

### Inference Script
- [ ] Reads environment variables: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- [ ] Uses OpenAI client properly
- [ ] Runs all three tasks (easy, medium, hard)
- [ ] Completes in < 20 minutes
- [ ] Produces numeric scores for all tasks
- [ ] Handles errors gracefully

### Documentation
- [ ] README.md includes:
  - [ ] Overview and task description
  - [ ] Real-world utility explanation
  - [ ] Observation and action space specs
  - [ ] Reward function explanation
  - [ ] All three tasks with difficulty levels
  - [ ] Setup & installation instructions
  - [ ] API endpoint documentation
  - [ ] Expected baseline results
  - [ ] Files listing
- [ ] README is clear and professional

---

## Hugging Face Spaces Deployment

### Step 1: Create a Space

1. Go to https://huggingface.co/new-space
2. Configure:
   - **Owner**: Your team or personal account
   - **Space name**: `email-triage-env` (or similar; must be unique)
   - **License**: MIT (or choose one)
   - **Space SDK**: Docker
3. Click "Create space"

### Step 2: Configure Environment Variables

In the Space Settings (gear icon) → "Repository secrets":

Add these environment variables:
- **API_BASE_URL**: Your LLM API endpoint (e.g., `https://router.huggingface.co/v1`)
- **MODEL_NAME**: The model identifier (e.g., `gpt-4` or `meta-llama/Llama-2-70b-chat-hf`)
- **HF_TOKEN**: Your Hugging Face API token (from https://huggingface.co/settings/tokens)
- **ENV_BASE_URL**: Keep as `http://localhost:8000` inside the container

### Step 3: Push Your Code

Clone the Space repository locally:
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/email-triage-env
cd email-triage-env
```

Copy your files into the cloned directory:
```bash
cp -r ../email-triage-env/* .
```

Commit and push:
```bash
git add .
git commit -m "Initial email triage environment submission"
git push
```

The Space will auto-build and deploy from the Dockerfile.

### Step 4: Verify Deployment

Once the Space shows "Running" (green status):

1. Click the "Embed" button to get the Space URL
2. Test the health endpoint:
   ```bash
   curl https://YOUR_USERNAME-email-triage-env.hf.space/health
   # Should return: {"status": "ok"}
   ```
3. Test reset:
   ```bash
   curl -X POST https://YOUR_USERNAME-email-triage-env.hf.space/reset?task=easy&session_id=test
   # Should return initialization data
   ```

### Step 5: Run Pre-Submission Validation

Use Scaler's pre-submission validation script:

```bash
chmod +x scripts/validate-submission.sh  # if provided
./validate-submission.sh https://YOUR_USERNAME-email-triage-env.hf.space
```

Or manually check:
- [ ] Ping returns 200 and responds to reset()
- [ ] Dockerfile builds successfully
- [ ] `openenv validate openenv.yaml` passes
- [ ] Baseline script runs: `python inference.py`
- [ ] All three tasks produce scores 0.0-1.0

---

## Common Issues & Fixes

### Issue: Docker build fails with "module not found"
**Fix**: Ensure `email_triage_env/__init__.py` exists and imports are correct.

### Issue: `/step` returns error "Session not found"
**Fix**: Make sure you call `/reset` first with the same `session_id`.

### Issue: Agent inference is too slow (>20 min)
**Fix**:
- Reduce `MAX_TURNS` in `inference.py`
- Use a faster model (not gpt-4)
- Implement context truncation

### Issue: Graders always return the same score
**Fix**: Ensure graders check `state.classifications` and compare against `state.ground_truth`.

### Issue: HF Space deployment fails
**Fix**:
- Check Space logs (Logs tab)
- Verify Dockerfile has correct working directory
- Ensure all COPY commands reference existing files
- Check that `requirements.txt` has all dependencies

---

## Final Submission

1. Ensure all checklist items above pass ✓
2. Get your HF Space URL: `https://YOUR_USERNAME-email-triage-env.hf.space`
3. Submit via Scaler portal:
   - Team lead submits (only one submission per team)
   - Include Space URL
   - Include GitHub repository link (if using GitHub)
4. Deadline: **April 8th, 11:59 PM**

---

## Scoring Breakdown

| Criterion | Weight | Target |
|-----------|--------|--------|
| Real-world utility | 30% | Email triage is real-world use case |
| Task & grader quality | 25% | 3 tasks, deterministic grading, 0.0-1.0 scores |
| Environment design | 20% | Clean state, good reward shaping |
| Code quality & spec | 15% | OpenEnv compliant, Docker works, README complete |
| Creativity & novelty | 10% | Interesting reward design, phishing patterns |

**Target Total**: 85-95%

---

Good luck with your submission! 🚀
