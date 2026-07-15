"""Environment-driven configuration. Mode resolution lives here so every
other module can stay ignorant of live-vs-offline (ADR-0007)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@dataclass
class Config:
    datahub_gms_url: str
    datahub_gms_token: str
    google_api_key: str
    github_token: str
    github_repository: str      # "owner/repo"
    bq_project: str
    bq_dataset: str
    mode: str                   # "live" | "offline"

    @classmethod
    def from_env(cls, mode: str = "auto") -> "Config":
        gms_url = os.environ.get("DATAHUB_GMS_URL", "")
        gms_token = os.environ.get("DATAHUB_GMS_TOKEN", "")
        if mode == "auto":
            # Token optional: a local quickstart runs without metadata auth
            mode = "live" if gms_url else "offline"
        return cls(
            datahub_gms_url=gms_url.rstrip("/"),
            datahub_gms_token=gms_token,
            google_api_key=os.environ.get("GOOGLE_API_KEY", "")
            or os.environ.get("GEMINI_API_KEY", ""),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            github_repository=os.environ.get("GITHUB_REPOSITORY", ""),
            # `or` (not get() default): Actions passes unset vars as ""
            bq_project=os.environ.get("GCP_PROJECT") or "dig-demo-sandbox",
            bq_dataset=os.environ.get("BQ_DATASET") or "fiction_retail",
            mode=mode,
        )

    def dataset_urn(self, model_name: str) -> str:
        fqn = f"{self.bq_project}.{self.bq_dataset}.{model_name}"
        return f"urn:li:dataset:(urn:li:dataPlatform:bigquery,{fqn},PROD)"
