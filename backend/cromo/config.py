"""Runtime configuration, read from environment variables (and a local .env in dev).

Secrets are only ever read here and passed to server-side clients. Nothing in
this module is exposed to the browser except `public_summary()`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(os.environ.get("CROMO_ROOT", Path(__file__).resolve().parents[2]))

# AMD Token Factory (event API): OpenAI-compatible shared endpoints on AMD GPUs; one key for every model.
TOKEN_FACTORY_BASE_URL = "https://developer.amd.com.cn/radeon/api/v1"
# Its documented limits are per key (20 requests/min per account, 8 concurrent); stay a little below them.
TOKEN_FACTORY_RPM = 18
TOKEN_FACTORY_CONCURRENCY = 6


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
    rpm_limit: int = 0  # client-side requests/minute per endpoint key (0 = unlimited)
    reasoning_effort: str = ""  # sent to the REASONER when set (Token Factory: none|low|medium|high ...)
    stream: bool = False  # stream answers (default on the Token Factory: its 10-minute limit is per chunk gap when streaming)
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
    api_docs: bool = False  # interactive /api/docs-ui; development only
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


def _role(name: str, fallback: RoleConfig | None = None, default_base: str = "", default_key: str = "") -> RoleConfig:
    p = f"CROMO_{name.upper()}_"
    base, key, model = _get(p + "BASE_URL"), _get(p + "API_KEY"), _get(p + "MODEL")
    if fallback is not None:
        base = base or (fallback.base_url if model else "")
        key = key or (fallback.api_key if base == fallback.base_url else "")
    base = base or (default_base if model else "")
    key = key or (default_key if base and base.rstrip("/") == default_base.rstrip("/") else "")
    return RoleConfig(name, base.rstrip("/"), key, model)


def load_settings() -> Settings:
    route = _get("CROMO_AMD_ROUTE", "vllm").lower()
    tf = route == "tokenfactory"
    # On the Token Factory route every role defaults to the event endpoint and the team key (AMD_TOKEN_FACTORY).
    tf_base = (_get("AMD_TOKEN_FACTORY_BASE_URL") or TOKEN_FACTORY_BASE_URL) if tf else ""
    tf_key = _get("AMD_TOKEN_FACTORY") if tf else ""
    reasoner = _role("reasoner", None, tf_base, tf_key)
    origins = tuple(o.strip() for o in _get("CROMO_ALLOWED_ORIGINS").split(",") if o.strip())
    return Settings(
        provider=_get("CROMO_PROVIDER", "fixture").lower(),
        amd_route=route,
        reasoner=reasoner,
        vision=_role("vision", reasoner, tf_base, tf_key),
        embeddings=_role("embeddings", reasoner, tf_base, tf_key),
        speech=_role("speech", reasoner, tf_base, tf_key),
        structured_output=_get("CROMO_STRUCTURED_OUTPUT", "json_object").lower(),
        hardware_label=_get("CROMO_HARDWARE_LABEL") or ("AMD Token Factory (shared endpoints on AMD GPUs)" if tf
                                                         else "AMD Instinct MI300X (192 GB HBM3), ROCm + vLLM"),
        gpu_price_per_hour=float(_get("CROMO_GPU_PRICE_PER_HOUR", "1.99") or 1.99),
        gpu_price_source=_get("CROMO_GPU_PRICE_SOURCE",
                              "AMD Developer Cloud list price, 1x MI300X: https://docs.digitalocean.com/products/amd/details/pricing/"),
        # the Token Factory allows 10 minutes for a non-streaming request; under load a long answer can take minutes
        request_timeout_s=float(_get("CROMO_REQUEST_TIMEOUT_S") or (600 if tf else 120)),
        # empty = route default; the Token Factory limits are per key, so CROMO paces itself below them
        max_concurrency=int(_get("CROMO_MAX_CONCURRENCY") or (TOKEN_FACTORY_CONCURRENCY if tf else 8)),
        rpm_limit=int(_get("CROMO_RPM_LIMIT") or (TOKEN_FACTORY_RPM if tf else 0)),
        reasoning_effort=_get("CROMO_REASONING_EFFORT").lower(),
        stream=_bool("CROMO_STREAM", tf),
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
        api_docs=_bool("CROMO_API_DOCS", False),
        data_dir=Path(_get("CROMO_DATA_DIR") or (ROOT / "data")),
    )


settings = load_settings()


def reload_settings() -> Settings:
    global settings
    settings = load_settings()
    return settings
