from app.config import Settings


def test_settings_strip_ai_values() -> None:
    settings = Settings(
        ai_provider=" groq ",
        ai_model=" llama-3.2-11b-vision-preview ",
        groq_api_key=" secret-key ",
    )

    assert settings.ai_provider == "groq"
    assert settings.ai_model == "llama-3.2-11b-vision-preview"
    assert settings.groq_api_key == "secret-key"