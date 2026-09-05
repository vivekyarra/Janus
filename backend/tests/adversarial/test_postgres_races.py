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
