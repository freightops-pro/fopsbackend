#!/usr/bin/env python3
"""
Test login directly to see the actual error
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config.db import get_db
from app.models.userModels import Users, Companies

try:
    print("Testing database query that happens during login...")
    db = next(get_db())
    
    # Try to query users (this is what happens during login)
    print("Querying Users...")
    user = db.query(Users).first()
    print(f"SUCCESS: Users query successful: {user.email if user else 'No users found'}")
    
    # Try to query companies
    print("Querying Companies...")
    company = db.query(Companies).first()
    print(f"SUCCESS: Companies query successful: {company.name if company else 'No companies found'}")
    
    print("\nSUCCESS: All queries successful!")
    
except Exception as e:
    print("\nERROR: Error occurred")
    print(f"Type: {type(e).__name__}")
    print(f"Message: {str(e)}")
    import traceback
    traceback.print_exc()

