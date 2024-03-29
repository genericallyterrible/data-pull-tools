"""
Utilities for reading and modifying TOML files.

Includes functions to load TOML files, get or create tables, and update values.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from functools import partial
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeVar

import tomlkit
from tomlkit import TOMLDocument, table
from tomlkit.container import Container
from tomlkit.items import Item, Table

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any


Pathish = str | PathLike[str] | Path
Containerish = Container | Table


K = TypeVar("K")
V = TypeVar("V")
RecursiveMap = Mapping[K, V | "RecursiveMap[K, V]"]
CollisionPolicy = Literal["raise", "replace"]
DEFAULT_COLLISION_POLICY: CollisionPolicy = "replace"


@contextmanager
def manage_toml_file(
    path: Pathish,
) -> Generator[TOMLDocument, Any, None]:
    """Manages a toml file in a context.
    Loads the file, yields the contents, and then saves when the context exits.

    Parameters
    ----------
    path : Pathish
        The path to the toml file.

    Yields
    ------
    TOMLDocument
        The loaded toml file.
    """
    path = Path(path)
    with path.open(mode="r+") as f:
        doc = tomlkit.load(f)
        yield doc
        f.seek(0)
        tomlkit.dump(doc, f)
        f.truncate()


def load_toml(
    path: Pathish,
) -> TOMLDocument:
    """Loads a toml file into memory.

    Parameters
    ----------
    path : Pathish
        The path to the toml file.

    Returns
    -------
    TOMLDocument
        The loaded toml document.
    """
    path = Path(path)
    with path.open(mode="rb") as f:
        return tomlkit.load(f)


class NonTableKeyCollisionError(Exception):
    ...


def _toml_get_or_table(
    toml: Containerish,
    key: str,
    *,
    collisions: CollisionPolicy = "replace",
) -> Table:
    """Gets a table from the given key, creating if missing.

    Parameters
    ----------
    toml : Containerish
        The parent toml object.
    key : str
        The key to get or create the table at.
    collisions : CollisionPolicy, default="replace"
        How to handle collisions, by default "replace".

    Returns
    -------
    Table
        The table at the given key.

    Raises
    ------
    NonTableKeyCollisionError
        If `collisions` is "raise" and the key already exists but is not a table.
    """
    if key not in toml:
        value = table()
        toml.add(key, value)
        return value

    value = toml[key]
    if not isinstance(value, Table):
        # Handle collisions
        if collisions == "raise":
            msg = "Key '%s' already exists and is not a table."
            raise NonTableKeyCollisionError(msg, key)
        if collisions == "replace":
            value = table()
            toml[key] = value
    return value


def update_toml_values(
    toml: Containerish,
    data: RecursiveMap[str, Any],
    *,
    collisions: CollisionPolicy = "replace",
) -> Containerish:
    """Updates the given toml values with the provided data.
    Creates intermediary tables as needed.

    Parameters
    ----------
    toml : Containerish
        The toml object to update.
    data : RecursiveMap[str, Any]
        The data to update the toml with.
    collisions : CollisionPolicy, default="replace"
        How to handle key collisions, by default "replace"

    Returns
    -------
    Containerish
        The updated toml object.
    """
    getter = partial(_toml_get_or_table, toml=toml, collisions=collisions)
    updater = partial(update_toml_values, collisions=collisions)

    for key, value in data.items():
        if isinstance(value, Mapping):
            updater(getter(key=key), value)
            continue
        toml[key] = value
    return toml


def update_toml_file(
    toml_path: Pathish,
    data: RecursiveMap[str, Any],
    *,
    collisions: CollisionPolicy = "replace",
) -> None:
    """Opens a toml file, updates its contents with the provided data, and saves it.
    Creates intermediary tables as needed.

    Parameters
    ----------
    toml_path : Pathish
        The path to the toml file to update.
    data : RecursiveMap[str, Any]
        The data to update the toml with.
    collisions : CollisionPolicy, default="replace"
        How to handle data key collisions, by default "replace"
    """
    with manage_toml_file(toml_path) as toml_file:
        update_toml_values(toml_file, data, collisions=collisions)


def update_toml_value(
    toml: Containerish,
    key_chain: str | Sequence[str],
    value: Any,  # noqa: ANN401
    *,
    collisions: CollisionPolicy = "replace",
) -> Containerish:
    current = toml
    if isinstance(key_chain, str):
        key_chain = [key_chain]

    for key in key_chain[:-1]:
        current = _toml_get_or_table(current, key, collisions=collisions)
    current[key_chain[-1]] = value
    return toml


def update_toml_file_value(
    toml_path: Pathish,
    key_chain: str | Sequence[str],
    value: Any,  # noqa: ANN401
    *,
    collisions: CollisionPolicy = "replace",
) -> None:
    with manage_toml_file(toml_path) as toml_file:
        update_toml_value(toml_file, key_chain, value, collisions=collisions)


def _get_toml_or_none(
    toml: Containerish,
    key: str,
) -> Item | Container | None:
    if key not in toml:
        return None
    return toml[key]


def get_toml_container(
    toml: Containerish,
    key_chain: str | Sequence[str],
) -> Containerish | None:
    current = toml
    if isinstance(key_chain, str):
        key_chain = [key_chain]

    for key in key_chain:
        if current is None or not isinstance(current, Containerish):
            # Exhausted early
            return None
        current = _get_toml_or_none(current, key)
    return current if isinstance(current, Containerish) else None


def get_toml_item(
    toml: Containerish,
    key_chain: str | Sequence[str],
) -> Item | None:
    current = toml
    if isinstance(key_chain, str):
        key_chain = [key_chain]

    for key in key_chain:
        if current is None or not isinstance(current, Containerish):
            # Exhausted early
            return None
        current = _get_toml_or_none(current, key)
    return current if not isinstance(current, Containerish) else None
