from collections.abc import Iterable, Sequence

from sqlalchemy import String, any_, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.orm import Session

from app.models import Department, Location, name_key
from app.schemas import NameQuery


def list_names[T: (Department, Location)](
    session: Session, model: type[T], query: NameQuery
) -> tuple[Sequence[T], int]:
    """Departments or locations alphabetically, narrowed down by part of their name."""
    statement = select(model)
    if query.q:
        key = name_key(query.q)
        statement = statement.where(
            model.key.contains(key, autoescape=True)
            if key
            else model.name.icontains(query.q, autoescape=True)
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.scalars(
        statement.order_by(func.lower(model.name))
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return rows.all(), total or 0


def ids_by_key(
    session: Session, model: type[Department | Location], names: Iterable[str | None]
) -> dict[str, int]:
    """The ids of these names, by key, adding those that are new; the first spelling of a
    new name becomes its name. Names without letters or digits have no key and are left out."""
    new: dict[str, str] = {}
    for name in names:
        if name and (key := name_key(name)):
            new.setdefault(key, name)
    if not new:
        return {}
    session.execute(
        insert(model)
        .values([{"name": name, "key": key} for key, name in new.items()])
        .on_conflict_do_nothing(index_elements=[model.key])
    )
    keys = literal(list(new), ARRAY(String))
    rows = session.execute(select(model.key, model.id).where(model.key == any_(keys)))
    return {key: id_ for key, id_ in rows}
