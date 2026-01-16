"""Translation module for DiversiPlant internationalization."""
import json
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any, List

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'pt']
DEFAULT_LANGUAGE = 'en'


class Translator:
    """
    Translation class for DiversiPlant.

    Loads translation files and provides lookup functionality.
    Supports nested keys like 'nav.location'.
    """

    def __init__(self, locales_dir: Path = None):
        """
        Initialize the translator.

        Args:
            locales_dir: Directory containing locale folders
        """
        if locales_dir is None:
            locales_dir = Path(__file__).parent / 'locales'

        self.locales_dir = locales_dir
        self._cache: Dict[str, Dict] = {}
        self._current_language = DEFAULT_LANGUAGE

        # Load all translations
        self._load_all()

    def _load_all(self):
        """Load all translation files into cache."""
        for lang in SUPPORTED_LANGUAGES:
            self._load_language(lang)

    def _load_language(self, lang: str):
        """Load translations for a specific language."""
        lang_dir = self.locales_dir / lang

        if not lang_dir.exists():
            return

        translations = {}

        # Load messages.json
        messages_file = lang_dir / 'messages.json'
        if messages_file.exists():
            try:
                with open(messages_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading {messages_file}: {e}")

        self._cache[lang] = translations

    def set_language(self, lang: str):
        """
        Set the current language.

        Args:
            lang: Language code ('en' or 'pt')
        """
        if lang in SUPPORTED_LANGUAGES:
            self._current_language = lang
        else:
            self._current_language = DEFAULT_LANGUAGE

    def get_language(self) -> str:
        """Get the current language code."""
        return self._current_language

    @lru_cache(maxsize=1000)
    def translate(self, key: str, lang: str = None, **kwargs) -> str:
        """
        Translate a key.

        Args:
            key: Translation key (e.g., 'nav.location')
            lang: Language code (uses current language if not specified)
            **kwargs: Variables to interpolate in the translation

        Returns:
            Translated string, or the key if not found
        """
        if lang is None:
            lang = self._current_language

        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE

        translations = self._cache.get(lang, {})

        # Navigate nested keys
        keys = key.split('.')
        value = translations

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None

            if value is None:
                # Fallback to English
                if lang != DEFAULT_LANGUAGE:
                    return self.translate(key, DEFAULT_LANGUAGE, **kwargs)
                return key

        # Handle string value
        if isinstance(value, str):
            # Interpolate variables
            if kwargs:
                try:
                    value = value.format(**kwargs)
                except KeyError:
                    pass
            return value

        return key

    def t(self, key: str, lang: str = None, **kwargs) -> str:
        """Shorthand for translate()."""
        return self.translate(key, lang, **kwargs)

    def get_all_keys(self, lang: str = None) -> List[str]:
        """Get all translation keys for a language."""
        if lang is None:
            lang = self._current_language

        translations = self._cache.get(lang, {})

        def flatten_keys(d: Dict, prefix: str = '') -> List[str]:
            keys = []
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.extend(flatten_keys(v, full_key))
                else:
                    keys.append(full_key)
            return keys

        return flatten_keys(translations)

    def get_missing_translations(self, target_lang: str) -> List[str]:
        """
        Find keys that exist in English but not in target language.

        Args:
            target_lang: Language to check

        Returns:
            List of missing translation keys
        """
        en_keys = set(self.get_all_keys('en'))
        target_keys = set(self.get_all_keys(target_lang))

        return sorted(en_keys - target_keys)

    def reload(self):
        """Reload all translation files."""
        self.translate.cache_clear()
        self._cache.clear()
        self._load_all()


# Global translator instance
_translator: Optional[Translator] = None


def get_translator() -> Translator:
    """Get or create the global translator instance."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def t(key: str, lang: str = None, **kwargs) -> str:
    """
    Translate a key using the global translator.

    Args:
        key: Translation key (e.g., 'nav.location')
        lang: Language code (uses current language if not specified)
        **kwargs: Variables to interpolate

    Returns:
        Translated string

    Example:
        >>> t('nav.location', 'pt')
        'Localização'
    """
    return get_translator().t(key, lang, **kwargs)


def set_language(lang: str):
    """Set the global language."""
    get_translator().set_language(lang)
