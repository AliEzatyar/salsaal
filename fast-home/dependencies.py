from database import SessionLocal
from fastapi import Depends


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() # return connnection obj to conn pool for reuse
        
        
