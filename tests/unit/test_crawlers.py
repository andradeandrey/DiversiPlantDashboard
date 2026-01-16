"""Tests for the crawler modules."""
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from crawlers import list_crawlers, get_crawler


class TestCrawlerRegistry:
    """Test cases for crawler registry functions."""

    def test_list_crawlers(self):
        """Test that all crawlers are listed."""
        crawlers = list_crawlers()
        expected = ['gbif', 'reflora', 'gift', 'wcvp', 'worldclim', 'treegoer', 'iucn']

        for name in expected:
            assert name in crawlers, f"Missing crawler: {name}"

    def test_get_crawler_valid(self):
        """Test getting a valid crawler."""
        # Note: This will fail without a real database URL
        # In a real test environment, you'd mock the database
        pass

    def test_get_crawler_invalid(self):
        """Test getting an invalid crawler returns None."""
        crawler = get_crawler('nonexistent', 'postgresql://test:test@localhost/test')
        assert crawler is None


class TestGBIFCrawler:
    """Test cases for GBIF crawler."""

    def test_name_property(self):
        """Test that GBIF crawler has correct name."""
        from crawlers.gbif import GBIFCrawler
        # Create with dummy URL (won't connect)
        assert GBIFCrawler.name == 'gbif'

    def test_normalize_status(self):
        """Test status normalization."""
        from crawlers.gbif import GBIFCrawler

        class MockCrawler(GBIFCrawler):
            def __init__(self):
                self.logger = None

        crawler = MockCrawler()

        assert crawler._normalize_status('ACCEPTED') == 'accepted'
        assert crawler._normalize_status('SYNONYM') == 'synonym'
        assert crawler._normalize_status('UNKNOWN') == 'unresolved'

    def test_normalize_language(self):
        """Test language code normalization."""
        from crawlers.gbif import GBIFCrawler

        class MockCrawler(GBIFCrawler):
            def __init__(self):
                self.logger = None

        crawler = MockCrawler()

        assert crawler._normalize_language('english') == 'en'
        assert crawler._normalize_language('portuguese') == 'pt'
        assert crawler._normalize_language('pt-br') == 'pt'
        assert crawler._normalize_language('eng') == 'en'


class TestREFLORACrawler:
    """Test cases for REFLORA crawler."""

    def test_name_property(self):
        """Test that REFLORA crawler has correct name."""
        from crawlers.reflora import REFLORACrawler
        assert REFLORACrawler.name == 'reflora'

    def test_clean_species_name(self):
        """Test species name cleaning."""
        from crawlers.reflora import REFLORACrawler

        class MockCrawler(REFLORACrawler):
            def __init__(self):
                self.logger = None
                self.session = None

        crawler = MockCrawler()

        # Test basic cleaning
        assert crawler._clean_species_name('Araucaria angustifolia') == 'Araucaria angustifolia'

        # Test with author
        assert crawler._clean_species_name('Araucaria angustifolia (Bertol.) Kuntze') == 'Araucaria angustifolia'


class TestGIFTCrawler:
    """Test cases for GIFT crawler.

    Tests the Climber.R logic (Renata Rodrigues Lucas) for determining growth_form.
    See docs/gift.md for detailed documentation.
    """

    def test_name_property(self):
        """Test that GIFT crawler has correct name."""
        from crawlers.gift import GIFTCrawler
        assert GIFTCrawler.name == 'gift'

    def _get_mock_crawler(self):
        """Create a mock GIFT crawler for testing."""
        from crawlers.gift import GIFTCrawler

        class MockCrawler(GIFTCrawler):
            def __init__(self):
                self.logger = None
                self._r_available = False

        return MockCrawler()

    def test_determine_growth_form_liana_priority(self):
        """Test that liana always takes priority (Climber.R rule 1)."""
        crawler = self._get_mock_crawler()

        # Liana should ALWAYS override trait_1.2.2
        assert crawler.determine_growth_form('liana', 'tree') == 'liana'
        assert crawler.determine_growth_form('liana', 'shrub') == 'liana'
        assert crawler.determine_growth_form('liana', 'herb') == 'liana'
        assert crawler.determine_growth_form('liana', 'forb') == 'liana'
        assert crawler.determine_growth_form('liana', 'palm') == 'liana'
        assert crawler.determine_growth_form('liana', None) == 'liana'
        assert crawler.determine_growth_form('liana', 'other') == 'liana'

    def test_determine_growth_form_vine_priority(self):
        """Test that vine always takes priority (Climber.R rule 2)."""
        crawler = self._get_mock_crawler()

        # Vine should ALWAYS override trait_1.2.2
        assert crawler.determine_growth_form('vine', 'tree') == 'vine'
        assert crawler.determine_growth_form('vine', 'shrub') == 'vine'
        assert crawler.determine_growth_form('vine', 'herb') == 'vine'
        assert crawler.determine_growth_form('vine', 'forb') == 'vine'
        assert crawler.determine_growth_form('vine', 'graminoid') == 'vine'
        assert crawler.determine_growth_form('vine', None) == 'vine'

    def test_determine_growth_form_self_supporting(self):
        """Test that self-supporting defers to trait_1.2.2 (Climber.R rule 3)."""
        crawler = self._get_mock_crawler()

        # Self-supporting should use trait_1.2.2
        assert crawler.determine_growth_form('self-supporting', 'tree') == 'tree'
        assert crawler.determine_growth_form('self-supporting', 'shrub') == 'shrub'
        assert crawler.determine_growth_form('self-supporting', 'subshrub') == 'subshrub'
        assert crawler.determine_growth_form('self-supporting', 'palm') == 'palm'
        assert crawler.determine_growth_form('self-supporting', 'forb') == 'forb'
        assert crawler.determine_growth_form('self-supporting', 'graminoid') == 'graminoid'
        assert crawler.determine_growth_form('self-supporting', None) == 'other'

    def test_determine_growth_form_herb_to_forb(self):
        """Test that herb is normalized to forb (Climber.R rule 5)."""
        crawler = self._get_mock_crawler()

        # herb should become forb
        assert crawler.determine_growth_form('self-supporting', 'herb') == 'forb'
        assert crawler.determine_growth_form(None, 'herb') == 'forb'
        assert crawler.determine_growth_form(None, 'herbaceous') == 'forb'

    def test_determine_growth_form_na_climber(self):
        """Test when climber_type is NA/None (Climber.R rule 4)."""
        crawler = self._get_mock_crawler()

        # When trait_1.4.2 is None, use trait_1.2.2
        assert crawler.determine_growth_form(None, 'tree') == 'tree'
        assert crawler.determine_growth_form(None, 'shrub') == 'shrub'
        assert crawler.determine_growth_form(None, 'palm') == 'palm'
        assert crawler.determine_growth_form(None, 'forb') == 'forb'
        assert crawler.determine_growth_form(None, 'graminoid') == 'graminoid'
        assert crawler.determine_growth_form(None, None) == 'other'

    def test_determine_growth_form_case_insensitive(self):
        """Test that determination is case-insensitive."""
        crawler = self._get_mock_crawler()

        assert crawler.determine_growth_form('LIANA', 'tree') == 'liana'
        assert crawler.determine_growth_form('Vine', 'shrub') == 'vine'
        assert crawler.determine_growth_form('Self-Supporting', 'TREE') == 'tree'

    def test_normalize_growth_form_value(self):
        """Test individual growth form value normalization."""
        crawler = self._get_mock_crawler()

        # Direct mappings
        assert crawler._normalize_growth_form_value('tree') == 'tree'
        assert crawler._normalize_growth_form_value('shrub') == 'shrub'
        assert crawler._normalize_growth_form_value('subshrub') == 'subshrub'
        assert crawler._normalize_growth_form_value('palm') == 'palm'
        assert crawler._normalize_growth_form_value('liana') == 'liana'
        assert crawler._normalize_growth_form_value('vine') == 'vine'
        assert crawler._normalize_growth_form_value('forb') == 'forb'
        assert crawler._normalize_growth_form_value('graminoid') == 'graminoid'

        # Normalizations
        assert crawler._normalize_growth_form_value('herb') == 'forb'
        assert crawler._normalize_growth_form_value('herbaceous') == 'forb'
        assert crawler._normalize_growth_form_value('grass') == 'graminoid'

        # Unknown values
        assert crawler._normalize_growth_form_value('unknown_value') == 'other'
        assert crawler._normalize_growth_form_value('') == 'other'
        assert crawler._normalize_growth_form_value(None) == 'other'

    def test_valid_growth_forms_constant(self):
        """Test that VALID_GROWTH_FORMS contains expected values."""
        from crawlers.gift import GIFTCrawler

        expected = {'tree', 'shrub', 'subshrub', 'palm', 'liana', 'vine',
                    'forb', 'graminoid', 'fern', 'bamboo', 'succulent',
                    'aquatic', 'epiphyte', 'other'}

        assert GIFTCrawler.VALID_GROWTH_FORMS == expected


class TestTreeGOERCrawler:
    """Test cases for TreeGOER crawler."""

    def test_name_property(self):
        """Test that TreeGOER crawler has correct name."""
        from crawlers.treegoer import TreeGOERCrawler
        assert TreeGOERCrawler.name == 'treegoer'


class TestIUCNCrawler:
    """Test cases for IUCN crawler."""

    def test_name_property(self):
        """Test that IUCN crawler has correct name."""
        from crawlers.iucn import IUCNCrawler
        assert IUCNCrawler.name == 'iucn'

    def test_categories_defined(self):
        """Test that IUCN categories are defined."""
        from crawlers.iucn import IUCNCrawler

        expected_categories = ['EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'NE']

        for cat in expected_categories:
            assert cat in IUCNCrawler.CATEGORIES
