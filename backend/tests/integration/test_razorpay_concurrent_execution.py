"""Integration test for x20 concurrent execution with real Razorpay test-mode.

This test requires:
- JANUS_POSTGRES_TEST_URL environment variable set to a real PostgreSQL database
- RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET set to valid test-mode credentials
- Real Razorpay test mode will be called (not mocked)

Run with: pytest backend/tests/integration/test_razorpay_concurrent_execution.py -v
"""
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db.models import Base, CheckoutProposal, Mandate
from app.domain.errors import AuthorizationDenied
from app.integrations.razorpay_adapter import RazorpayAdapter
from app.repositories.catalog import seed_catalog
from app.services.execution_service import ExecutionService
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256


POSTGRES_URL = os.getenv("JANUS_POSTGRES_TEST_URL")
REQUIRE_REAL_RAZORPAY = os.getenv("REQUIRE_REAL_RAZORPAY", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL or not REQUIRE_REAL_RAZORPAY,
    reason="Set JANUS_POSTGRES_TEST_URL and REQUIRE_REAL_RAZORPAY=true for real Razorpay test-mode execution"
)


@pytest.fixture
def pg_sessions():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def real_razorpay_adapter():
    """Provide real Razorpay adapter for test-mode execution."""
    settings = get_settings()
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        pytest.skip("Razorpay credentials not configured")
    
    if settings.razorpay_mode != "test":
        pytest.skip("Only test mode is supported for integration tests")
    
    return RazorpayAdapter(settings)


def seed_execution_x20(factory):
    """Seed one proposal that 20 callers will race to execute."""
    with factory() as db:
        seed_catalog(db)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        values = {
            "id": "mnd_x20_real",
            "instruction_text": "Buy headphones under INR 20,000",
            "hard_constraints": {
                "max_amount_paise": 2_000_000,
                "allowed_currencies": ["INR"],
                "allowed_merchants": ["merchant_demo"],
                "allowed_categories": ["headphones"],
                "allowed_conditions": ["new"],
                "max_quantity": 1,
                "max_executions": 1
            },
            "semantic_constraints": [],
            "expires_at": now + timedelta(hours=1),
            "version": 1,
            "max_executions": 1
        }
        signer = SignatureService()
        canonical = canonical_json_bytes(canonical_mandate_payload(values))
        mandate = Mandate(
            **values,
            signed_version=1,
            status="ACTIVE",
            execution_count=0,
            canonical_payload=canonical.decode(),
            payload_hash=payload_sha256(canonical),
            signature=signer.sign(canonical),
            public_key=signer.public_key_pem
        )
        db.add(mandate)
        
        db.add(CheckoutProposal(
            id="prp_x20_real",
            mandate_id=mandate.id,
            mandate_version=1,
            product_id="prod_a",
            quantity=1,
            agent_request_id="x20-real-concurrent-test",
            expected_amount_paise=1849900,
            currency="INR",
            status="ALLOWED",
            decision={}
        ))
        db.commit()


def test_x20_concurrent_real_razorpay_execution(pg_sessions, real_razorpay_adapter) -> None:
    """Test that 20 concurrent execution attempts with real Razorpay test-mode result in exactly one order.
    
    This is a LIVE integration test that:
    - Uses real PostgreSQL database with row locking
    - Calls real Razorpay test-mode API
    - Tests concurrent execution safety
    - Verifies idempotency under concurrency
    
    Expected behavior:
    - Exactly 1 Razorpay order created in test mode
    - 19 duplicate requests blocked
    - Database row locking prevents race conditions
    """
    seed_execution_x20(pg_sessions)
    barrier = threading.Barrier(20)
    outcomes = []
    razorpay_order_ids = []
    lock = threading.Lock()

    def run(proposal_id):
        barrier.wait()  # All threads start at the same time
        try:
            with pg_sessions() as db:
                result = ExecutionService(db, real_razorpay_adapter).execute(proposal_id)
                with lock:
                    outcomes.append("replay" if result.get("idempotent_replay") else "executed")
                    order_id = result.get("razorpay_order_id") or result.get("id")
                    if order_id:
                        razorpay_order_ids.append(order_id)
        except AuthorizationDenied:
            with lock:
                outcomes.append("blocked")
        except Exception as e:
            with lock:
                outcomes.append(f"error: {type(e).__name__}: {str(e)}")

    # Launch 20 concurrent threads
    threads = [threading.Thread(target=run, args=("prp_x20_real",)) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)  # Give more time for 20 threads with real API calls

    # Verify results
    executed_count = sum(1 for o in outcomes if o == "executed")
    blocked_count = sum(1 for o in outcomes if o == "blocked")
    replay_count = sum(1 for o in outcomes if o == "replay")
    error_count = sum(1 for o in outcomes if o.startswith("error"))
    
    print(f"\n=== x20 REAL RAZORPAY TEST RESULTS ===")
    print(f"Executed: {executed_count}")
    print(f"Blocked: {blocked_count}")
    print(f"Errors: {error_count}")
    print(f"Razorpay Order IDs created: {len(set(razorpay_order_ids))}")
    if razorpay_order_ids:
        print(f"Order ID: {razorpay_order_ids[0]}")
    for i, outcome in enumerate(outcomes):
        if outcome.startswith("error"):
            print(f"  Thread {i}: {outcome}")
    print("=" * 50)
    
    # Exactly one should execute, 19 should be blocked
    assert executed_count == 1, f"Expected 1 execution, got {executed_count}"
    assert blocked_count + replay_count == 19, "Expected 19 safe duplicate outcomes"
    assert error_count == 0, f"Expected 0 errors, got {error_count}: {outcomes}"
    
    # Only one unique Razorpay order should be created
    unique_order_ids = set(razorpay_order_ids)
    assert len(unique_order_ids) == 1, f"Expected 1 unique Razorpay order, got {len(unique_order_ids)}"
    
    # Verify the order was created in test mode
    order_id = razorpay_order_ids[0]
    assert order_id, "Razorpay order ID should be present"
    print(f"✓ Successfully created single Razorpay test-mode order: {order_id}")


def test_sequential_x20_with_real_razorpay(pg_sessions, real_razorpay_adapter) -> None:
    """Test 20 sequential requests to verify idempotency without concurrency.
    
    This test verifies that the idempotency mechanism works correctly even without
    the complexity of concurrent execution.
    """
    seed_execution_x20(pg_sessions)
    outcomes = []
    razorpay_order_ids = []

    for _ in range(20):
        try:
            with pg_sessions() as db:
                result = ExecutionService(db, real_razorpay_adapter).execute("prp_x20_real")
                outcomes.append("replay" if result.get("idempotent_replay") else "executed")
                order_id = result.get("razorpay_order_id") or result.get("id")
                if order_id:
                    razorpay_order_ids.append(order_id)
        except AuthorizationDenied:
            outcomes.append("blocked")
        except Exception as e:
            outcomes.append(f"error: {type(e).__name__}")

    executed_count = sum(1 for o in outcomes if o == "executed")
    blocked_count = sum(1 for o in outcomes if o == "blocked")
    replay_count = sum(1 for o in outcomes if o == "replay")
    
    print(f"\n=== SEQUENTIAL x20 TEST RESULTS ===")
    print(f"Executed: {executed_count}")
    print(f"Blocked: {blocked_count}")
    print(f"Unique Razorpay orders: {len(set(razorpay_order_ids))}")
    print("=" * 40)
    
    assert executed_count == 1, f"Expected 1 execution, got {executed_count}"
    assert blocked_count + replay_count == 19, "Expected 19 safe duplicate outcomes"
    assert len(set(razorpay_order_ids)) == 1, f"Expected 1 unique order, got {len(set(razorpay_order_ids))}"
