#!/usr/bin/env python
"""
Local test script for Email Triage Environment
Tests all core functionality without needing the API server
"""

import sys
import json

# Add the project to path
sys.path.insert(0, '/c/Users/keert/Downloads/Egli/email-triage-env')

from email_triage_env.env import EmailTriageEnv
from email_triage_env.models import TriageAction, EmailCategory
from email_triage_env.graders import EmailTriageGrader


def test_easy_task():
    """Test easy task."""
    print("\n" + "="*60)
    print("TEST: Easy Task")
    print("="*60)
    
    env = EmailTriageEnv()
    obs = env.reset(task="easy", seed=42)
    
    print(f"Initial observation:")
    print(f"  Inbox remaining: {obs.inbox_remaining}")
    print(f"  Task: {obs.task_difficulty}")
    print(f"  Current email: '{obs.current_email.subject}'")
    
    # Classify first email (should be urgent based on synthetic data)
    action = TriageAction(
        email_id=obs.current_email.email_id,
        category=EmailCategory.URGENT,
        confidence=0.9
    )
    
    obs, reward, done, info = env.step(action)
    print(f"\nAfter first classification:")
    print(f"  Reward: {reward.value}")
    print(f"  Breakdown: {reward.breakdown}")
    print(f"  Done: {done}")
    print(f"  Info: {json.dumps(info, indent=2)}")
    
    # Continue with remaining emails
    while not done:
        action = TriageAction(
            email_id=obs.current_email.email_id,
            category=EmailCategory.INFORMATIONAL,  # Default neutral Classification
            confidence=0.5
        )
        obs, reward, done, info = env.step(action)
    
    # Grade the task
    state = env.state()
    score = EmailTriageGrader.grade_easy(state)
    print(f"\nTask completed!")
    print(f"  Final score: {score}")
    
    return score


def test_medium_task():
    """Test medium task."""
    print("\n" + "="*60)
    print("TEST: Medium Task")
    print("="*60)
    
    env = EmailTriageEnv()
    obs = env.reset(task="medium", seed=42)
    
    print(f"Inbox size: {obs.inbox_remaining + 1}")
    print(f"First email: '{obs.current_email.subject[:40]}...'")
    
    # Make some smart classifications
    classifications = []
    while obs.inbox_remaining > 0:
        # Simple heuristic: check for urgency keywords
        is_urgent = "urgent" in obs.current_email.subject.lower()
        is_spam = "free" in obs.current_email.subject.lower() or \
                  "claim" in obs.current_email.subject.lower()
        
        if is_spam:
            category = EmailCategory.SPAM
        elif is_urgent:
            category = EmailCategory.URGENT
        else:
            category = EmailCategory.INFORMATIONAL
        
        action = TriageAction(
            email_id=obs.current_email.email_id,
            category=category,
            confidence=0.7
        )
        
        obs, reward, done, info = env.step(action)
        classifications.append((obs.current_email.subject[:30], category.value, reward.value))
    
    # Final classification
    action = TriageAction(
        email_id=obs.current_email.email_id,
        category=EmailCategory.INFORMATIONAL,
        confidence=0.6
    )
    obs, reward, done, info = env.step(action)
    
    # Grade
    state = env.state()
    score = EmailTriageGrader.grade_medium(state)
    
    print(f"\nTask completed!")
    print(f"  Emails processed: {len(classifications)}")
    print(f"  Final score: {score}")
    
    return score


def test_hard_task():
    """Test hard task."""
    print("\n" + "="*60)
    print("TEST: Hard Task")
    print("="*60)
    
    env = EmailTriageEnv()
    obs = env.reset(task="hard", seed=42)
    
    print(f"Inbox size: {obs.inbox_remaining + 1}")
    
    # Classify all emails with moderate confidence (hard task!)
    count = 0
    while count <= len(env.state().emails_in_inbox):
        # Very simple heuristic
        category = EmailCategory.INFORMATIONAL
        confidence = 0.5
        
        action = TriageAction(
            email_id=obs.current_email.email_id,
            category=category,
            confidence=confidence
        )
        
        obs, reward, done, info = env.step(action)
        count += 1
        
        if obs.inbox_remaining == 0:
            break
    
    # Grade
    state = env.state()
    score = EmailTriageGrader.grade_hard(state)
    
    print(f"\nTask completed!")
    print(f"  Final score: {score}")
    
    return score


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EMAIL TRIAGE OPENENV - LOCAL VALIDATION TEST")
    print("="*70)
    
    try:
        easy_score = test_easy_task()
        medium_score = test_medium_task()
        hard_score = test_hard_task()
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Easy task score: {easy_score:.2f}")
        print(f"Medium task score: {medium_score:.2f}")
        print(f"Hard task score: {hard_score:.2f}")
        print(f"Average score: {(easy_score + medium_score + hard_score) / 3:.2f}")
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
        return 0
    
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
