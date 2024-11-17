from datetime import date
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from core.config import settings



#print(Settings.POSTGRES_USER)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

#SQLModel.metadata.create_all(engine)

