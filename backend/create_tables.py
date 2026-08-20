from app.database import Base, engine
from app.models import Trace, TraceEvent


Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")