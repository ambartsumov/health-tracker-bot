#!/usr/bin/env python3
"""
Quick test to verify SQLAlchemy session management fix.
Tests that User objects can be accessed after session closes.
"""

import sys
from database.manager import db_manager
from database.models import GoalType
from datetime import date

def test_session_fix():
    """Test that User objects work after session closes."""
    
    print("Testing SQLAlchemy session management fix...")
    print("-" * 50)
    
    # Initialize database
    db_manager.initialize()
    print("✓ Database initialized")
    
    # Test 1: Create user and access attributes
    print("\n[Test 1] Creating user and accessing attributes...")
    try:
        user = db_manager.create_user(
            telegram_id="999999",
            name="Test User",
            date_of_birth=date(1990, 1, 1),
            weight_kg=75.0,
            height_cm=180.0,
            goal=GoalType.WEIGHT_LOSS
        )
        
        # Try to access attributes (would fail before fix)
        print(f"  User ID: {user.id}")
        print(f"  Name: {user.name}")
        print(f"  Telegram ID: {user.telegram_id}")
        print(f"  Weight: {user.weight_kg} kg")
        print(f"  Goal: {user.goal}")
        print("✓ User created and attributes accessible")
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False
    
    # Test 2: Get user and access attributes
    print("\n[Test 2] Getting user and accessing attributes...")
    try:
        retrieved_user = db_manager.get_user_by_telegram_id("999999")
        
        if not retrieved_user:
            print("✗ User not found")
            return False
        
        # Try to access attributes (would fail before fix)
        print(f"  Retrieved User ID: {retrieved_user.id}")
        print(f"  Retrieved Name: {retrieved_user.name}")
        print(f"  Retrieved Telegram ID: {retrieved_user.telegram_id}")
        print(f"  Retrieved Weight: {retrieved_user.weight_kg} kg")
        print("✓ User retrieved and attributes accessible")
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False
    
    # Test 3: Update user and access attributes
    print("\n[Test 3] Updating user and accessing attributes...")
    try:
        updated_user = db_manager.update_user(
            user.id,
            weight_kg=73.0,
            height_cm=182.0
        )
        
        if not updated_user:
            print("✗ User not found")
            return False
        
        print(f"  Updated Weight: {updated_user.weight_kg} kg")
        print(f"  Updated Height: {updated_user.height_cm} cm")
        print("✓ User updated and attributes accessible")
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed! SQLAlchemy session fix works.")
    return True

if __name__ == "__main__":
    try:
        success = test_session_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
