from app.db import SessionLocal
from app.seeds import run

with SessionLocal() as db:
    print(run(db))
