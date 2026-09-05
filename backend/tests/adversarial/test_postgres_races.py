import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, CheckoutProposal, Mandate
from app.domain.errors import AuthorizationDenied
from app.repositories.catalog import seed_catalog
from app.services.execution_service import ExecutionService
from app.services.revocation_service import revoke_mandate
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256
from tests.integration.test_execution import FakeRazorpay


POSTGRES_URL = os.getenv("JANUS_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="set JANUS_POSTGRES_TEST_URL for real row-lock tests")


@pytest.fixture
def pg_sessions():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_execution(factory, two=False):
    with factory() as db:
        seed_catalog(db)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        values = {"id": "mnd_race", "instruction_text": "Buy headphones under INR 20,000", "hard_constraints": {"max_amount_paise": 2_000_000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1}, "semantic_constraints": [], "expires_at": now + timedelta(hours=1), "version": 1, "max_executions": 1}
        signer = SignatureService()
        canonical = canonical_json_bytes(canonical_mandate_payload(values))
        mandate = Mandate(**values, signed_version=1, status="ACTIVE", execution_count=0, canonical_payload=canonical.decode(), payload_hash=payload_sha256(canonical), signature=signer.sign(canonical), public_key=signer.public_key_pem)
        db.add(mandate)
        for index in range(2 if two else 1):
            db.add(CheckoutProposal(id=f"prp_race_{index}", mandate_id=mandate.id, mandate_version=1, product_id="prod_a", quantity=1, agent_request_id=f"race-{index}", expected_amount_paise=1849900, currency="INR", status="ALLOWED", decision={}))
        db.commit()


class BlockingRazorpay(FakeRazorpay):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def create_order(self, **kwargs):
        self.entered.set()
        assert self.release.wait(5)
        return super().create_order(**kwargs)


def test_execution_reservation_wins_then_may_complete(pg_sessions) -> None:
    seed_execution(pg_sessions)
    adapter = BlockingRazorpay()
    errors = []

    def execute():
        try:
            with pg_sessions() as db:
                ExecutionService(db, adapter).execute("prp_race_0")
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=execute)
    thread.start()
    assert adapter.entered.wait(5)
    with pg_sessions() as db:
        result = revoke_mandate(db, "mnd_race")
        assert result.status == "CONSUMED"
    adapter.release.set()
    thread.join(5)
    assert not errors
    assert len(adapter.calls) == 1


def test_revocation_wins_then_execution_is_denied(pg_sessions) -> None:
    seed_execution(pg_sessions)
    with pg_sessions() as db:
        assert revoke_mandate(db, "mnd_race").status == "REVOKED"
    adapter = FakeRazorpay()
    with pg_sessions() as db, pytest.raises(AuthorizationDenied):
        ExecutionService(db, adapter).execute("prp_race_0")
    assert adapter.calls == []


def test_two_execution_race_creates_one_order(pg_sessions) -> None:
    seed_execution(pg_sessions, two=True)
    adapter = FakeRazorpay()
    barrier = threading.Barrier(2)
    outcomes = []

    def run(proposal_id):
        barrier.wait()
        try:
            with pg_sessions() as db:
                ExecutionService(db, adapter).execute(proposal_id)
            outcomes.append("executed")
        except AuthorizationDenied:
            outcomes.append("blocked")

    threads = [threading.Thread(target=run, args=(f"prp_race_{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["blocked", "executed"]
    assert len(adapter.calls) == 1


def seed_execution_x20(factory):
    """Seed a mandate and 20 proposals for x20 concurrent test."""
    with factory() as db:
        seed_catalog(db)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        values = {
            "id": "mnd_x20",
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
        
        # Create 20 proposals with the same agent_request_id to test idempotency
        for index in range(20):
            db.add(CheckoutProposal(
                id=f"prp_x20_{index}",
                mandate_id=mandate.id,
                mandate_version=1,
                product_id="prod_a",
                quantity=1,
                agent_request_id="x20-concurrent-test",  # Same request ID for all
                expected_amount_paise=1849900,
                currency="INR",
                status="ALLOWED",
                decision={}
            ))
        db.commit()


def test_x20_concurrent_execution_creates_single_razorpay_order(pg_sessions) -> None:
    """Test that 20 concurrent execution attempts with the same agent_request_id result in exactly one Razorpay order.
    
    This tests both idempotency and concurrency safety:
    - All 20 proposals share the same agent_request_id
    - Only one should succeed in creating a Razorpay order
    - The other 19 should be blocked as duplicates
    """
    seed_execution_x20(pg_sessions)
    adapter = FakeRazorpay()
    barrier = threading.Barrier(20)
    outcomes = []
    lock = threading.Lock()

    def run(proposal_id):
        barrier.wait()  # All threads start at the same time
        try:
            with pg_sessions() as db:
                ExecutionService(db, adapter).execute(proposal_id)
            with lock:
                outcomes.append("executed")
        except AuthorizationDenied:
            with lock:
                outcomes.append("blocked")
        except Exception as e:
            with lock:
                outcomes.append(f"error: {type(e).__name__}")

    # Launch 20 concurrent threads
    threads = [threading.Thread(target=run, args=(f"prp_x20_{index}",)) for index in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)  # Give more time for 20 threads

    # Verify results
    executed_count = sum(1 for o in outcomes if o == "executed")
    blocked_count = sum(1 for o in outcomes if o == "blocked")
    error_count = sum(1 for o in outcomes if o.startswith("error"))
    
    print(f"x20 Test Results: {executed_count} executed, {blocked_count} blocked, {error_count} errors")
    
    # Exactly one should execute, 19 should be blocked
    assert executed_count == 1, f"Expected 1 execution, got {executed_count}"
    assert blocked_count == 19, f"Expected 19 blocked, got {blocked_count}"
    assert error_count == 0, f"Expected 0 errors, got {error_count}"
    
    # Only one Razorpay order should be created
    assert len(adapter.calls) == 1, f"Expected 1 Razorpay call, got {len(adapter.calls)}"
    
    # Verify the Razorpay order was created with the correct amount
    assert adapter.calls[0]["amount"] == 18499  # ₹18,499 in rupees
