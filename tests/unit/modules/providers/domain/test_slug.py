import pytest

from app.modules.providers.domain.slug import generate_provider_slug


def test_generate_provider_slug_normalizes_display_name() -> None:
    slug = generate_provider_slug("  Barbearia João!  ", suffix="a1b2c3d4")

    assert slug == "barbearia-joao-a1b2c3d4"


def test_generate_provider_slug_falls_back_when_display_name_has_no_useful_chars() -> None:
    slug = generate_provider_slug("!!!", suffix="a1b2c3d4")

    assert slug == "provider-a1b2c3d4"


def test_generate_provider_slug_truncates_base_to_fit_limit() -> None:
    display_name = "A" * 200

    slug = generate_provider_slug(display_name, suffix="a1b2c3d4")

    assert len(slug) <= 80
    assert slug.endswith("-a1b2c3d4")
    assert slug.startswith("a" * 71)


def test_generate_provider_slug_rejects_suffix_that_is_too_long() -> None:
    with pytest.raises(ValueError):
        generate_provider_slug("Provider Test", suffix="x" * 80)
