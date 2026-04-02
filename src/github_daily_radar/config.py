from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    github_token: str = Field(alias="GITHUB_TOKEN")
    github_pat: str | None = Field(default=None, alias="GITHUB_PAT")
    qwen_api_key: str = Field(alias="QWEN_API_KEY")
    feishu_webhook_url: str = Field(alias="FEISHU_WEBHOOK_URL")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")
    default_model: str = Field(default="codingplan", alias="LLM_MODEL")
    llm_max_candidates: int = Field(default=24, alias="LLM_MAX_CANDIDATES")
    search_requests_per_minute: int = Field(default=25, alias="SEARCH_REQUESTS_PER_MINUTE")
    api_total_budget: int = Field(default=36, alias="API_TOTAL_BUDGET")
    api_search_budget: int = Field(default=18, alias="API_SEARCH_BUDGET")
    api_graphql_budget: int = Field(default=600, alias="API_GRAPHQL_BUDGET")
    cooldown_days: int = Field(default=14, alias="COOLDOWN_DAYS")
    report_limit: int = Field(default=0, alias="REPORT_LIMIT")
    daily_schedule_hour_utc: int = Field(default=1, alias="DAILY_SCHEDULE_HOUR_UTC")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def github_auth_token(self) -> str:
        return self.github_pat or self.github_token
