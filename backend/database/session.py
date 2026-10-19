from collections.abc import Generator

from pathlib import Path

 

from sqlalchemy import Engine, create_engine, event

from sqlalchemy.orm import Session, sessionmaker

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_DIR = PROJECT_ROOT / "data" / "database"

DATABASE_FILE = DATABASE_DIR / "customer_support.db"

DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"

 

 

def ensure_database_directory() -> None:

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

 

 

ensure_database_directory()

 

engine: Engine = create_engine(

    DATABASE_URL,

    connect_args={

        "check_same_thread": False,

    },

)

 

 

@event.listens_for(engine, "connect")

def enable_sqlite_foreign_keys(

    database_connection,

    connection_record,

) -> None:

    """

    SQLite does not enforce foreign keys unless enabled for each connection.

    """

    del connection_record

 

    cursor = database_connection.cursor()

    cursor.execute("PRAGMA foreign_keys=ON")

    cursor.close()

 

 

SessionLocal = sessionmaker(

    bind=engine,

    autoflush=False,

    expire_on_commit=False,

)

 

 

def get_session() -> Generator[Session, None, None]:

    session = SessionLocal()

 

    try:

        yield session

    finally:

        session.close()

