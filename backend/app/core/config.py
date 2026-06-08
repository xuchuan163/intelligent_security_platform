from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "mysql+pymysql://root:275874@localhost:3306/intelligent_security_platform"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int = 3600
    redis_url: str = "redis://localhost:6379/0"
    memory_session_ttl_seconds: int = 1800
    cache_profile_ttl_seconds: int = 600
    cache_nl2sql_ttl_seconds: int = 600
    cache_empty_ttl_seconds: int = 60
    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"
    neo4j_database: str = "neo4j"
    dashscope_api_key: str | None = None
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    nl2sql_provider: str = "disabled"
    qwen_nl2sql_timeout_seconds: int = 10
    processing_timeout_hours: int = 72
    upload_dir: str = "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    reset_database_on_start: int = 0
    auth_mode: str = "mock"
    auth_allow_mock_headers: bool = True
    rbac_enforce: bool = True
    jwt_secret_key: str = "dev-only-change-me-use-32-byte-secret-min"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    demo_default_password: str = "Demo@12345"
    oauth_enabled: bool = False
    oauth_mock_enabled: bool = True
    oauth_client_id: str = "cscec-safety-demo"
    oauth_client_secret: str | None = None
    oauth_authorize_url: str = "https://idp.example.cscec/oauth/authorize"
    oauth_token_url: str = "https://idp.example.cscec/oauth/token"
    oauth_redirect_uri: str = "http://127.0.0.1:8011/api/v1/auth/oauth/callback"
    oauth_scopes: str = "openid profile"
    oauth_mock_code: str = "MOCK_AUTHORIZED"
    oauth_mock_user_id: str = "mock-admin"
    oauth_default_tenant_id: str = "CSCEC"
    oauth_frontend_callback_url: str = "http://127.0.0.1:5173/login"
    milvus_enabled: bool = False
    milvus_uri: str = "http://127.0.0.1:29530"
    milvus_timeout_seconds: int = 3
    milvus_accident_cases_collection: str = "accident_cases"
    milvus_safety_knowledge_collection: str = "safety_knowledge"
    milvus_embedding_dimension: int = 1024
    embedding_provider: str = "disabled"
    embedding_model: str = "text-embedding-v3"
    embedding_batch_size: int = 16
    rag_default_tenant_id: str = "CSCEC"
    rag_top_k: int = 3
    rag_score_threshold: float = 0.35
    webhook_enabled: bool = False
    webhook_wecom_bot_url: str | None = None
    webhook_timeout_seconds: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
