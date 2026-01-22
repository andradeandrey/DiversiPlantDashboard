"""TraitBank (Encyclopedia of Life) crawler for trait data.

Data source: EOL TraitBank
API: https://eol.org/service/cypher (requires JWT authentication)
Alternative: Kaggle dataset export

Additional source: AnAge (Animal Ageing and Longevity Database)
URL: https://genomics.senescence.info/species/

This crawler fetches raw trait data and checks for longevity/lifespan records.
"""
import os
import json
import requests
import zipfile
import csv
import sys
from typing import Generator, Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Increase CSV field size limit for large TraitBank fields
csv.field_size_limit(sys.maxsize)


class TraitBankCrawler:
    """
    Crawler for EOL TraitBank data.

    This crawler downloads raw trait data and saves it as JSON.
    It does NOT integrate with the database - only fetches raw data.

    Sources:
        - EOL Cypher API (requires power user JWT token)
        - Kaggle dataset: https://www.kaggle.com/datasets/mylesoneill/eol-trait-bank
    """

    name = 'traitbank'

    # EOL API endpoint
    API_URL = 'https://eol.org/service/cypher'

    # Known predicate URIs for longevity/lifespan traits
    LONGEVITY_PREDICATES = [
        'http://purl.obolibrary.org/obo/VT_0001661',  # life span
        'http://eol.org/schema/terms/lifeSpan',
        'http://purl.obolibrary.org/obo/PATO_0000050',  # life span (PATO)
        'http://rs.tdwg.org/dwc/terms/longevity',
        'longevity',
        'life span',
        'lifespan',
        'maximum longevity',
        'maximum lifespan',
    ]

    # Output directory for raw data
    OUTPUT_DIR = 'data/traitbank_raw'

    def __init__(self, jwt_token: Optional[str] = None):
        """
        Initialize the TraitBank crawler.

        Args:
            jwt_token: EOL API JWT token (optional, for API access)
        """
        self.jwt_token = jwt_token or os.getenv('EOL_CYPHER_KEY')
        self.session = requests.Session()

        if self.jwt_token:
            self.session.headers['Authorization'] = f'JWT {self.jwt_token}'

        # Create output directory
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

        self.stats = {
            'total_traits': 0,
            'longevity_records': 0,
            'unique_species': set(),
            'predicates_found': set(),
        }

    def query_api(self, cypher_query: str, format: str = 'cypher') -> Dict:
        """
        Execute a Cypher query against the EOL TraitBank API.

        Args:
            cypher_query: Neo4j Cypher query string
            format: Response format ('cypher' for JSON, 'csv' for CSV)

        Returns:
            API response as dict
        """
        if not self.jwt_token:
            raise ValueError(
                "JWT token required. Set EOL_CYPHER_KEY env var or pass jwt_token. "
                "To get a token: 1) Create account at eol.org, "
                "2) Email hammockj@si.edu to become power user, "
                "3) Get token at https://eol.org/services/authenticate"
            )

        params = {
            'query': cypher_query,
            'format': format,
        }

        response = self.session.get(self.API_URL, params=params, timeout=120)
        response.raise_for_status()

        if format == 'cypher':
            return response.json()
        return {'csv': response.text}

    def fetch_all_predicates(self) -> List[Dict]:
        """
        Fetch all measurement predicates from TraitBank.

        Returns:
            List of predicate dicts with name and URI
        """
        query = """
        MATCH (t:Term {type:"measurement"})
        RETURN DISTINCT t.name as name, t.uri as uri
        LIMIT 1000;
        """

        result = self.query_api(query)
        predicates = []

        if 'data' in result:
            for row in result['data']:
                predicates.append({
                    'name': row[0],
                    'uri': row[1]
                })

        return predicates

    def find_longevity_predicates(self) -> List[Dict]:
        """
        Find predicates related to longevity/lifespan.

        Returns:
            List of matching predicate dicts
        """
        all_predicates = self.fetch_all_predicates()

        longevity_matches = []
        search_terms = ['life', 'span', 'longevity', 'age', 'duration']

        for pred in all_predicates:
            name = (pred.get('name') or '').lower()
            uri = (pred.get('uri') or '').lower()

            if any(term in name or term in uri for term in search_terms):
                longevity_matches.append(pred)

        return longevity_matches

    def fetch_longevity_traits(self, limit: int = 10000) -> Generator[Dict, None, None]:
        """
        Fetch trait records related to longevity/lifespan.

        Args:
            limit: Maximum records to fetch

        Yields:
            Raw trait records
        """
        # Query for traits with longevity-related predicates
        query = f"""
        MATCH (t:Trait)<-[:trait]-(p:Page),
              (t)-[:predicate]->(pred:Term)
        WHERE pred.name =~ '(?i).*(life.*span|longevity|maximum.*age).*'
           OR pred.uri IN {self.LONGEVITY_PREDICATES}
        OPTIONAL MATCH (t)-[:units_term]->(units:Term)
        OPTIONAL MATCH (t)-[:supplier]->(r:Resource)
        RETURN p.page_id as page_id,
               p.canonical as species_name,
               pred.name as predicate_name,
               pred.uri as predicate_uri,
               t.measurement as value,
               t.literal as literal_value,
               units.name as units,
               r.resource_id as source_id
        LIMIT {limit};
        """

        result = self.query_api(query)

        if 'data' in result:
            columns = result.get('columns', [
                'page_id', 'species_name', 'predicate_name',
                'predicate_uri', 'value', 'literal_value', 'units', 'source_id'
            ])

            for row in result['data']:
                record = dict(zip(columns, row))
                yield record

    def load_from_csv(self, csv_path: str) -> Generator[Dict, None, None]:
        """
        Load trait data from Kaggle CSV export.

        Args:
            csv_path: Path to traits.csv file

        Yields:
            Raw trait records
        """
        print(f"Loading traits from: {csv_path}")

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                yield row

    def load_from_kaggle_zip(self, zip_path: str) -> Dict[str, Any]:
        """
        Load all data from Kaggle ZIP export.

        Args:
            zip_path: Path to downloaded Kaggle ZIP file

        Returns:
            Dict with loaded data from each file
        """
        data = {
            'pages': [],
            'traits': [],
            'terms': [],
            'metadata': [],
        }

        print(f"Extracting Kaggle ZIP: {zip_path}")

        with zipfile.ZipFile(zip_path, 'r') as z:
            for filename in z.namelist():
                basename = os.path.basename(filename)

                if basename == 'traits.csv':
                    print("Loading traits.csv...")
                    with z.open(filename) as f:
                        import io
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
                        for row in reader:
                            data['traits'].append(row)

                elif basename == 'terms.csv':
                    print("Loading terms.csv...")
                    with z.open(filename) as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
                        for row in reader:
                            data['terms'].append(row)

                elif basename == 'pages.csv':
                    print("Loading pages.csv (sample)...")
                    with z.open(filename) as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
                        # Only load first 1000 for inspection
                        for i, row in enumerate(reader):
                            if i >= 1000:
                                break
                            data['pages'].append(row)

        return data

    def analyze_traits_for_longevity(self, traits_path: str) -> Dict[str, Any]:
        """
        Analyze a traits CSV file to find longevity-related records.

        Args:
            traits_path: Path to traits.csv

        Returns:
            Analysis results with counts and samples
        """
        results = {
            'total_records': 0,
            'longevity_records': 0,
            'longevity_samples': [],
            'predicate_counts': {},
            'unique_species_with_longevity': set(),
        }

        longevity_terms = [
            'life span', 'lifespan', 'life-span',
            'longevity', 'maximum age', 'max age',
            'life expectancy', 'lifetime', 'life time',
            'years lived', 'age at death', 'lifespan_years',
        ]

        print(f"Analyzing traits from: {traits_path}")

        with open(traits_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)

            for row in reader:
                results['total_records'] += 1

                if results['total_records'] % 500000 == 0:
                    print(f"  Processed {results['total_records']:,} records...")

                # Check predicate/trait name for longevity terms
                predicate = (row.get('predicate', '') or '').lower()
                predicate_uri = (row.get('predicate_uri', '') or '').lower()

                # Track all predicates
                pred_key = row.get('predicate', 'unknown')
                results['predicate_counts'][pred_key] = \
                    results['predicate_counts'].get(pred_key, 0) + 1

                # Check if this is a longevity record
                is_longevity = any(
                    term in predicate or term in predicate_uri
                    for term in longevity_terms
                )

                if is_longevity:
                    results['longevity_records'] += 1

                    species = row.get('page_id') or row.get('scientific_name', '')
                    if species:
                        results['unique_species_with_longevity'].add(species)

                    # Keep samples
                    if len(results['longevity_samples']) < 20:
                        results['longevity_samples'].append(row)

        # Convert set to count
        results['unique_species_count'] = len(results['unique_species_with_longevity'])
        results['unique_species_with_longevity'] = list(
            results['unique_species_with_longevity']
        )[:100]  # Keep only first 100 for display

        return results

    def save_raw_json(self, data: Any, filename: str) -> str:
        """
        Save raw data as JSON file.

        Args:
            data: Data to save
            filename: Output filename (without path)

        Returns:
            Full path to saved file
        """
        filepath = os.path.join(self.OUTPUT_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        print(f"Saved: {filepath}")
        return filepath

    def run_api_mode(self, limit: int = 10000) -> Dict[str, Any]:
        """
        Run crawler using EOL API.

        Args:
            limit: Maximum records to fetch

        Returns:
            Results summary
        """
        print("="*60)
        print("TraitBank Crawler - API Mode")
        print("="*60)

        # 1. Find longevity predicates
        print("\n1. Finding longevity-related predicates...")
        try:
            predicates = self.find_longevity_predicates()
            print(f"   Found {len(predicates)} predicates")

            self.save_raw_json(predicates, 'longevity_predicates.json')
        except Exception as e:
            print(f"   Error: {e}")
            predicates = []

        # 2. Fetch longevity traits
        print(f"\n2. Fetching longevity trait records (limit={limit})...")
        try:
            traits = list(self.fetch_longevity_traits(limit=limit))
            print(f"   Found {len(traits)} records")

            self.save_raw_json(traits, 'longevity_traits_raw.json')
        except Exception as e:
            print(f"   Error: {e}")
            traits = []

        # 3. Summary
        results = {
            'mode': 'api',
            'timestamp': datetime.now().isoformat(),
            'predicates_found': len(predicates),
            'longevity_records': len(traits),
            'unique_species': len(set(t.get('species_name') for t in traits if t.get('species_name'))),
            'predicates': predicates,
            'sample_records': traits[:10],
        }

        self.save_raw_json(results, 'traitbank_summary.json')

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Predicates found: {results['predicates_found']}")
        print(f"Longevity records: {results['longevity_records']}")
        print(f"Unique species: {results['unique_species']}")
        print(f"Output directory: {self.OUTPUT_DIR}")

        return results

    def run_csv_mode(self, csv_path: str) -> Dict[str, Any]:
        """
        Run crawler using local CSV file (from Kaggle).

        Args:
            csv_path: Path to traits.csv

        Returns:
            Results summary
        """
        print("="*60)
        print("TraitBank Crawler - CSV Mode")
        print("="*60)

        if not os.path.exists(csv_path):
            print(f"ERROR: File not found: {csv_path}")
            print("\nTo get the data:")
            print("1. Download from: https://www.kaggle.com/datasets/mylesoneill/eol-trait-bank")
            print("2. Extract traits.csv from the ZIP")
            print(f"3. Run: python -c \"from crawlers.traitbank import TraitBankCrawler; TraitBankCrawler().run_csv_mode('{csv_path}')\"")
            return {}

        # Analyze the CSV
        results = self.analyze_traits_for_longevity(csv_path)
        results['mode'] = 'csv'
        results['timestamp'] = datetime.now().isoformat()
        results['source_file'] = csv_path

        # Save results
        self.save_raw_json(results, 'traitbank_longevity_analysis.json')

        # Save samples
        if results['longevity_samples']:
            self.save_raw_json(
                results['longevity_samples'],
                'longevity_samples.json'
            )

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total trait records: {results['total_records']:,}")
        print(f"Longevity records: {results['longevity_records']:,}")
        print(f"Unique species with longevity: {results['unique_species_count']:,}")
        print(f"Output directory: {self.OUTPUT_DIR}")

        # Show top predicates
        print("\nTop 20 predicates:")
        sorted_preds = sorted(
            results['predicate_counts'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        for pred, count in sorted_preds:
            print(f"  {pred}: {count:,}")

        return results

    def download_kaggle_dataset(self) -> Optional[str]:
        """
        Download TraitBank dataset from Kaggle.

        Requires kaggle CLI to be configured.

        Returns:
            Path to downloaded ZIP file, or None if failed
        """
        import subprocess

        output_path = os.path.join(self.OUTPUT_DIR, 'eol-trait-bank.zip')

        if os.path.exists(output_path):
            print(f"Dataset already exists: {output_path}")
            return output_path

        print("Downloading from Kaggle...")
        print("(Requires kaggle CLI: pip install kaggle)")

        try:
            subprocess.run([
                'kaggle', 'datasets', 'download',
                '-d', 'mylesoneill/eol-trait-bank',
                '-p', self.OUTPUT_DIR,
            ], check=True)

            return output_path
        except Exception as e:
            print(f"Download failed: {e}")
            print("\nManual download:")
            print("1. Go to: https://www.kaggle.com/datasets/mylesoneill/eol-trait-bank")
            print("2. Download the ZIP file")
            print(f"3. Place it at: {output_path}")
            return None

    def download_anage(self) -> Optional[str]:
        """
        Download AnAge database (Animal Ageing and Longevity Database).

        This is the best source for longevity data with ~4,600 species.

        Returns:
            Path to extracted data file
        """
        url = 'https://genomics.senescence.info/species/dataset.zip'
        zip_path = os.path.join(self.OUTPUT_DIR, 'anage_dataset.zip')
        data_path = os.path.join(self.OUTPUT_DIR, 'anage_data.txt')

        if os.path.exists(data_path):
            print(f"AnAge data already exists: {data_path}")
            return data_path

        print("Downloading AnAge database...")
        print(f"URL: {url}")

        try:
            response = self.session.get(url, timeout=60, stream=True, verify=True)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"Downloaded: {zip_path}")

            # Extract
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(self.OUTPUT_DIR)

            print(f"Extracted to: {self.OUTPUT_DIR}")
            return data_path

        except Exception as e:
            print(f"Download failed: {e}")
            return None

    def analyze_anage(self, data_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze AnAge data for longevity records.

        Args:
            data_path: Path to anage_data.txt (downloads if not provided)

        Returns:
            Analysis results
        """
        if not data_path:
            data_path = self.download_anage()

        if not data_path or not os.path.exists(data_path):
            return {'error': 'Failed to get AnAge data'}

        print(f"\nAnalyzing AnAge data: {data_path}")
        print("=" * 60)

        records = []
        longevity_records = []

        with open(data_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            for row in reader:
                records.append(row)

                max_longevity = row.get('Maximum longevity (yrs)', '')
                if max_longevity and max_longevity.strip():
                    try:
                        years = float(max_longevity)
                        if years > 0:
                            longevity_records.append({
                                'species': f"{row.get('Genus', '')} {row.get('Species', '')}",
                                'common_name': row.get('Common name', ''),
                                'class': row.get('Class', ''),
                                'order': row.get('Order', ''),
                                'family': row.get('Family', ''),
                                'max_longevity_years': years,
                                'source': row.get('Source', ''),
                                'data_quality': row.get('Data quality', ''),
                            })
                    except ValueError:
                        pass

        # Statistics by class
        class_counts = {}
        for rec in longevity_records:
            cls = rec['class']
            class_counts[cls] = class_counts.get(cls, 0) + 1

        results = {
            'source': 'AnAge',
            'url': 'https://genomics.senescence.info/species/',
            'total_records': len(records),
            'longevity_records': len(longevity_records),
            'coverage_percent': round(len(longevity_records) / len(records) * 100, 1),
            'by_class': class_counts,
            'sample_records': longevity_records[:20],
        }

        # Save results
        self.save_raw_json(results, 'anage_analysis.json')
        self.save_raw_json(longevity_records, 'anage_longevity_all.json')

        print(f"Total records: {results['total_records']:,}")
        print(f"Longevity records: {results['longevity_records']:,}")
        print(f"Coverage: {results['coverage_percent']}%")
        print(f"\nBy taxonomic class:")
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {cls}: {count:,}")

        return results

    def run_anage_mode(self) -> Dict[str, Any]:
        """
        Run crawler using AnAge database.

        Returns:
            Results summary
        """
        print("=" * 60)
        print("TraitBank Crawler - AnAge Mode")
        print("=" * 60)
        print("\nAnAge is the best source for animal longevity data.")
        print("Contains ~4,600 species with 89% having longevity data.")

        return self.analyze_anage()


def main():
    """Main entry point for TraitBank crawler."""
    import argparse

    parser = argparse.ArgumentParser(
        description='TraitBank (EOL) Crawler - Download raw trait data'
    )
    parser.add_argument(
        '--mode',
        choices=['api', 'csv', 'kaggle', 'anage'],
        default='anage',
        help='Data source mode (default: anage)'
    )
    parser.add_argument(
        '--csv-path',
        default='data/traitbank_raw/traits.csv',
        help='Path to traits.csv (for csv mode)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10000,
        help='Maximum records to fetch (for api mode)'
    )
    parser.add_argument(
        '--token',
        help='EOL API JWT token (for api mode)'
    )

    args = parser.parse_args()

    crawler = TraitBankCrawler(jwt_token=args.token)

    if args.mode == 'api':
        crawler.run_api_mode(limit=args.limit)
    elif args.mode == 'csv':
        crawler.run_csv_mode(args.csv_path)
    elif args.mode == 'kaggle':
        zip_path = crawler.download_kaggle_dataset()
        if zip_path:
            print(f"\nDownloaded: {zip_path}")
            print("Extract and run with --mode csv")
    elif args.mode == 'anage':
        crawler.run_anage_mode()


if __name__ == '__main__':
    main()
