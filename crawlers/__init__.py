"""DiversiPlant Data Crawlers Module."""
from typing import Optional
from .base import BaseCrawler
from .gbif import GBIFCrawler
from .reflora import REFLORACrawler
from .gift import GIFTCrawler
from .wcvp import WCVPCrawler
from .worldclim import WorldClimCrawler
from .treegoer import TreeGOERCrawler
from .iucn import IUCNCrawler
from .try_db import TRYCrawler
from .practitioners import PractitionersCrawler
from .gbif_occurrences import GBIFOccurrenceCrawler

CRAWLERS = {
    'gbif': GBIFCrawler,
    'gbif_occurrences': GBIFOccurrenceCrawler,
    'reflora': REFLORACrawler,
    'gift': GIFTCrawler,
    'wcvp': WCVPCrawler,
    'worldclim': WorldClimCrawler,
    'treegoer': TreeGOERCrawler,
    'iucn': IUCNCrawler,
    'try': TRYCrawler,
    'practitioners': PractitionersCrawler,
}


def get_crawler(name: str, db_url: str) -> Optional[BaseCrawler]:
    """Get a crawler instance by name."""
    crawler_class = CRAWLERS.get(name.lower())
    if crawler_class:
        return crawler_class(db_url)
    return None


def list_crawlers() -> list:
    """List all available crawler names."""
    return list(CRAWLERS.keys())


__all__ = [
    'BaseCrawler',
    'GBIFCrawler',
    'GBIFOccurrenceCrawler',
    'REFLORACrawler',
    'GIFTCrawler',
    'WCVPCrawler',
    'WorldClimCrawler',
    'TreeGOERCrawler',
    'IUCNCrawler',
    'TRYCrawler',
    'PractitionersCrawler',
    'get_crawler',
    'list_crawlers',
]
