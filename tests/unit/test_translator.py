"""Tests for the i18n translator module."""
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from i18n.translator import Translator, t, get_translator, set_language


class TestTranslator:
    """Test cases for Translator class."""

    def test_translator_initialization(self):
        """Test that translator initializes correctly."""
        translator = Translator()
        assert translator is not None
        assert translator._current_language == 'en'

    def test_translate_english(self):
        """Test English translation."""
        translator = Translator()
        result = translator.t('nav.location', 'en')
        assert result == 'Location'

    def test_translate_portuguese(self):
        """Test Portuguese translation."""
        translator = Translator()
        result = translator.t('nav.location', 'pt')
        assert result == 'Localização'

    def test_missing_key_returns_key(self):
        """Test that missing key returns the key itself."""
        translator = Translator()
        result = translator.t('nonexistent.key', 'en')
        assert result == 'nonexistent.key'

    def test_set_language(self):
        """Test setting current language."""
        translator = Translator()
        translator.set_language('pt')
        assert translator.get_language() == 'pt'

    def test_invalid_language_fallback(self):
        """Test that invalid language falls back to default."""
        translator = Translator()
        translator.set_language('invalid')
        assert translator.get_language() == 'en'

    def test_nested_keys(self):
        """Test translation of nested keys."""
        translator = Translator()
        result = translator.t('growth_forms.tree', 'en')
        assert result == 'Tree'

        result = translator.t('growth_forms.tree', 'pt')
        assert result == 'Árvore'

    def test_global_translator(self):
        """Test global translator function."""
        result = t('common.loading', 'en')
        assert result == 'Loading...'

        result = t('common.loading', 'pt')
        assert result == 'Carregando...'

    def test_get_translator_singleton(self):
        """Test that get_translator returns same instance."""
        translator1 = get_translator()
        translator2 = get_translator()
        assert translator1 is translator2

    def test_get_all_keys(self):
        """Test getting all translation keys."""
        translator = Translator()
        keys = translator.get_all_keys('en')
        assert 'nav.location' in keys
        assert 'growth_forms.tree' in keys
        assert len(keys) > 0


class TestTranslatorGrowthForms:
    """Test cases for growth form translations."""

    def test_all_growth_forms_en(self):
        """Test all growth form translations in English."""
        translator = Translator()
        growth_forms = ['tree', 'shrub', 'herb', 'climber', 'palm', 'bamboo']

        for form in growth_forms:
            result = translator.t(f'growth_forms.{form}', 'en')
            assert result != f'growth_forms.{form}', f"Missing translation for {form}"

    def test_all_growth_forms_pt(self):
        """Test all growth form translations in Portuguese."""
        translator = Translator()
        growth_forms = ['tree', 'shrub', 'herb', 'climber', 'palm', 'bamboo']

        for form in growth_forms:
            result = translator.t(f'growth_forms.{form}', 'pt')
            assert result != f'growth_forms.{form}', f"Missing translation for {form}"


class TestTranslatorIUCN:
    """Test cases for IUCN category translations."""

    def test_iucn_categories_en(self):
        """Test IUCN category translations in English."""
        translator = Translator()
        categories = ['EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'NE']

        for cat in categories:
            result = translator.t(f'iucn.{cat}', 'en')
            assert result != f'iucn.{cat}', f"Missing translation for {cat}"

    def test_iucn_categories_pt(self):
        """Test IUCN category translations in Portuguese."""
        translator = Translator()
        categories = ['EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'NE']

        for cat in categories:
            result = translator.t(f'iucn.{cat}', 'pt')
            assert result != f'iucn.{cat}', f"Missing translation for {cat}"
