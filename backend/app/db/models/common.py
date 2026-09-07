from enum import Enum as PythonEnum
from typing import Any

from sqlalchemy import Enum


def database_enum(enum_class: type[PythonEnum], name: str, length: int = 32) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


JsonObject = dict[str, Any]

