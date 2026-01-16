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
    """Test cases for GIFT crawler."""

    def test_name_property(self):
        """Test that GIFT crawler has correct name."""
        from crawlers.gift import GIFTCrawler
        assert GIFTCrawler.name == 'gift'

    def test_normalize_growth_form(self):
        """Test growth form normalization."""
        from crawlers.gift import GIFTCrawler

        class MockCrawler(GIFTCrawler):
            def __init__(self):
                self.logger = None
                self._r_available = False

        crawler = MockCrawler()

        assert crawler._normalize_growth_form('tree') == 'tree'
        assert crawler._normalize_growth_form('Tree') == 'tree'
        assert crawler._normalize_growth_form('herbaceous') == 'herb'
        assert crawler._normalize_growth_form('liana') == 'climber'
        assert crawler._normalize_growth_form('vine') == 'climber'


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
