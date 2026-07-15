import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def mk_manifest(models):
    """models: list of (name, [columns], raw_sql)."""
    return {"nodes": {
        f"model.fiction_retail.{name}": {
            "name": name,
            "raw_code": sql,
            "columns": {c: {"data_type": None} for c in cols},
        } for name, cols, sql in models
    }}
