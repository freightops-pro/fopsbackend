"""Test script for AI agents - Annie, Atlas, and Alex."""
import asyncio
import sys
from datetime import datetime
from sqlalchemy import select
from app.core.db import AsyncSessionFactory
from app.models.ai_task import AITask
from app.services.annie_ai import AnnieAI
from app.services.atlas_ai import AtlasAI
from app.services.alex_ai import AlexAI
import uuid

# Fix for Windows ProactorEventLoop incompatibility with psycopg
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def test_annie():
    """Test Annie AI - Operations Agent."""
    print("\n" + "="*60)
    print("TESTING ANNIE AI - Operations Agent")
    print("="*60)

    async with AsyncSessionFactory() as db:
        # Create a test task for Annie
        task = AITask(
            id=str(uuid.uuid4()),
            company_id="test_company",
            user_id="test_user",
            agent_type="annie",
            task_type="load_creation",
            task_description="Create a load for customer Walmart, rate $850, from Baytown TX to Seabrook TX for general freight",
            status="queued",
            created_at=datetime.utcnow()
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        print(f"\n[+] Created task: {task.id}")
        print(f"    Description: {task.task_description}")

        # Execute the task
        annie = AnnieAI(db)
        await annie.register_tools()

        print(f"\n[+] Annie registered {len(annie.tools)} tools:")
        for tool in annie.tools:
            print(f"    - {tool.name}")

        print("\n[*] Executing task...")
        success, error = await annie.execute_task(task, "test_company", "test_user")

        # Refresh task to see results
        await db.refresh(task)

        if success:
            print(f"\n[OK] Task COMPLETED successfully!")
            print(f"  Status: {task.status}")
            if task.result:
                print(f"  Result: {task.result.get('summary', 'No summary')}")
            print(f"  Tokens used: {task.total_tokens_used}")
            print(f"  Cost: ${task.total_cost_usd}")
            if task.executed_steps:
                print(f"  Steps executed: {len(task.executed_steps)}")
        else:
            print(f"\n[FAIL] Task FAILED")
            print(f"  Error: {error}")
            print(f"  Status: {task.status}")

        return success


async def test_atlas():
    """Test Atlas AI - Monitoring Agent."""
    print("\n" + "="*60)
    print("TESTING ATLAS AI - Monitoring Agent")
    print("="*60)

    async with AsyncSessionFactory() as db:
        # Create a test task for Atlas
        task = AITask(
            id=str(uuid.uuid4()),
            company_id="test_company",
            user_id="test_user",
            agent_type="atlas",
            task_type="monitoring",
            task_description="Calculate the on-time delivery rate for the last 7 days",
            status="queued",
            created_at=datetime.utcnow()
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        print(f"\n[+] Created task: {task.id}")
        print(f"  Description: {task.task_description}")

        # Execute the task
        atlas = AtlasAI(db)
        await atlas.register_tools()

        print(f"\n[+] Atlas registered {len(atlas.tools)} tools:")
        for tool in atlas.tools:
            print(f"  - {tool.name}")

        print("\n[*] Executing task...")
        success, error = await atlas.execute_task(task, "test_company", "test_user")

        # Refresh task to see results
        await db.refresh(task)

        if success:
            print(f"\n[OK] Task COMPLETED successfully!")
            print(f"  Status: {task.status}")
            if task.result:
                print(f"  Result: {task.result.get('summary', 'No summary')}")
            print(f"  Tokens used: {task.total_tokens_used}")
            print(f"  Cost: ${task.total_cost_usd}")
            if task.executed_steps:
                print(f"  Steps executed: {len(task.executed_steps)}")
        else:
            print(f"\n[FAIL] Task FAILED")
            print(f"  Error: {error}")
            print(f"  Status: {task.status}")

        return success


async def test_alex():
    """Test Alex AI - Sales & Analytics Agent."""
    print("\n" + "="*60)
    print("TESTING ALEX AI - Sales & Analytics Agent")
    print("="*60)

    async with AsyncSessionFactory() as db:
        # Create a test task for Alex
        task = AITask(
            id=str(uuid.uuid4()),
            company_id="test_company",
            user_id="test_user",
            agent_type="alex",
            task_type="analytics",
            task_description="Generate a comprehensive executive summary for this month",
            status="queued",
            created_at=datetime.utcnow()
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        print(f"\n[+] Created task: {task.id}")
        print(f"  Description: {task.task_description}")

        # Execute the task
        alex = AlexAI(db)
        await alex.register_tools()

        print(f"\n[+] Alex registered {len(alex.tools)} tools:")
        for tool in alex.tools:
            print(f"  - {tool.name}")

        print("\n[*] Executing task...")
        success, error = await alex.execute_task(task, "test_company", "test_user")

        # Refresh task to see results
        await db.refresh(task)

        if success:
            print(f"\n[OK] Task COMPLETED successfully!")
            print(f"  Status: {task.status}")
            if task.result:
                print(f"  Result: {task.result.get('summary', 'No summary')}")
            print(f"  Tokens used: {task.total_tokens_used}")
            print(f"  Cost: ${task.total_cost_usd}")
            if task.executed_steps:
                print(f"  Steps executed: {len(task.executed_steps)}")
        else:
            print(f"\n[FAIL] Task FAILED")
            print(f"  Error: {error}")
            print(f"  Status: {task.status}")

        return success


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("FREIGHTOPS AI AGENT TEST SUITE")
    print("="*60)
    print("\nTesting all three autonomous AI agents:")
    print("  1. Annie - Operations (dispatch, loads, drivers)")
    print("  2. Atlas - Monitoring (exceptions, alerts, performance)")
    print("  3. Alex - Sales & Analytics (forecasting, KPIs, insights)")

    results = {
        "annie": await test_annie(),
        "atlas": await test_atlas(),
        "alex": await test_alex(),
    }

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"\nAnnie (Operations):  {'[OK] PASS' if results['annie'] else '[FAIL] FAIL'}")
    print(f"Atlas (Monitoring):  {'[OK] PASS' if results['atlas'] else '[FAIL] FAIL'}")
    print(f"Alex (Analytics):    {'[OK] PASS' if results['alex'] else '[FAIL] FAIL'}")

    all_passed = all(results.values())
    print(f"\n{'='*60}")
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED! AI agents are operational.")
    else:
        print("[WARNING]  Some tests failed. Check errors above.")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
