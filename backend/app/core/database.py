from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.sessionmaker
    with factory() as session:
        yield session
