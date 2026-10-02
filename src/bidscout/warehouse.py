"""Build the warehouse and read the tables the app is allowed to read.

The data has three homes, in this order (docs/data-model.md has the picture):

1. **Landing** — the SQLite file ``bidscout watch``, ``fetch`` and ``score``
   write. The portal's JSON exactly as it arrived, plus the rules engine's
   verdicts. Ground rule 3 lives here.
2. **Warehouse** — a DuckDB file built from landing by the dbt project in
   ``warehouse/``: staging views, then ``core`` facts and dimensions, then the
   ``app`` marts. Landing is attached read-only; dbt never writes to it.
3. **Site** — ``site/data.json``, written by ``bidscout export`` from the
   ``app`` marts and nothing else.

``dbt build`` runs the data tests as well as the models, so a contract the
marts break (a duplicate notice, a decision on a notice nobody read) stops the
export instead of reaching the page.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from bidscout.errors import BidscoutError

#: The dbt project. The package is installed editable from this repository, so
#: the project sits two levels above ``src/bidscout``.
PROJECT_DIR = Path(
    os.environ.get("BIDSCOUT_DBT_PROJECT", Path(__file__).resolve().parents[2] / "warehouse")
)

#: The only tables ``export`` reads. Everything else in the warehouse is for
#: analysis; a new page feature starts by adding a column to one of these.
APP_MARTS = ("app_tenders", "app_tender_reasons", "app_tender_requirements", "app_pipeline_status")


#: The name the landing SQLite file is attached under (warehouse/profiles.yml).
LANDING_ALIAS = "bidscout_landing"


class WarehouseBuildFailed(BidscoutError):
    """``dbt build`` failed: a model did not build or a data test did not pass."""


def warehouse_path_for(db_path: str | Path) -> Path:
    """Where the warehouse for a landing file lives: beside it, same stem.

    ``data/bidscout.sqlite3`` builds ``data/bidscout.duckdb`` and the demo's
    ``data/demo.sqlite3`` builds ``data/demo.duckdb``, so the two never mix.
    """
    path = Path(db_path)
    return path.with_name(f"{path.stem}.duckdb")


def transform(
    db_path: str | Path, warehouse: str | Path | None = None, company: str = "Example SRL"
) -> Path:
    """Run ``dbt build`` over the landing file and return the warehouse path.

    ``company`` picks whose verdicts the app marts show; the scores table holds
    one row per (notice, company).

    dbt runs in its own process. In-process, dbt-duckdb keeps its handle on the
    warehouse open, and DuckDB then refuses the read-only connection the export
    opens next; dbt also reconfigures logging globally, which a CLI should not
    inherit.
    """
    landing = Path(db_path).resolve()
    if not landing.exists():
        raise WarehouseBuildFailed(f"no landing database at {landing}")
    target = Path(warehouse).resolve() if warehouse else warehouse_path_for(landing)
    if target.stem == LANDING_ALIAS:
        # DuckDB names a database after its file, so this one would collide
        # with the attached landing file and dbt would fail with a binder error.
        raise WarehouseBuildFailed(f"the warehouse cannot be called {target.name}; rename it")
    target.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable, "-c", "from dbt.cli.main import cli; cli()",
        "build",
        "--project-dir", str(PROJECT_DIR),
        "--profiles-dir", str(PROJECT_DIR),
        "--target-path", str(PROJECT_DIR / "target"),
        "--log-path", str(PROJECT_DIR / "logs"),
        "--vars", _yaml_vars({"company": company}),
        "--no-use-colors",
    ]
    env = {**os.environ, "BIDSCOUT_DB": str(landing), "BIDSCOUT_WAREHOUSE": str(target)}
    done = subprocess.run(
        command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    if done.returncode != 0:
        # The last lines name the model or the data test that failed.
        tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-25:])
        raise WarehouseBuildFailed(f"dbt build failed:\n{tail}")
    return target


def _yaml_vars(values: dict[str, str]) -> str:
    """``--vars`` as a YAML flow mapping, each value quoted so a name stays a string."""
    quoted = ", ".join(f"{key}: {_quote(value)}" for key, value in values.items())
    return "{" + quoted + "}"


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def open_for_exploring(db_path: str | Path, warehouse: str | Path) -> Any:
    """Open the warehouse read-only, with landing attached the way dbt attaches it.

    Attached under the same alias, the staging views resolve, so every layer —
    landing, staging, intermediate, core, app — can be browsed in one place.
    Read-only on both, so exploring can never change what the page is built from.
    """
    import duckdb  # noqa: PLC0415 - only exploring and the export need it

    connection = duckdb.connect(str(warehouse), read_only=True)
    landing = Path(db_path).resolve().as_posix().replace("'", "''")
    connection.execute("INSTALL sqlite; LOAD sqlite;")
    connection.execute(f"ATTACH '{landing}' AS {LANDING_ALIAS} (TYPE sqlite, READ_ONLY)")
    return connection


def read_app_marts(warehouse: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Return every row of every ``app`` mart, as plain dicts.

    DuckDB hands DECIMAL columns back as ``Decimal`` and timestamps as
    ``datetime``; the export turns both into strings. Nothing here is a float.
    """
    import duckdb  # noqa: PLC0415 - only the export needs it

    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        marts: dict[str, list[dict[str, Any]]] = {}
        for name in APP_MARTS:
            cursor = connection.execute(f"SELECT * FROM app.{name}")
            columns = [column[0] for column in cursor.description]
            marts[name] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return marts
    finally:
        connection.close()
