import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa

import ibis


def test_read_csv(data_directory):
    t = ibis.read_csv(data_directory / "functional_alltypes.csv")
    assert t.count().execute()


def test_read_parquet(data_directory):
    t = ibis.read_parquet(data_directory / "functional_alltypes.parquet")
    assert t.count().execute()


def test_read_json(data_directory, tmp_path):
    pqt = ibis.read_parquet(data_directory / "functional_alltypes.parquet")

    path = tmp_path.joinpath("ft.json")
    path.write_text(pqt.execute().to_json(orient="records", lines=True))

    jst = ibis.read_json(path)

    nrows = pqt.count().execute()
    assert nrows
    assert nrows == jst.count().execute()


def test_temp_directory(tmp_path):
    query = sa.text("SELECT value FROM duckdb_settings() WHERE name = 'temp_directory'")

    # 1. in-memory + no temp_directory specified
    con = ibis.duckdb.connect()
    with con.begin() as c:
        cur = c.execute(query)
        value = cur.scalar()
        assert value  # we don't care what the specific value is

    temp_directory = Path(tempfile.gettempdir()) / "duckdb"

    # 2. in-memory + temp_directory specified
    con = ibis.duckdb.connect(temp_directory=temp_directory)
    with con.begin() as c:
        cur = c.execute(query)
        value = cur.scalar()
    assert value == str(temp_directory)

    # 3. on-disk + no temp_directory specified
    # untested, duckdb sets the temp_directory to something implementation
    # defined

    # 4. on-disk + temp_directory specified
    con = ibis.duckdb.connect(tmp_path / "test2.ddb", temp_directory=temp_directory)
    with con.begin() as c:
        cur = c.execute(query)
        value = cur.scalar()
    assert value == str(temp_directory)


@pytest.fixture(scope="session")
def pgurl():  # pragma: no cover
    pgcon = ibis.postgres.connect(user="postgres", password="postgres")
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 1.0], "y": ["a", "b", "c", "a"]})
    s = ibis.schema(dict(x="float64", y="str"))

    pgcon.create_table("duckdb_test", df, s, force=True)
    yield pgcon.con.url
    pgcon.drop_table("duckdb_test", force=True)


@pytest.mark.skipif(
    os.environ.get("DUCKDB_POSTGRES") is None, reason="avoiding CI shenanigans"
)
def test_read_postgres(pgurl):  # pragma: no cover
    con = ibis.duckdb.connect()
    table = con.read_postgres(
        f"postgres://{pgurl.username}:{pgurl.password}@{pgurl.host}:{pgurl.port}",
        table_name="duckdb_test",
    )
    assert table.count().execute()


def test_read_sqlite(data_directory):
    con = ibis.duckdb.connect()
    path = data_directory / "ibis_testing.db"
    ft = con.read_sqlite(path, table_name="functional_alltypes")
    assert ft.count().execute()

    with pytest.raises(ValueError):
        con.read_sqlite(path)


def test_read_sqlite_no_table_name(data_directory):
    con = ibis.duckdb.connect()
    path = data_directory / "ibis_testing.db"

    with pytest.raises(ValueError):
        con.read_sqlite(path)


def test_register_sqlite(data_directory):
    con = ibis.duckdb.connect()
    path = data_directory / "ibis_testing.db"
    ft = con.register(f"sqlite://{path}", "functional_alltypes")
    assert ft.count().execute()
