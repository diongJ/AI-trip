import pytest

from src.config.settings import ConfigurationError, Settings


def test_missing_deepseek_key_has_actionable_error() -> None:
    settings = Settings(_env_file=None, deepseek_api_key=None)
    with pytest.raises(ConfigurationError, match="DEEPSEEK_API_KEY"):
        settings.require_deepseek()


def test_missing_neo4j_values_do_not_expose_secret() -> None:
    settings = Settings(
        _env_file=None,
        neo4j_uri=None,
        neo4j_username=None,
        neo4j_password=None,
    )
    with pytest.raises(ConfigurationError, match="NEO4J_URI") as error:
        settings.require_neo4j()
    assert "password=" not in str(error.value).lower()

