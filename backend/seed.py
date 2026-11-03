"""Creates the tables and a small set of demo data.
Run from the backend folder:   python seed.py
The ids are fixed on purpose, so Member 2's tests and Member 3's screens can rely on them."""
from app.db import SessionLocal, init_db
from app.models import Customer, Account, Merchant, Device


def seed(db):
    """Adds the demo data once. Returns True if it added data, False if it was already there."""
    if db.get(Customer, "cust-alice") is not None:
        return False
    db.add_all([
        Customer(id="cust-alice", name="Alice", email="alice@example.com",
                 avg_txn_amount=2000, home_location="Hubballi"),
        Customer(id="cust-bob", name="Bob", email="bob@example.com",
                 avg_txn_amount=1500, home_location="Bengaluru"),
        Customer(id="cust-chai", name="Chai Stall", email="chai@example.com",
                 avg_txn_amount=500, home_location="Hubballi"),
    ])
    db.flush()      # customers must exist before the accounts that point to them
    db.add_all([
        Account(id="acc-alice", customer_id="cust-alice", account_number="ACC-ALICE-01", balance=50000),
        Account(id="acc-bob", customer_id="cust-bob", account_number="ACC-BOB-01", balance=30000),
        Account(id="acc-chai", customer_id="cust-chai", account_number="ACC-CHAI-01", balance=8000),
        Merchant(id="m-chai", name="Chai Stall", risk_level=10),
        Merchant(id="m-gift", name="Gift Card Hub", risk_level=80),
        Device(id="dev-1", customer_id="cust-alice", device_fingerprint="fp-alice-phone",
               ip_address="192.168.1.10"),
    ])
    db.commit()
    return True


if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    print("Seeded demo data." if seed(session) else "Demo data already present. Nothing changed.")
    session.close()
