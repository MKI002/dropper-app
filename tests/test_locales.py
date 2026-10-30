"""The web UI translations must match English: same keys, same placeholders, same bold markers,
and plural forms that fit the language (CLDR categories, as picked by Intl.PluralRules)."""

import json
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "dropper" / "static"
LOCALES = STATIC / "locales"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# plural categories per language; "other" is the fallback the UI always needs
CATEGORIES = {
    "en": {"one", "other"}, "de": {"one", "other"}, "tr": {"one", "other"},
    "es": {"one", "many", "other"}, "fr": {"one", "many", "other"},
    "it": {"one", "many", "other"}, "pt": {"one", "many", "other"},
    "pl": {"one", "few", "many", "other"}, "ru": {"one", "few", "many", "other"},
    "ja": {"other"}, "ko": {"other"}, "zh": {"other"},
}
# forms a translation must spell out; "many" for es/fr/it/pt only covers millions and falls back to "other"
REQUIRED = {
    "en": {"one", "other"}, "de": {"one", "other"}, "tr": {"one", "other"},
    "es": {"one", "other"}, "fr": {"one", "other"}, "it": {"one", "other"}, "pt": {"one", "other"},
    "pl": {"one", "few", "many", "other"}, "ru": {"one", "few", "many", "other"},
    "ja": {"other"}, "ko": {"other"}, "zh": {"other"},
}
UI_LANGS = re.findall(r'code: "(\w+)"', (STATIC / "js" / "i18n.js").read_text(encoding="utf-8"))


def load(code: str) -> dict:
    return json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


def test_every_ui_language_has_a_locale_file():
    assert UI_LANGS[0] == "en"
    assert set(UI_LANGS) == set(CATEGORIES)
    for code in UI_LANGS:
        assert (LOCALES / f"{code}.json").is_file(), code


def test_static_keys_used_by_the_app_exist_in_english():
    source = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    used = set(re.findall(r'\bth?\("([a-z][\w.]*)"', source))
    used |= set(re.findall(r'data-i18n(?:-\w+)?="([\w.]+)"', (STATIC / "index.html").read_text(encoding="utf-8")))
    missing = sorted(key for key in used if not key.endswith(".") and key not in load("en"))
    assert not missing


@pytest.mark.parametrize("code", [c for c in CATEGORIES if c != "en"])
def test_translation_matches_english(code):
    en, other = load("en"), load(code)
    assert set(other) == set(en), f"missing {sorted(set(en) - set(other))}, extra {sorted(set(other) - set(en))}"
    for key, source in en.items():
        value = other[key]
        if isinstance(source, dict):
            assert isinstance(value, dict), key
            forms = set(value)
            assert REQUIRED[code] <= forms <= CATEGORIES[code], f"{key}: {sorted(forms)}"
            for form, text in value.items():
                assert isinstance(text, str) and text.strip(), f"{key}.{form}"
                # a singular may say "one drop" instead of "{n} drop", but nothing new may appear
                assert placeholders(text) <= placeholders(source["other"]), f"{key}.{form}"
            assert placeholders(value["other"]) == placeholders(source["other"]), key
            assert value["other"].count("**") == source["other"].count("**"), key
        else:
            assert isinstance(value, str) and value.strip(), key
            assert placeholders(value) == placeholders(source), key
            assert value.count("**") == source.count("**"), key


def test_english_plurals_are_well_formed():
    for key, value in load("en").items():
        if isinstance(value, dict):
            assert set(value) == {"one", "other"}, key
