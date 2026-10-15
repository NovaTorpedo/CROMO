"""Runtime configuration, read from environment variables (and a local .env in dev).

Secrets are only ever read here and passed to server-side clients. Nothing in
this module is exposed to the browser except `public_summary()`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(os.environ.get("CROMO_ROOT", Path(__file__).resolve().parents[2]))


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env, override=False)
        except ImportError:  # pragma: no cover
            pass


_load_dotenv()


def _get(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    if v is None:
        # tolerate lowercase variants (the original workspace .env used them)
        v = os.environ.get(name.lower(), default)
    return v.strip()


def _bool(name: str, default: bool = False) -> bool:
    v = _get(name, "")
    return default if v == "" else v.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class RoleConfig:
    role: str
    base_url: str
    api_key: str = field(repr=False)
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


@dataclass(frozen=True)
class Settings:
    provider: str  # "fixture" | "amd"
    amd_route: str  # "vllm" | "tokenfactory" (label only)
    reasoner: RoleConfig
    vision: RoleConfig
    embeddings: RoleConfig
    speech: RoleConfig
    structured_output: str  # "json_schema" | "json_object" | "none"
    hardware_label: str
    gpu_price_per_hour: float
    gpu_price_source: str
    request_timeout_s: float
    max_concurrency: int
    evolus_api_key: str = field(repr=False)
    evolus_application_id: str = field(repr=False)
    evolus_extractor_agent_id: str = ""
    evolus_extractor_id: str = ""
    evolus_trial_workflow_id: str = ""
    evolus_library_id: str = ""
    evolus_agent_model: str = ""
    evolus_enabled: bool = True
    metadata_source: str = "auto"  # auto | reasoner | evolus | fixture
    access_token: str = field(default="", repr=False)
    allowed_origins: tuple[str, ...] = ()
    public_demo: bool = False
    archive_dir: Path = ROOT / "archive"
    data_dir: Path = ROOT / "data"
    fixtures_dir: Path = ROOT / "fixtures"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    @property
    def runtime_dir(self) -> Path:
        return self.data_dir / "runtime"

    @property
    def db_path(self) -> Path:
        return self.runtime_dir / "cromo.db"

    @property
    def recorded_dir(self) -> Path:
        return self.data_dir / "recorded"

    @property
    def is_live(self) -> bool:
        return self.provider == "amd" and self.reasoner.configured

    @property
    def evolus_configured(self) -> bool:
        return self.evolus_enabled and bool(self.evolus_api_key and self.evolus_application_id)

    def public_summary(self) -> dict:
        """Safe, secret-free description for the UI."""
        def role(r: RoleConfig) -> dict:
            fam = "gemma" if "gemma" in r.model.lower() else ("qwen" if "qwen" in r.model.lower() else "other")
            return {"configured": r.configured, "model": r.model if r.configured else None, "family": fam if r.configured else None,
                    "endpoint_host": _host(r.base_url) if r.configured else None}

        return {
            "provider": "amd" if self.is_live else "fixture",
            "amd_route": self.amd_route,
            "hardware": self.hardware_label,
            "gpu_price_per_hour": self.gpu_price_per_hour,
            "gpu_price_source": self.gpu_price_source,
            "roles": {"reasoner": role(self.reasoner), "vision": role(self.vision),
                      "embeddings": role(self.embeddings), "speech": role(self.speech)},
            "evolus": {
                "configured": self.evolus_configured,
                "extractor": bool(self.evolus_extractor_id),
                "trial_workflow": bool(self.evolus_trial_workflow_id),
                "library": bool(self.evolus_library_id),
                "agent": bool(self.evolus_agent_model),
            },
            "public_demo": self.public_demo,
            "write_protected": bool(self.access_token),
        }


def _host(url: str) -> str:
    from urllib.parse import urlparse

    try:
        h = urlparse(url).hostname or ""
    except ValueError:
        return ""
    # never reveal raw IPs of private endpoints in the UI
    if h.replace(".", "").isdigit():
        return "private vLLM endpoint"
    return h


def _role(name: str, fallback: RoleConfig | None = None) -> RoleConfig:
    p = f"CROMO_{name.upper()}_"
    base, key, model = _get(p + "BASE_URL"), _get(p + "API_KEY"), _get(p + "MODEL")
    if fallback is not None:
        base = base or (fallback.base_url if model else "")
        key = key or (fallback.api_key if base == fallback.base_url else "")
    return RoleConfig(name, base.rstrip("/"), key, model)


def load_settings() -> Settings:
    reasoner = _role("reasoner")
    origins = tuple(o.strip() for o in _get("CROMO_ALLOWED_ORIGINS").split(",") if o.strip())
    return Settings(
        provider=_get("CROMO_PROVIDER", "fixture").lower(),
        amd_route=_get("CROMO_AMD_ROUTE", "vllm").lower(),
        reasoner=reasoner,
        vision=_role("vision", reasoner),
        embeddings=_role("embeddings", reasoner),
        speech=_role("speech", reasoner),
        structured_output=_get("CROMO_STRUCTURED_OUTPUT", "json_object").lower(),
        hardware_label=_get("CROMO_HARDWARE_LABEL", "AMD Instinct MI300X (192 GB HBM3), ROCm + vLLM"),
        gpu_price_per_hour=float(_get("CROMO_GPU_PRICE_PER_HOUR", "1.99") or 1.99),
        gpu_price_source=_get("CROMO_GPU_PRICE_SOURCE",
                              "AMD Developer Cloud list price, 1x MI300X: https://docs.digitalocean.com/products/amd/details/pricing/"),
        request_timeout_s=float(_get("CROMO_REQUEST_TIMEOUT_S", "120") or 120),
        max_concurrency=int(_get("CROMO_MAX_CONCURRENCY", "8") or 8),
        evolus_api_key=_get("EVOLUS_API_KEY"),
        evolus_application_id=_get("EVOLUS_APPLICATION_ID"),
        evolus_extractor_agent_id=_get("EVOLUS_EXTRACTOR_AGENT_ID"),
        evolus_extractor_id=_get("EVOLUS_EXTRACTOR_ID"),
        evolus_trial_workflow_id=_get("EVOLUS_TRIAL_WORKFLOW_ID"),
        evolus_library_id=_get("EVOLUS_LIBRARY_ID"),
        evolus_agent_model=_get("EVOLUS_AGENT_MODEL"),
        evolus_enabled=_bool("CROMO_EVOLUS_ENABLED", True),
        metadata_source=_get("CROMO_METADATA_SOURCE", "auto").lower(),
        access_token=_get("CROMO_ACCESS_TOKEN"),
        allowed_origins=origins,
        public_demo=_bool("CROMO_PUBLIC_DEMO", False),
        data_dir=Path(_get("CROMO_DATA_DIR") or (ROOT / "data")),
    )


settings = load_settings()


def reload_settings() -> Settings:
    global settings
    settings = load_settings()
    return settings
