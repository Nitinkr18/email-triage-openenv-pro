#!/usr/bin/env python
"""
Setup script - Quick inference dry-run test
Validates that the environment can be imported and used without API
"""

import sys
sys.path.insert(0, '.')

from email_triage_env.env import EmailTriageEnv
from email_triage_env.models import TriageAction, EmailCategory
from email_triage_env.graders import EmailTriageGrader


def quick_test():
    """Run a quick sanity check."""
    print("Testing Email Triage Environment...")
    
    env = EmailTriageEnv()
    
    # Easy task
    obs = env.reset(task="easy")
    print(f"✓ Easy task initialized: {obs.inbox_remaining + 1} emails")
    
    # Make a classification
    action = TriageAction(
        email_id=obs.current_email.email_id,
        category=EmailCategory.URGENT if "URGENT" in obs.current_email.subject else EmailCategory.INFORMATIONAL,
        confidence=0.8
    )
    obs, reward, done, info = env.step(action)
    print(f"✓ Step executed, reward = {reward.value:.2f}")
    
    # Get state and grade
    state = env.state()
    score = EmailTriageGrader.grade_easy(state)
    print(f"✓ Task graded, score = {score:.2f}")
    
    print("\n✓ Environment is working correctly!")
    return True


if __name__ == "__main__":
    try:
        success = quick_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
