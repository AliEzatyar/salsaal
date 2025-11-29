from database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() # return connnection obj to conn pool for reuse
        
        
