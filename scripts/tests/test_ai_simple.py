"""Simple AI agent test - bypasses API authentication."""
import asyncio
import sys
import os
from datetime import datetime

# Add Google AI API key from environment
os.environ['GOOGLE_AI_API_KEY'] = 'AIzaSyBJeSsvOc1UcI0UF78Qfm6bMTuI0UNc1eE'

from sqlalchemy import select
from app.core.db import AsyncSessionFactory
from app.models.ai_task import AITask
from app.models.company import Company
from app.services.alex_ai import AlexAI
import uuid

# Fix for Windows ProactorEventLoop incompatibility with psycopg
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def test_alex_simple():
    """Test Alex AI with a simple task."""
    print("\n" + "="*60)
    print("TESTING ALEX AI - Revenue Metrics")
    print("="*60)

    async with AsyncSessionFactory() as db:
        # Ensure test company exists
        company_id = "test-company"
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

        if not company:
            print(f"\n[+] Creating test company: {company_id}")
            try:
                company = Company(
                    id=company_id,
                    name="Test Company",
                    email="test@testcompany.com",
                    dotNumber="123456",
                    mcNumber="MC123456"
                )
                db.add(company)
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"    Note: Company may already exist (ignoring): {str(e)[:50]}")
        else:
            print(f"\n[+] Using existing company: {company_id}")
        # Create a simple test task
        task = AITask(
            id=str(uuid.uuid4()),
            company_id=company_id,
            user_id="test",
            agent_type="alex",
            task_type="analytics",
            task_description="Calculate revenue metrics for the last 30 days",
            status="queued",
            created_at=datetime.utcnow()
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        print(f"\n[+] Created task: {task.id}")
        print(f"    Description: {task.task_description}")

        # Execute the task
        alex = AlexAI(db)
        await alex.register_tools()

        print(f"\n[+] Alex initialized with {len(alex.tools)} tools")
        print(f"    Model: {alex.model_name}")

        print("\n[*] Executing task...")
        try:
            success, error = await alex.execute_task(task, company_id, "test")

            # Refresh task to see results
            await db.refresh(task)

            if success:
                print(f"\n[OK] Task COMPLETED!")
                print(f"     Status: {task.status}")
                print(f"     Tokens used: {task.total_tokens_used}")
                print(f"     Cost: ${task.total_cost_usd}")

                if task.result:
                    print(f"\n[RESULT]")
                    result = task.result
                    if isinstance(result, dict):
                        for key, value in result.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  {result}")

                if task.executed_steps:
                    print(f"\n[STEPS] Executed {len(task.executed_steps)} steps")
                    for i, step in enumerate(task.executed_steps[:3], 1):  # Show first 3
                        print(f"  {i}. {step.get('tool_name', 'unknown')}")

                return True
            else:
                print(f"\n[FAIL] Task FAILED")
                print(f"       Error: {error}")
                print(f"       Status: {task.status}")
                return False

        except Exception as e:
            print(f"\n[ERROR] Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Run simple test."""
    print("\n" + "="*60)
    print("FREIGHTOPS AI - SIMPLE VERIFICATION TEST")
    print("="*60)
    print("\nThis test verifies that:")
    print("  1. AI agent can initialize")
    print("  2. Google AI API connection works")
    print("  3. Task execution completes")
    print("  4. Database tracking works")

    success = await test_alex_simple()

    print("\n" + "="*60)
    if success:
        print("[SUCCESS] AI agent is fully operational!")
        print("="*60)
        return 0
    else:
        print("[FAIL] AI agent test failed - see errors above")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
