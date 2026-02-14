from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    app_name: str = 'Cubie NAS'
    app_host: str = '0.0.0.0'
    app_port: int = 8443
    database_url: str = 'sqlite:////var/lib/cubie-nas/cubie_nas.db'
    jwt_secret: str = 'change-me'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 120
    nas_root: str = '/srv/nas'
    tls_cert_file: str = '/etc/cubie-nas/cert.pem'
    tls_key_file: str = '/etc/cubie-nas/key.pem'
    log_level: str = 'info'


settings = Settings()
