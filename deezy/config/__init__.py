import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class DatabaseSettings:
    type: str = "sqlite"
    path: str = "data/deezy.db"
    host: str = ""
    port: int = 5432
    name: str = ""
    user: str = ""
    password: str = ""


@dataclass
class LLMSettings:
    provider: str = "local"
    model: str = "llama3.2:3b"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60
    max_retries: int = 3
    provider_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSettings:
    max_iterations: int = 10
    max_tool_calls_per_iteration: int = 3
    enable_memory: bool = True
    memory_limit: int = 50
    approval_required_for_high_risk: bool = True
    approval_required_for_medium_risk: bool = False
    auto_approve_low_risk: bool = True


@dataclass
class ToolsSettings:
    product_research: Dict[str, Any] = field(default_factory=dict)
    website: Dict[str, Any] = field(default_factory=dict)
    pinterest: Dict[str, Any] = field(default_factory=dict)
    analytics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerSettings:
    enabled: bool = False
    timezone: str = "UTC"
    jobs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalSettings:
    risk_levels: Dict[str, Any] = field(default_factory=dict)
    notification_methods: list = field(default_factory=list)


@dataclass
class LoggingSettings:
    level: str = "DEBUG"
    format: str = "json"
    file: str = "data/deezy.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console_output: bool = True


@dataclass
class WebsiteSettings:
    root_path: str = ""
    data_path: str = ""
    templates_path: str = ""
    categories: list = field(default_factory=list)
    affiliate_tag: str = ""


@dataclass
class ScoringSettings:
    weights: Dict[str, float] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExternalAPISettings:
    reddit: Dict[str, Any] = field(default_factory=dict)
    amazon_paapi: Dict[str, Any] = field(default_factory=dict)
    pinterest: Dict[str, Any] = field(default_factory=dict)
    google_analytics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Settings:
    app: Dict[str, Any] = field(default_factory=dict)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    tools: ToolsSettings = field(default_factory=ToolsSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    events: Dict[str, Any] = field(default_factory=dict)
    approval: ApprovalSettings = field(default_factory=ApprovalSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    website: WebsiteSettings = field(default_factory=WebsiteSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    external_apis: ExternalAPISettings = field(default_factory=ExternalAPISettings)


def is_demo() -> bool:
    """True for the hosted, sandboxed demo: DEEZY_DEMO=1, or any Vercel deployment."""
    return os.environ.get("DEEZY_DEMO", "").lower() in ("1", "true", "yes") or bool(os.environ.get("VERCEL"))


def load_config(config_path: Optional[str] = None) -> Settings:
    """Load configuration from YAML file with environment variable substitution."""
    if config_path is None:
        config_path = os.environ.get("DEEZY_CONFIG") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "settings.yaml"
        )

    path = Path(config_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Load .env file if exists
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path)

    # Substitute environment variables
    def substitute_env(obj: Any) -> Any:
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.environ.get(env_var, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: substitute_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [substitute_env(item) for item in obj]
        return obj

    raw = substitute_env(raw)

    # Build settings object
    settings = Settings()

    if "app" in raw:
        settings.app = raw["app"]

    if "database" in raw:
        settings.database = DatabaseSettings(**raw["database"])

    if "llm" in raw:
        llm_data = raw["llm"]
        provider_settings = llm_data.pop("provider_settings", {})
        # Extract provider-specific settings
        for provider in ["openrouter", "openai", "local", "anthropic", "ollama"]:
            if provider in llm_data:
                provider_settings[provider] = llm_data.pop(provider)
        settings.llm = LLMSettings(**llm_data, provider_settings=provider_settings)

    if "agent" in raw:
        settings.agent = AgentSettings(**raw["agent"])

    if "tools" in raw:
        settings.tools = ToolsSettings(**raw["tools"])

    if "scheduler" in raw:
        settings.scheduler = SchedulerSettings(**raw["scheduler"])

    if "events" in raw:
        settings.events = raw["events"]

    if "approval" in raw:
        settings.approval = ApprovalSettings(**raw["approval"])

    if "logging" in raw:
        settings.logging = LoggingSettings(**raw["logging"])

    if "website" in raw:
        settings.website = WebsiteSettings(**raw["website"])

    if "scoring" in raw:
        settings.scoring = ScoringSettings(**raw["scoring"])

    if "external_apis" in raw:
        settings.external_apis = ExternalAPISettings(**raw["external_apis"])

    # Environment overrides
    if os.environ.get("DEEZY_LLM_PROVIDER"):
        settings.llm.provider = os.environ["DEEZY_LLM_PROVIDER"].lower()
    if is_demo():
        # The hosted demo never calls an LLM and never reaches the network.
        settings.llm.provider = "mock"
        settings.llm.model = "mock-model"
        # Show the approval flow: medium-risk steps (e.g. creating a file) must be approved.
        settings.agent.approval_required_for_medium_risk = True
    if os.environ.get("AFFILIATE_TAG"):
        settings.website.affiliate_tag = os.environ["AFFILIATE_TAG"]

    # Apply cost constraint from identity or env
    max_cost = int(os.environ.get("MAX_MONTHLY_COST", settings.app.get("max_monthly_cost", 0)))
    settings.app["max_monthly_cost"] = max_cost

    return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance (singleton)."""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


def reset_settings():
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
