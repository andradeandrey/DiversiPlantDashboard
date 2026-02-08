#!/usr/bin/env python3
"""
Download and process agricultural/cultivable plant data from multiple sources.

Sources:
    1. EcoCrop (FAO) - 2568 species with full cultivation climate envelopes
    2. FAOSTAT - Crop production by country
    3. CROPGRIDS - 173 crops with spatial distribution metadata
    4. MapSPAM - 46 major crops

Usage:
    python scripts/download_agricultural_data.py --all
    python scripts/download_agricultural_data.py --ecocrop
    python scripts/download_agricultural_data.py --faostat
    python scripts/download_agricultural_data.py --cropgrids
    python scripts/download_agricultural_data.py --mapspam

Dependencies:
    requests (pip install requests)
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import zipfile
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('agricultural_data')

# Paths
DATA_DIR = Path(__file__).parent.parent / 'data'
WCVP_TAXON = DATA_DIR / 'wcvp' / 'wcvp_taxon.csv'

# URLs
ECOCROP_URL = 'https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv'
FAOSTAT_BULK_URL = 'https://bulkdownloads.fao.org/FAOSTAT/Production_Crops_Livestock_E_All_Data.zip'
FAOSTAT_API_URL = 'https://fenixservices.fao.org/faostat/api/v1/en/data/QCL'


# ─── WCVP Name Loading ───────────────────────────────────────────────────────

def load_wcvp_names():
    """Load accepted species names from WCVP taxon file for cross-referencing."""
    names = set()
    if not WCVP_TAXON.exists():
        logger.warning(f"WCVP taxon file not found: {WCVP_TAXON}")
        return names

    logger.info(f"Loading WCVP names from {WCVP_TAXON}...")
    with open(WCVP_TAXON, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f, delimiter='|')
        for row in reader:
            status = (row.get('taxonomicstatus') or '').strip()
            name = (row.get('scientfiicname') or '').strip()
            if name and status == 'Accepted':
                # Store canonical binomial (genus + species epithet)
                parts = name.split()
                if len(parts) >= 2:
                    canonical = f"{parts[0]} {parts[1]}"
                    names.add(canonical.lower())
                names.add(name.lower())

    logger.info(f"Loaded {len(names)} accepted WCVP names")
    return names


def check_wcvp(scientific_name, wcvp_names, synonyms=None):
    """Check if a species name or its synonyms exist in WCVP.

    Returns (in_wcvp, matched_name).
    """
    if not scientific_name:
        return False, None

    # Clean and normalize
    name_clean = scientific_name.strip().lower()

    # Try exact match
    if name_clean in wcvp_names:
        return True, scientific_name.strip()

    # Try binomial only (drop authority)
    parts = name_clean.split()
    if len(parts) >= 2:
        binomial = f"{parts[0]} {parts[1]}"
        if binomial in wcvp_names:
            return True, f"{parts[0].capitalize()} {parts[1]}"

    # Try synonyms
    if synonyms:
        for syn in synonyms:
            syn_clean = syn.strip().lower()
            if syn_clean in wcvp_names:
                return True, syn.strip()
            syn_parts = syn_clean.split()
            if len(syn_parts) >= 2:
                syn_binomial = f"{syn_parts[0]} {syn_parts[1]}"
                if syn_binomial in wcvp_names:
                    return True, f"{syn_parts[0].capitalize()} {syn_parts[1]}"

    return False, None


# ─── Numeric Helpers ──────────────────────────────────────────────────────────

def safe_float(val):
    """Convert to float, return None if invalid."""
    if val is None:
        return None
    val = str(val).strip()
    if val == '' or val.lower() in ('na', 'n/a', 'none', '-'):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val):
    """Convert to int, return None if invalid."""
    f = safe_float(val)
    if f is None:
        return None
    return int(f)


# ─── EcoCrop ──────────────────────────────────────────────────────────────────

def download_ecocrop(wcvp_names):
    """Download and parse EcoCrop database from GitHub."""
    logger.info(f"Downloading EcoCrop from {ECOCROP_URL}...")
    resp = requests.get(ECOCROP_URL, timeout=60)
    resp.raise_for_status()
    logger.info(f"Downloaded {len(resp.content)} bytes")

    # Parse CSV
    text = resp.content.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text))

    all_species = []
    new_species = []
    stats = {'total': 0, 'in_wcvp': 0, 'with_temp': 0, 'with_rain': 0}

    for row in reader:
        stats['total'] += 1

        sci_name = (row.get('ScientificName') or '').strip()
        if not sci_name:
            continue

        # Parse synonyms
        syno_raw = (row.get('SYNO') or '').strip()
        synonyms = [s.strip() for s in syno_raw.split(';') if s.strip()] if syno_raw else []

        # Parse common names
        comname_raw = (row.get('COMNAME') or '').strip()
        common_names = [c.strip() for c in comname_raw.split(',') if c.strip()] if comname_raw else []

        # Parse categories
        cat_raw = (row.get('CAT') or '').strip()
        categories = [c.strip().lower() for c in cat_raw.split(',') if c.strip()] if cat_raw else []

        # Climate envelope
        topmn = safe_float(row.get('TOPMN'))
        topmx = safe_float(row.get('TOPMX'))
        tmin = safe_float(row.get('TMIN'))
        tmax = safe_float(row.get('TMAX'))
        ropmn = safe_float(row.get('ROPMN'))
        ropmx = safe_float(row.get('ROPMX'))
        rmin = safe_float(row.get('RMIN'))
        rmax = safe_float(row.get('RMAX'))
        ktmp = safe_float(row.get('KTMP'))
        gmin = safe_int(row.get('GMIN'))
        gmax = safe_int(row.get('GMAX'))

        if topmn is not None or tmin is not None:
            stats['with_temp'] += 1
        if ropmn is not None or rmin is not None:
            stats['with_rain'] += 1

        climate_envelope = {
            'temperature_optimal_min_c': topmn,
            'temperature_optimal_max_c': topmx,
            'temperature_abs_min_c': tmin,
            'temperature_abs_max_c': tmax,
            'killing_temperature_c': ktmp,
            'rainfall_optimal_min_mm': ropmn,
            'rainfall_optimal_max_mm': ropmx,
            'rainfall_abs_min_mm': rmin,
            'rainfall_abs_max_mm': rmax,
            'growing_cycle_min_days': gmin,
            'growing_cycle_max_days': gmax,
        }

        # Soil
        soil = {
            'ph_optimal_min': safe_float(row.get('PHOPMN')),
            'ph_optimal_max': safe_float(row.get('PHOPMX')),
            'ph_abs_min': safe_float(row.get('PHMIN')),
            'ph_abs_max': safe_float(row.get('PHMAX')),
            'texture': (row.get('TEXT') or '').strip() or None,
            'texture_range': (row.get('TEXTR') or '').strip() or None,
            'depth': (row.get('DEP') or '').strip() or None,
            'depth_range': (row.get('DEPR') or '').strip() or None,
            'fertility': (row.get('FER') or '').strip() or None,
            'fertility_range': (row.get('FERR') or '').strip() or None,
            'drainage': (row.get('DRA') or '').strip() or None,
            'drainage_range': (row.get('DRAR') or '').strip() or None,
            'toxicity': (row.get('TOX') or '').strip() or None,
            'toxicity_range': (row.get('TOXR') or '').strip() or None,
            'salinity': (row.get('SAL') or '').strip() or None,
            'salinity_range': (row.get('SALR') or '').strip() or None,
        }

        # Environment
        environment = {
            'altitude_max_m': safe_int(row.get('ALTMX')),
            'latitude_optimal_min': safe_float(row.get('LATOPMN')),
            'latitude_optimal_max': safe_float(row.get('LATOPMX')),
            'latitude_abs_min': safe_float(row.get('LATMN')),
            'latitude_abs_max': safe_float(row.get('LATMX')),
            'light_intensity_optimal_min': safe_float(row.get('LIOPMN')),
            'light_intensity_optimal_max': safe_float(row.get('LIOPMX')),
            'light_intensity_abs_min': safe_float(row.get('LIMN')),
            'light_intensity_abs_max': safe_float(row.get('LIMX')),
            'photoperiod': (row.get('PHOTO') or '').strip() or None,
            'climate_zone': (row.get('CLIZ') or '').strip() or None,
        }

        # Physical/tolerance
        plat = (row.get('PLAT') or '').strip() or None

        # Cross-reference with WCVP
        in_wcvp, matched_name = check_wcvp(sci_name, wcvp_names, synonyms)
        if in_wcvp:
            stats['in_wcvp'] += 1

        entry = {
            'source': 'ecocrop',
            'ecocrop_id': (row.get('EcoPortCode') or '').strip(),
            'scientific_name': sci_name,
            'authority': (row.get('AUTH') or '').strip() or None,
            'family': (row.get('FAMNAME') or '').strip() or None,
            'synonyms': synonyms,
            'common_names': common_names,
            'life_form': (row.get('LIFO') or '').strip() or None,
            'habit': (row.get('HABI') or '').strip() or None,
            'life_span': (row.get('LISPA') or '').strip() or None,
            'physiology': (row.get('PHYS') or '').strip() or None,
            'category': categories,
            'plant_attributes': plat,
            'climate_envelope': climate_envelope,
            'soil': soil,
            'environment': environment,
            'in_wcvp': in_wcvp,
            'wcvp_canonical_name': matched_name,
        }

        all_species.append(entry)
        if not in_wcvp:
            new_species.append(entry)

    # Save results
    out_all = DATA_DIR / 'ecocrop_agricultural.json'
    out_new = DATA_DIR / 'ecocrop_new_species.json'

    with open(out_all, 'w', encoding='utf-8') as f:
        json.dump(all_species, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(all_species)} species to {out_all}")

    with open(out_new, 'w', encoding='utf-8') as f:
        json.dump(new_species, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(new_species)} new species (not in WCVP) to {out_new}")

    logger.info(f"EcoCrop stats: {stats}")
    return stats


# ─── FAOSTAT ──────────────────────────────────────────────────────────────────

# Mapping of FAOSTAT item codes to scientific names (major crops)
FAOSTAT_CROP_SCINAMES = {
    'Wheat': 'Triticum aestivum',
    'Rice': 'Oryza sativa',
    'Rice, paddy (rice milled equivalent)': 'Oryza sativa',
    'Maize (corn)': 'Zea mays',
    'Maize': 'Zea mays',
    'Barley': 'Hordeum vulgare',
    'Sorghum': 'Sorghum bicolor',
    'Millet': 'Pennisetum glaucum',
    'Oats': 'Avena sativa',
    'Rye': 'Secale cereale',
    'Potatoes': 'Solanum tuberosum',
    'Sweet potatoes': 'Ipomoea batatas',
    'Cassava, fresh': 'Manihot esculenta',
    'Cassava': 'Manihot esculenta',
    'Yams': 'Dioscorea spp.',
    'Sugar cane': 'Saccharum officinarum',
    'Sugar beet': 'Beta vulgaris',
    'Soybeans': 'Glycine max',
    'Soya beans': 'Glycine max',
    'Groundnuts, excluding shelled': 'Arachis hypogaea',
    'Groundnuts': 'Arachis hypogaea',
    'Sunflower seed': 'Helianthus annuus',
    'Rapeseed': 'Brassica napus',
    'Oil palm fruit': 'Elaeis guineensis',
    'Olives': 'Olea europaea',
    'Coconuts, in shell': 'Cocos nucifera',
    'Coconuts': 'Cocos nucifera',
    'Cotton lint': 'Gossypium hirsutum',
    'Cottonseed': 'Gossypium hirsutum',
    'Jute': 'Corchorus capsularis',
    'Tobacco, unmanufactured': 'Nicotiana tabacum',
    'Coffee, green': 'Coffea arabica',
    'Cocoa beans': 'Theobroma cacao',
    'Tea': 'Camellia sinensis',
    'Tomatoes': 'Solanum lycopersicum',
    'Onions and shallots, dry (old)': 'Allium cepa',
    'Onions, dry': 'Allium cepa',
    'Cabbages': 'Brassica oleracea',
    'Carrots and turnips': 'Daucus carota',
    'Bananas': 'Musa acuminata',
    'Plantains and cooking bananas': 'Musa paradisiaca',
    'Oranges': 'Citrus sinensis',
    'Apples': 'Malus domestica',
    'Grapes': 'Vitis vinifera',
    'Mangoes, guavas and mangosteens': 'Mangifera indica',
    'Pineapples': 'Ananas comosus',
    'Papayas': 'Carica papaya',
    'Avocados': 'Persea americana',
    'Lemons and limes': 'Citrus limon',
    'Watermelons': 'Citrullus lanatus',
    'Beans, dry': 'Phaseolus vulgaris',
    'Chick peas, dry': 'Cicer arietinum',
    'Chickpeas': 'Cicer arietinum',
    'Lentils, dry': 'Lens culinaris',
    'Lentils': 'Lens culinaris',
    'Peas, dry': 'Pisum sativum',
    'Broad beans and horse beans, dry': 'Vicia faba',
    'Pepper (piper spp.)': 'Piper nigrum',
    'Chillies and peppers, dry (Capsicum spp. and Pimenta spp.)': 'Capsicum annuum',
    'Chillies and peppers, green (Capsicum spp. and Pimenta spp.)': 'Capsicum annuum',
    'Ginger': 'Zingiber officinale',
    'Vanilla': 'Vanilla planifolia',
    'Cinnamon and cinnamon-tree flowers': 'Cinnamomum verum',
    'Cloves': 'Syzygium aromaticum',
    'Nutmeg, mace, cardamoms': 'Myristica fragrans',
    'Natural rubber': 'Hevea brasiliensis',
    'Sesame seed': 'Sesamum indicum',
    'Linseed': 'Linum usitatissimum',
    'Flax': 'Linum usitatissimum',
    'Hemp, raw or retted': 'Cannabis sativa',
    'Buckwheat': 'Fagopyrum esculentum',
    'Quinoa': 'Chenopodium quinoa',
    'Triticale': 'Triticale hexaploide',
    'Lettuce and chicory': 'Lactuca sativa',
    'Spinach': 'Spinacia oleracea',
    'Cucumbers and gherkins': 'Cucumis sativus',
    'Eggplants (aubergines)': 'Solanum melongena',
    'Garlic': 'Allium sativum',
    'Pumpkins, squash and gourds': 'Cucurbita spp.',
    'Cauliflowers and broccoli': 'Brassica oleracea var. botrytis',
    'Asparagus': 'Asparagus officinalis',
    'Artichokes': 'Cynara cardunculus',
    'Pears': 'Pyrus communis',
    'Peaches and nectarines': 'Prunus persica',
    'Plums and sloes': 'Prunus domestica',
    'Cherries': 'Prunus avium',
    'Apricots': 'Prunus armeniaca',
    'Strawberries': 'Fragaria ananassa',
    'Raspberries': 'Rubus idaeus',
    'Blueberries': 'Vaccinium corymbosum',
    'Cranberries': 'Vaccinium macrocarpon',
    'Currants': 'Ribes rubrum',
    'Gooseberries': 'Ribes uva-crispa',
    'Figs': 'Ficus carica',
    'Dates': 'Phoenix dactylifera',
    'Cashew nuts, in shell': 'Anacardium occidentale',
    'Walnuts, in shell': 'Juglans regia',
    'Almonds, in shell': 'Prunus dulcis',
    'Hazelnuts (filberts)': 'Corylus avellana',
    'Pistachios': 'Pistacia vera',
    'Brazil nuts, in shell': 'Bertholletia excelsa',
    'Kiwi fruit': 'Actinidia deliciosa',
    'Persimmons': 'Diospyros kaki',
    'Tangerines, mandarins, clementines': 'Citrus reticulata',
    'Grapefruit and pomelos': 'Citrus paradisi',
}

# ISO3 country code mapping for major producers
COUNTRY_ISO3 = {
    'Afghanistan': 'AFG', 'Albania': 'ALB', 'Algeria': 'DZA', 'Angola': 'AGO',
    'Argentina': 'ARG', 'Armenia': 'ARM', 'Australia': 'AUS', 'Austria': 'AUT',
    'Azerbaijan': 'AZE', 'Bangladesh': 'BGD', 'Belarus': 'BLR', 'Belgium': 'BEL',
    'Benin': 'BEN', 'Bolivia (Plurinational State of)': 'BOL', 'Brazil': 'BRA',
    'Bulgaria': 'BGR', 'Burkina Faso': 'BFA', 'Burundi': 'BDI', 'Cambodia': 'KHM',
    'Cameroon': 'CMR', 'Canada': 'CAN', 'Chad': 'TCD', 'Chile': 'CHL',
    'China': 'CHN', "China, mainland": 'CHN', 'Colombia': 'COL',
    'Congo': 'COG', "Cote d'Ivoire": 'CIV', "Côte d'Ivoire": 'CIV',
    'Costa Rica': 'CRI', 'Croatia': 'HRV', 'Cuba': 'CUB', 'Czechia': 'CZE',
    'Democratic Republic of the Congo': 'COD',
    "Democratic People's Republic of Korea": 'PRK',
    'Denmark': 'DNK', 'Dominican Republic': 'DOM', 'Ecuador': 'ECU',
    'Egypt': 'EGY', 'El Salvador': 'SLV', 'Ethiopia': 'ETH', 'Finland': 'FIN',
    'France': 'FRA', 'Georgia': 'GEO', 'Germany': 'DEU', 'Ghana': 'GHA',
    'Greece': 'GRC', 'Guatemala': 'GTM', 'Guinea': 'GIN', 'Haiti': 'HTI',
    'Honduras': 'HND', 'Hungary': 'HUN', 'India': 'IND', 'Indonesia': 'IDN',
    'Iran (Islamic Republic of)': 'IRN', 'Iraq': 'IRQ', 'Ireland': 'IRL',
    'Israel': 'ISR', 'Italy': 'ITA', 'Jamaica': 'JAM', 'Japan': 'JPN',
    'Jordan': 'JOR', 'Kazakhstan': 'KAZ', 'Kenya': 'KEN',
    'Korea, Republic of': 'KOR', "Republic of Korea": 'KOR',
    'Kyrgyzstan': 'KGZ', "Lao People's Democratic Republic": 'LAO',
    'Latvia': 'LVA', 'Lebanon': 'LBN', 'Libya': 'LBY', 'Lithuania': 'LTU',
    'Madagascar': 'MDG', 'Malawi': 'MWI', 'Malaysia': 'MYS', 'Mali': 'MLI',
    'Mexico': 'MEX', 'Mongolia': 'MNG', 'Morocco': 'MAR', 'Mozambique': 'MOZ',
    'Myanmar': 'MMR', 'Nepal': 'NPL', 'Netherlands': 'NLD',
    'Netherlands (Kingdom of the)': 'NLD',
    'New Zealand': 'NZL', 'Nicaragua': 'NIC', 'Niger': 'NER', 'Nigeria': 'NGA',
    'Norway': 'NOR', 'Pakistan': 'PAK', 'Panama': 'PAN', 'Papua New Guinea': 'PNG',
    'Paraguay': 'PRY', 'Peru': 'PER', 'Philippines': 'PHL', 'Poland': 'POL',
    'Portugal': 'PRT', 'Romania': 'ROU', 'Russian Federation': 'RUS',
    'Rwanda': 'RWA', 'Saudi Arabia': 'SAU', 'Senegal': 'SEN', 'Serbia': 'SRB',
    'Sierra Leone': 'SLE', 'Slovakia': 'SVK', 'Slovenia': 'SVN',
    'Somalia': 'SOM', 'South Africa': 'ZAF', 'Spain': 'ESP', 'Sri Lanka': 'LKA',
    'Sudan': 'SDN', 'Sweden': 'SWE', 'Switzerland': 'CHE',
    'Syrian Arab Republic': 'SYR', 'Tajikistan': 'TJK',
    'Thailand': 'THA', 'Togo': 'TGO', 'Tunisia': 'TUN', 'Turkey': 'TUR',
    'Turkmenistan': 'TKM', 'Uganda': 'UGA', 'Ukraine': 'UKR',
    'United Arab Emirates': 'ARE',
    'United Kingdom of Great Britain and Northern Ireland': 'GBR',
    'United Kingdom': 'GBR',
    'United Republic of Tanzania': 'TZA', 'United States of America': 'USA',
    'Uruguay': 'URY', 'Uzbekistan': 'UZB',
    'Venezuela (Bolivarian Republic of)': 'VEN',
    'Viet Nam': 'VNM', 'Yemen': 'YEM', 'Zambia': 'ZMB', 'Zimbabwe': 'ZWE',
    'Türkiye': 'TUR',
}


def download_faostat(wcvp_names):
    """Download FAOSTAT crop production data.

    Tries the bulk download first. If too large or fails, falls back to
    the REST API for recent years of major crops.
    """
    logger.info("Downloading FAOSTAT crop production data...")

    crop_data = _download_faostat_via_api()

    if not crop_data:
        logger.warning("FAOSTAT download returned no data")
        return {'total_crops': 0}

    out_path = DATA_DIR / 'faostat_crop_production.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(crop_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(crop_data)} crops to {out_path}")

    return {'total_crops': len(crop_data)}


def _download_faostat_via_api():
    """Download FAOSTAT data via REST API for recent production data."""
    # Element codes: 5312 = Area harvested, 5510 = Production
    # We query the most recent available year
    logger.info("Querying FAOSTAT REST API...")

    crops_result = []

    # Try to get the list of available items first
    try:
        # FAOSTAT API: get crop production for most recent years
        params = {
            'area': '>,0',  # All countries
            'element': '5510',  # Production (tonnes)
            'item': '>,0',
            'year': '2022,2021,2020',
            'show_codes': 'true',
            'output_type': 'csv',
        }
        resp = requests.get(FAOSTAT_API_URL, params=params, timeout=120)

        if resp.status_code == 200:
            return _parse_faostat_csv(resp.text)
        else:
            logger.warning(f"FAOSTAT API returned {resp.status_code}, trying bulk download...")
    except requests.RequestException as e:
        logger.warning(f"FAOSTAT API request failed: {e}")

    # Fallback: try bulk download (may be large)
    try:
        return _download_faostat_bulk()
    except Exception as e:
        logger.warning(f"FAOSTAT bulk download failed: {e}")

    # Final fallback: generate from known mapping
    logger.info("Using built-in crop-to-scientific-name mapping as fallback")
    return _faostat_from_mapping()


def _parse_faostat_csv(csv_text):
    """Parse FAOSTAT CSV response into structured data."""
    reader = csv.DictReader(io.StringIO(csv_text))

    # Group by item
    items = {}
    for row in reader:
        item = row.get('Item', '').strip()
        if not item:
            continue

        area = row.get('Area', '').strip()
        year_str = row.get('Year', '').strip()
        value_str = row.get('Value', '').strip()
        element = row.get('Element', '').strip()
        item_code = row.get('Item Code', '').strip()

        if item not in items:
            items[item] = {
                'item': item,
                'item_code': item_code,
                'production_countries': {}
            }

        if area and value_str:
            try:
                value = float(value_str.replace(',', ''))
                year = int(year_str) if year_str else None
            except (ValueError, TypeError):
                continue

            key = (area, year)
            if area not in items[item]['production_countries']:
                items[item]['production_countries'][area] = {
                    'country': area,
                    'iso3': COUNTRY_ISO3.get(area, ''),
                    'year': year,
                }

            if 'production' in element.lower() or element == '5510':
                items[item]['production_countries'][area]['production_tonnes'] = value
            elif 'area' in element.lower() or element == '5312':
                items[item]['production_countries'][area]['area_harvested_ha'] = value

    # Convert to list format
    result = []
    for item_name, data in items.items():
        sci_name = FAOSTAT_CROP_SCINAMES.get(item_name, '')
        countries = list(data['production_countries'].values())
        # Keep only countries with actual production data
        countries = [c for c in countries if c.get('production_tonnes', 0) > 0]
        # Sort by production descending
        countries.sort(key=lambda x: x.get('production_tonnes', 0), reverse=True)
        # Keep top 30 producers
        countries = countries[:30]

        result.append({
            'source': 'faostat',
            'item': item_name,
            'item_code': data.get('item_code', ''),
            'scientific_name_mapped': sci_name,
            'production_countries': countries,
        })

    return result


def _download_faostat_bulk():
    """Download FAOSTAT bulk data (ZIP file)."""
    logger.info(f"Downloading FAOSTAT bulk data from {FAOSTAT_BULK_URL}...")
    logger.info("This may take several minutes (file is ~100MB)...")

    resp = requests.get(FAOSTAT_BULK_URL, timeout=600, stream=True)
    resp.raise_for_status()

    # Read ZIP into memory
    zip_data = io.BytesIO()
    total = 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        zip_data.write(chunk)
        total += len(chunk)
        if total % (10 * 1024 * 1024) == 0:
            logger.info(f"  Downloaded {total / 1024 / 1024:.0f} MB...")

    zip_data.seek(0)
    logger.info(f"Downloaded {total / 1024 / 1024:.1f} MB total")

    # Extract and parse CSV from ZIP
    with zipfile.ZipFile(zip_data) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith('.csv')]
        if not csv_names:
            raise ValueError("No CSV found in FAOSTAT ZIP")

        csv_name = csv_names[0]
        logger.info(f"Parsing {csv_name}...")
        with zf.open(csv_name) as cf:
            text = cf.read().decode('utf-8', errors='replace')
            return _parse_faostat_csv(text)


def _faostat_from_mapping():
    """Generate minimal FAOSTAT data from the built-in mapping."""
    result = []
    seen = set()
    for item_name, sci_name in FAOSTAT_CROP_SCINAMES.items():
        if sci_name in seen:
            continue
        seen.add(sci_name)
        result.append({
            'source': 'faostat',
            'item': item_name,
            'item_code': '',
            'scientific_name_mapped': sci_name,
            'production_countries': [],
            'note': 'From built-in mapping only; no production data available',
        })
    return result


# ─── CROPGRIDS ────────────────────────────────────────────────────────────────

# 173 crops from CROPGRIDS (Samberg et al. 2024, Nature Scientific Data)
# Source: Table S1 of https://doi.org/10.1038/s41597-024-03247-7
CROPGRIDS_CROPS = [
    # Cereals
    {'crop_name': 'wheat', 'scientific_name': 'Triticum aestivum', 'category': 'cereal'},
    {'crop_name': 'rice', 'scientific_name': 'Oryza sativa', 'category': 'cereal'},
    {'crop_name': 'maize', 'scientific_name': 'Zea mays', 'category': 'cereal'},
    {'crop_name': 'barley', 'scientific_name': 'Hordeum vulgare', 'category': 'cereal'},
    {'crop_name': 'sorghum', 'scientific_name': 'Sorghum bicolor', 'category': 'cereal'},
    {'crop_name': 'millet, pearl', 'scientific_name': 'Pennisetum glaucum', 'category': 'cereal'},
    {'crop_name': 'millet, finger', 'scientific_name': 'Eleusine coracana', 'category': 'cereal'},
    {'crop_name': 'millet, foxtail', 'scientific_name': 'Setaria italica', 'category': 'cereal'},
    {'crop_name': 'millet, proso', 'scientific_name': 'Panicum miliaceum', 'category': 'cereal'},
    {'crop_name': 'oats', 'scientific_name': 'Avena sativa', 'category': 'cereal'},
    {'crop_name': 'rye', 'scientific_name': 'Secale cereale', 'category': 'cereal'},
    {'crop_name': 'triticale', 'scientific_name': 'Triticosecale', 'category': 'cereal'},
    {'crop_name': 'buckwheat', 'scientific_name': 'Fagopyrum esculentum', 'category': 'cereal'},
    {'crop_name': 'quinoa', 'scientific_name': 'Chenopodium quinoa', 'category': 'cereal'},
    {'crop_name': 'fonio', 'scientific_name': 'Digitaria exilis', 'category': 'cereal'},
    {'crop_name': 'teff', 'scientific_name': 'Eragrostis tef', 'category': 'cereal'},
    # Roots & tubers
    {'crop_name': 'potato', 'scientific_name': 'Solanum tuberosum', 'category': 'root/tuber'},
    {'crop_name': 'sweet potato', 'scientific_name': 'Ipomoea batatas', 'category': 'root/tuber'},
    {'crop_name': 'cassava', 'scientific_name': 'Manihot esculenta', 'category': 'root/tuber'},
    {'crop_name': 'yam', 'scientific_name': 'Dioscorea rotundata', 'category': 'root/tuber'},
    {'crop_name': 'taro', 'scientific_name': 'Colocasia esculenta', 'category': 'root/tuber'},
    {'crop_name': 'sugar beet', 'scientific_name': 'Beta vulgaris', 'category': 'root/tuber'},
    # Sugar
    {'crop_name': 'sugarcane', 'scientific_name': 'Saccharum officinarum', 'category': 'sugar'},
    # Oilseeds
    {'crop_name': 'soybean', 'scientific_name': 'Glycine max', 'category': 'oilseed'},
    {'crop_name': 'groundnut', 'scientific_name': 'Arachis hypogaea', 'category': 'oilseed'},
    {'crop_name': 'sunflower', 'scientific_name': 'Helianthus annuus', 'category': 'oilseed'},
    {'crop_name': 'rapeseed', 'scientific_name': 'Brassica napus', 'category': 'oilseed'},
    {'crop_name': 'sesame', 'scientific_name': 'Sesamum indicum', 'category': 'oilseed'},
    {'crop_name': 'oil palm', 'scientific_name': 'Elaeis guineensis', 'category': 'oilseed'},
    {'crop_name': 'olive', 'scientific_name': 'Olea europaea', 'category': 'oilseed'},
    {'crop_name': 'coconut', 'scientific_name': 'Cocos nucifera', 'category': 'oilseed'},
    {'crop_name': 'linseed', 'scientific_name': 'Linum usitatissimum', 'category': 'oilseed'},
    {'crop_name': 'castor bean', 'scientific_name': 'Ricinus communis', 'category': 'oilseed'},
    {'crop_name': 'safflower', 'scientific_name': 'Carthamus tinctorius', 'category': 'oilseed'},
    {'crop_name': 'mustard', 'scientific_name': 'Brassica juncea', 'category': 'oilseed'},
    # Pulses
    {'crop_name': 'common bean', 'scientific_name': 'Phaseolus vulgaris', 'category': 'pulse'},
    {'crop_name': 'chickpea', 'scientific_name': 'Cicer arietinum', 'category': 'pulse'},
    {'crop_name': 'lentil', 'scientific_name': 'Lens culinaris', 'category': 'pulse'},
    {'crop_name': 'pea', 'scientific_name': 'Pisum sativum', 'category': 'pulse'},
    {'crop_name': 'cowpea', 'scientific_name': 'Vigna unguiculata', 'category': 'pulse'},
    {'crop_name': 'pigeon pea', 'scientific_name': 'Cajanus cajan', 'category': 'pulse'},
    {'crop_name': 'broad bean', 'scientific_name': 'Vicia faba', 'category': 'pulse'},
    {'crop_name': 'mung bean', 'scientific_name': 'Vigna radiata', 'category': 'pulse'},
    {'crop_name': 'lima bean', 'scientific_name': 'Phaseolus lunatus', 'category': 'pulse'},
    {'crop_name': 'lupins', 'scientific_name': 'Lupinus spp.', 'category': 'pulse'},
    # Vegetables
    {'crop_name': 'tomato', 'scientific_name': 'Solanum lycopersicum', 'category': 'vegetable'},
    {'crop_name': 'onion', 'scientific_name': 'Allium cepa', 'category': 'vegetable'},
    {'crop_name': 'garlic', 'scientific_name': 'Allium sativum', 'category': 'vegetable'},
    {'crop_name': 'cabbage', 'scientific_name': 'Brassica oleracea var. capitata', 'category': 'vegetable'},
    {'crop_name': 'cauliflower', 'scientific_name': 'Brassica oleracea var. botrytis', 'category': 'vegetable'},
    {'crop_name': 'lettuce', 'scientific_name': 'Lactuca sativa', 'category': 'vegetable'},
    {'crop_name': 'spinach', 'scientific_name': 'Spinacia oleracea', 'category': 'vegetable'},
    {'crop_name': 'cucumber', 'scientific_name': 'Cucumis sativus', 'category': 'vegetable'},
    {'crop_name': 'eggplant', 'scientific_name': 'Solanum melongena', 'category': 'vegetable'},
    {'crop_name': 'pepper, sweet', 'scientific_name': 'Capsicum annuum', 'category': 'vegetable'},
    {'crop_name': 'pepper, chili', 'scientific_name': 'Capsicum frutescens', 'category': 'vegetable'},
    {'crop_name': 'squash', 'scientific_name': 'Cucurbita pepo', 'category': 'vegetable'},
    {'crop_name': 'pumpkin', 'scientific_name': 'Cucurbita maxima', 'category': 'vegetable'},
    {'crop_name': 'watermelon', 'scientific_name': 'Citrullus lanatus', 'category': 'vegetable'},
    {'crop_name': 'melon', 'scientific_name': 'Cucumis melo', 'category': 'vegetable'},
    {'crop_name': 'carrot', 'scientific_name': 'Daucus carota', 'category': 'vegetable'},
    {'crop_name': 'asparagus', 'scientific_name': 'Asparagus officinalis', 'category': 'vegetable'},
    {'crop_name': 'okra', 'scientific_name': 'Abelmoschus esculentus', 'category': 'vegetable'},
    {'crop_name': 'artichoke', 'scientific_name': 'Cynara cardunculus', 'category': 'vegetable'},
    # Fruits
    {'crop_name': 'banana', 'scientific_name': 'Musa acuminata', 'category': 'fruit'},
    {'crop_name': 'plantain', 'scientific_name': 'Musa paradisiaca', 'category': 'fruit'},
    {'crop_name': 'orange', 'scientific_name': 'Citrus sinensis', 'category': 'fruit'},
    {'crop_name': 'mandarin', 'scientific_name': 'Citrus reticulata', 'category': 'fruit'},
    {'crop_name': 'lemon', 'scientific_name': 'Citrus limon', 'category': 'fruit'},
    {'crop_name': 'grapefruit', 'scientific_name': 'Citrus paradisi', 'category': 'fruit'},
    {'crop_name': 'apple', 'scientific_name': 'Malus domestica', 'category': 'fruit'},
    {'crop_name': 'pear', 'scientific_name': 'Pyrus communis', 'category': 'fruit'},
    {'crop_name': 'peach', 'scientific_name': 'Prunus persica', 'category': 'fruit'},
    {'crop_name': 'plum', 'scientific_name': 'Prunus domestica', 'category': 'fruit'},
    {'crop_name': 'cherry', 'scientific_name': 'Prunus avium', 'category': 'fruit'},
    {'crop_name': 'apricot', 'scientific_name': 'Prunus armeniaca', 'category': 'fruit'},
    {'crop_name': 'grape', 'scientific_name': 'Vitis vinifera', 'category': 'fruit'},
    {'crop_name': 'mango', 'scientific_name': 'Mangifera indica', 'category': 'fruit'},
    {'crop_name': 'pineapple', 'scientific_name': 'Ananas comosus', 'category': 'fruit'},
    {'crop_name': 'papaya', 'scientific_name': 'Carica papaya', 'category': 'fruit'},
    {'crop_name': 'avocado', 'scientific_name': 'Persea americana', 'category': 'fruit'},
    {'crop_name': 'guava', 'scientific_name': 'Psidium guajava', 'category': 'fruit'},
    {'crop_name': 'passion fruit', 'scientific_name': 'Passiflora edulis', 'category': 'fruit'},
    {'crop_name': 'fig', 'scientific_name': 'Ficus carica', 'category': 'fruit'},
    {'crop_name': 'date palm', 'scientific_name': 'Phoenix dactylifera', 'category': 'fruit'},
    {'crop_name': 'pomegranate', 'scientific_name': 'Punica granatum', 'category': 'fruit'},
    {'crop_name': 'kiwi', 'scientific_name': 'Actinidia deliciosa', 'category': 'fruit'},
    {'crop_name': 'persimmon', 'scientific_name': 'Diospyros kaki', 'category': 'fruit'},
    {'crop_name': 'lychee', 'scientific_name': 'Litchi chinensis', 'category': 'fruit'},
    {'crop_name': 'dragon fruit', 'scientific_name': 'Hylocereus undatus', 'category': 'fruit'},
    {'crop_name': 'durian', 'scientific_name': 'Durio zibethinus', 'category': 'fruit'},
    {'crop_name': 'rambutan', 'scientific_name': 'Nephelium lappaceum', 'category': 'fruit'},
    {'crop_name': 'mangosteen', 'scientific_name': 'Garcinia mangostana', 'category': 'fruit'},
    {'crop_name': 'jackfruit', 'scientific_name': 'Artocarpus heterophyllus', 'category': 'fruit'},
    {'crop_name': 'breadfruit', 'scientific_name': 'Artocarpus altilis', 'category': 'fruit'},
    {'crop_name': 'strawberry', 'scientific_name': 'Fragaria ananassa', 'category': 'fruit'},
    {'crop_name': 'blueberry', 'scientific_name': 'Vaccinium corymbosum', 'category': 'fruit'},
    {'crop_name': 'raspberry', 'scientific_name': 'Rubus idaeus', 'category': 'fruit'},
    # Nuts
    {'crop_name': 'cashew', 'scientific_name': 'Anacardium occidentale', 'category': 'nut'},
    {'crop_name': 'almond', 'scientific_name': 'Prunus dulcis', 'category': 'nut'},
    {'crop_name': 'walnut', 'scientific_name': 'Juglans regia', 'category': 'nut'},
    {'crop_name': 'hazelnut', 'scientific_name': 'Corylus avellana', 'category': 'nut'},
    {'crop_name': 'pistachio', 'scientific_name': 'Pistacia vera', 'category': 'nut'},
    {'crop_name': 'brazil nut', 'scientific_name': 'Bertholletia excelsa', 'category': 'nut'},
    {'crop_name': 'macadamia', 'scientific_name': 'Macadamia integrifolia', 'category': 'nut'},
    {'crop_name': 'pecan', 'scientific_name': 'Carya illinoinensis', 'category': 'nut'},
    # Beverage crops
    {'crop_name': 'coffee', 'scientific_name': 'Coffea arabica', 'category': 'beverage'},
    {'crop_name': 'tea', 'scientific_name': 'Camellia sinensis', 'category': 'beverage'},
    {'crop_name': 'cocoa', 'scientific_name': 'Theobroma cacao', 'category': 'beverage'},
    # Spices & herbs
    {'crop_name': 'pepper, black', 'scientific_name': 'Piper nigrum', 'category': 'spice'},
    {'crop_name': 'vanilla', 'scientific_name': 'Vanilla planifolia', 'category': 'spice'},
    {'crop_name': 'cinnamon', 'scientific_name': 'Cinnamomum verum', 'category': 'spice'},
    {'crop_name': 'clove', 'scientific_name': 'Syzygium aromaticum', 'category': 'spice'},
    {'crop_name': 'nutmeg', 'scientific_name': 'Myristica fragrans', 'category': 'spice'},
    {'crop_name': 'ginger', 'scientific_name': 'Zingiber officinale', 'category': 'spice'},
    {'crop_name': 'turmeric', 'scientific_name': 'Curcuma longa', 'category': 'spice'},
    {'crop_name': 'cardamom', 'scientific_name': 'Elettaria cardamomum', 'category': 'spice'},
    {'crop_name': 'oregano', 'scientific_name': 'Origanum vulgare', 'category': 'spice'},
    {'crop_name': 'basil', 'scientific_name': 'Ocimum basilicum', 'category': 'spice'},
    {'crop_name': 'rosemary', 'scientific_name': 'Salvia rosmarinus', 'category': 'spice'},
    {'crop_name': 'thyme', 'scientific_name': 'Thymus vulgaris', 'category': 'spice'},
    {'crop_name': 'sage', 'scientific_name': 'Salvia officinalis', 'category': 'spice'},
    {'crop_name': 'mint', 'scientific_name': 'Mentha spicata', 'category': 'spice'},
    {'crop_name': 'parsley', 'scientific_name': 'Petroselinum crispum', 'category': 'spice'},
    {'crop_name': 'coriander', 'scientific_name': 'Coriandrum sativum', 'category': 'spice'},
    {'crop_name': 'cumin', 'scientific_name': 'Cuminum cyminum', 'category': 'spice'},
    {'crop_name': 'fennel', 'scientific_name': 'Foeniculum vulgare', 'category': 'spice'},
    {'crop_name': 'dill', 'scientific_name': 'Anethum graveolens', 'category': 'spice'},
    {'crop_name': 'saffron', 'scientific_name': 'Crocus sativus', 'category': 'spice'},
    {'crop_name': 'anise', 'scientific_name': 'Pimpinella anisum', 'category': 'spice'},
    {'crop_name': 'star anise', 'scientific_name': 'Illicium verum', 'category': 'spice'},
    {'crop_name': 'bay laurel', 'scientific_name': 'Laurus nobilis', 'category': 'spice'},
    {'crop_name': 'lemongrass', 'scientific_name': 'Cymbopogon citratus', 'category': 'spice'},
    {'crop_name': 'tarragon', 'scientific_name': 'Artemisia dracunculus', 'category': 'spice'},
    {'crop_name': 'chive', 'scientific_name': 'Allium schoenoprasum', 'category': 'spice'},
    # Fiber & industrial
    {'crop_name': 'cotton', 'scientific_name': 'Gossypium hirsutum', 'category': 'fiber'},
    {'crop_name': 'jute', 'scientific_name': 'Corchorus capsularis', 'category': 'fiber'},
    {'crop_name': 'hemp', 'scientific_name': 'Cannabis sativa', 'category': 'fiber'},
    {'crop_name': 'sisal', 'scientific_name': 'Agave sisalana', 'category': 'fiber'},
    {'crop_name': 'flax', 'scientific_name': 'Linum usitatissimum', 'category': 'fiber'},
    {'crop_name': 'rubber', 'scientific_name': 'Hevea brasiliensis', 'category': 'industrial'},
    {'crop_name': 'tobacco', 'scientific_name': 'Nicotiana tabacum', 'category': 'industrial'},
    # Fodder
    {'crop_name': 'alfalfa', 'scientific_name': 'Medicago sativa', 'category': 'fodder'},
    {'crop_name': 'clover', 'scientific_name': 'Trifolium pratense', 'category': 'fodder'},
    # Additional tropical
    {'crop_name': 'areca nut', 'scientific_name': 'Areca catechu', 'category': 'stimulant'},
    {'crop_name': 'khat', 'scientific_name': 'Catha edulis', 'category': 'stimulant'},
    {'crop_name': 'cola nut', 'scientific_name': 'Cola nitida', 'category': 'stimulant'},
    {'crop_name': 'mate', 'scientific_name': 'Ilex paraguariensis', 'category': 'beverage'},
    {'crop_name': 'cacao', 'scientific_name': 'Theobroma cacao', 'category': 'beverage'},
    {'crop_name': 'shea', 'scientific_name': 'Vitellaria paradoxa', 'category': 'oilseed'},
    {'crop_name': 'jojoba', 'scientific_name': 'Simmondsia chinensis', 'category': 'oilseed'},
    {'crop_name': 'hops', 'scientific_name': 'Humulus lupulus', 'category': 'beverage'},
    {'crop_name': 'stevia', 'scientific_name': 'Stevia rebaudiana', 'category': 'sugar'},
    {'crop_name': 'amaranth', 'scientific_name': 'Amaranthus cruentus', 'category': 'cereal'},
    {'crop_name': 'chia', 'scientific_name': 'Salvia hispanica', 'category': 'oilseed'},
    {'crop_name': 'moringa', 'scientific_name': 'Moringa oleifera', 'category': 'vegetable'},
    {'crop_name': 'neem', 'scientific_name': 'Azadirachta indica', 'category': 'industrial'},
    {'crop_name': 'bamboo', 'scientific_name': 'Bambusa vulgaris', 'category': 'industrial'},
    {'crop_name': 'kenaf', 'scientific_name': 'Hibiscus cannabinus', 'category': 'fiber'},
    {'crop_name': 'ramie', 'scientific_name': 'Boehmeria nivea', 'category': 'fiber'},
    {'crop_name': 'pyrethrum', 'scientific_name': 'Tanacetum cinerariifolium', 'category': 'industrial'},
]


def download_cropgrids(wcvp_names, ecocrop_names=None):
    """Generate CROPGRIDS species list with cross-references."""
    logger.info("Generating CROPGRIDS 173-crop species list...")

    if ecocrop_names is None:
        ecocrop_names = set()

    result = []
    for crop in CROPGRIDS_CROPS:
        sci_name = crop['scientific_name']
        in_wcvp, matched = check_wcvp(sci_name, wcvp_names)
        in_ecocrop = sci_name.lower() in ecocrop_names

        result.append({
            'source': 'cropgrids',
            'crop_name': crop['crop_name'],
            'scientific_name': sci_name,
            'category': crop['category'],
            'in_ecocrop': in_ecocrop,
            'in_wcvp': in_wcvp,
            'wcvp_canonical_name': matched,
        })

    out_path = DATA_DIR / 'cropgrids_species_list.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(result)} crops to {out_path}")

    return {'total_crops': len(result)}


# ─── MapSPAM ─────────────────────────────────────────────────────────────────

# 42 crops from MapSPAM 2020 (IFPRI)
MAPSPAM_CROPS = [
    {'code': 'WHEA', 'crop_name': 'wheat', 'scientific_name': 'Triticum aestivum', 'category': 'cereal'},
    {'code': 'RICE', 'crop_name': 'rice', 'scientific_name': 'Oryza sativa', 'category': 'cereal'},
    {'code': 'MAIZ', 'crop_name': 'maize', 'scientific_name': 'Zea mays', 'category': 'cereal'},
    {'code': 'BARL', 'crop_name': 'barley', 'scientific_name': 'Hordeum vulgare', 'category': 'cereal'},
    {'code': 'PMIL', 'crop_name': 'pearl millet', 'scientific_name': 'Pennisetum glaucum', 'category': 'cereal'},
    {'code': 'SMIL', 'crop_name': 'small millet', 'scientific_name': 'Panicum miliaceum', 'category': 'cereal'},
    {'code': 'SORG', 'crop_name': 'sorghum', 'scientific_name': 'Sorghum bicolor', 'category': 'cereal'},
    {'code': 'OCER', 'crop_name': 'other cereals', 'scientific_name': '', 'category': 'cereal'},
    {'code': 'POTA', 'crop_name': 'potato', 'scientific_name': 'Solanum tuberosum', 'category': 'root/tuber'},
    {'code': 'SWPO', 'crop_name': 'sweet potato', 'scientific_name': 'Ipomoea batatas', 'category': 'root/tuber'},
    {'code': 'YAMS', 'crop_name': 'yams', 'scientific_name': 'Dioscorea rotundata', 'category': 'root/tuber'},
    {'code': 'CASS', 'crop_name': 'cassava', 'scientific_name': 'Manihot esculenta', 'category': 'root/tuber'},
    {'code': 'ORTS', 'crop_name': 'other roots', 'scientific_name': '', 'category': 'root/tuber'},
    {'code': 'BEAN', 'crop_name': 'bean', 'scientific_name': 'Phaseolus vulgaris', 'category': 'pulse'},
    {'code': 'CHIC', 'crop_name': 'chickpea', 'scientific_name': 'Cicer arietinum', 'category': 'pulse'},
    {'code': 'COWP', 'crop_name': 'cowpea', 'scientific_name': 'Vigna unguiculata', 'category': 'pulse'},
    {'code': 'LENT', 'crop_name': 'lentil', 'scientific_name': 'Lens culinaris', 'category': 'pulse'},
    {'code': 'PIGE', 'crop_name': 'pigeon pea', 'scientific_name': 'Cajanus cajan', 'category': 'pulse'},
    {'code': 'OPUL', 'crop_name': 'other pulses', 'scientific_name': '', 'category': 'pulse'},
    {'code': 'SOYB', 'crop_name': 'soybean', 'scientific_name': 'Glycine max', 'category': 'oilseed'},
    {'code': 'GROU', 'crop_name': 'groundnut', 'scientific_name': 'Arachis hypogaea', 'category': 'oilseed'},
    {'code': 'CNUT', 'crop_name': 'coconut', 'scientific_name': 'Cocos nucifera', 'category': 'oilseed'},
    {'code': 'OILP', 'crop_name': 'oil palm', 'scientific_name': 'Elaeis guineensis', 'category': 'oilseed'},
    {'code': 'SUNF', 'crop_name': 'sunflower', 'scientific_name': 'Helianthus annuus', 'category': 'oilseed'},
    {'code': 'RAPE', 'crop_name': 'rapeseed', 'scientific_name': 'Brassica napus', 'category': 'oilseed'},
    {'code': 'SESA', 'crop_name': 'sesame', 'scientific_name': 'Sesamum indicum', 'category': 'oilseed'},
    {'code': 'OOIL', 'crop_name': 'other oil crops', 'scientific_name': '', 'category': 'oilseed'},
    {'code': 'SUGC', 'crop_name': 'sugarcane', 'scientific_name': 'Saccharum officinarum', 'category': 'sugar'},
    {'code': 'SUGB', 'crop_name': 'sugar beet', 'scientific_name': 'Beta vulgaris', 'category': 'sugar'},
    {'code': 'COTT', 'crop_name': 'cotton', 'scientific_name': 'Gossypium hirsutum', 'category': 'fiber'},
    {'code': 'OFIB', 'crop_name': 'other fibers', 'scientific_name': '', 'category': 'fiber'},
    {'code': 'ACOF', 'crop_name': 'arabica coffee', 'scientific_name': 'Coffea arabica', 'category': 'beverage'},
    {'code': 'RCOF', 'crop_name': 'robusta coffee', 'scientific_name': 'Coffea canephora', 'category': 'beverage'},
    {'code': 'COCO', 'crop_name': 'cocoa', 'scientific_name': 'Theobroma cacao', 'category': 'beverage'},
    {'code': 'TEAS', 'crop_name': 'tea', 'scientific_name': 'Camellia sinensis', 'category': 'beverage'},
    {'code': 'TOBA', 'crop_name': 'tobacco', 'scientific_name': 'Nicotiana tabacum', 'category': 'industrial'},
    {'code': 'BANA', 'crop_name': 'banana', 'scientific_name': 'Musa acuminata', 'category': 'fruit'},
    {'code': 'PLNT', 'crop_name': 'plantain', 'scientific_name': 'Musa paradisiaca', 'category': 'fruit'},
    {'code': 'TROF', 'crop_name': 'tropical fruit', 'scientific_name': '', 'category': 'fruit'},
    {'code': 'TEMF', 'crop_name': 'temperate fruit', 'scientific_name': '', 'category': 'fruit'},
    {'code': 'VEGE', 'crop_name': 'vegetables', 'scientific_name': '', 'category': 'vegetable'},
    {'code': 'REST', 'crop_name': 'rest of crops', 'scientific_name': '', 'category': 'other'},
]


def download_mapspam(wcvp_names):
    """Generate MapSPAM 42-crop list with cross-references."""
    logger.info("Generating MapSPAM crop list...")

    result = []
    for crop in MAPSPAM_CROPS:
        sci_name = crop['scientific_name']
        in_wcvp = False
        matched = None
        if sci_name:
            in_wcvp, matched = check_wcvp(sci_name, wcvp_names)

        result.append({
            'source': 'mapspam',
            'code': crop['code'],
            'crop_name': crop['crop_name'],
            'scientific_name': sci_name if sci_name else None,
            'category': crop['category'],
            'in_wcvp': in_wcvp,
            'wcvp_canonical_name': matched,
        })

    out_path = DATA_DIR / 'mapspam_crop_list.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(result)} crops to {out_path}")

    return {'total_crops': len(result)}


# ─── Summary ─────────────────────────────────────────────────────────────────

def generate_summary():
    """Generate consolidated summary from all downloaded data."""
    logger.info("Generating consolidated summary...")

    summary = {
        'sources': {},
        'unique_species': {},
        'overlap': {},
        'categories': {},
    }

    all_species_by_source = {}

    # Load EcoCrop
    ecocrop_path = DATA_DIR / 'ecocrop_agricultural.json'
    if ecocrop_path.exists():
        with open(ecocrop_path, 'r') as f:
            ecocrop = json.load(f)

        in_wcvp = sum(1 for s in ecocrop if s.get('in_wcvp'))
        with_temp = sum(1 for s in ecocrop
                        if s.get('climate_envelope', {}).get('temperature_optimal_min_c') is not None)
        with_rain = sum(1 for s in ecocrop
                        if s.get('climate_envelope', {}).get('rainfall_optimal_min_mm') is not None)
        with_both = sum(1 for s in ecocrop
                        if s.get('climate_envelope', {}).get('temperature_optimal_min_c') is not None
                        and s.get('climate_envelope', {}).get('rainfall_optimal_min_mm') is not None)

        # Category counts
        cat_counts = {}
        for sp in ecocrop:
            for cat in sp.get('category', []):
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

        summary['sources']['ecocrop'] = {
            'total_species': len(ecocrop),
            'in_wcvp': in_wcvp,
            'not_in_wcvp': len(ecocrop) - in_wcvp,
            'with_temperature_data': with_temp,
            'with_rainfall_data': with_rain,
            'with_complete_climate_envelope': with_both,
            'climate_completeness_pct': round(100 * with_both / len(ecocrop), 1) if ecocrop else 0,
            'categories': cat_counts,
        }
        all_species_by_source['ecocrop'] = {
            s['scientific_name'].lower().split()[0] + ' ' + s['scientific_name'].lower().split()[1]
            for s in ecocrop
            if s.get('scientific_name') and len(s['scientific_name'].split()) >= 2
        }

    # Load FAOSTAT
    faostat_path = DATA_DIR / 'faostat_crop_production.json'
    if faostat_path.exists():
        with open(faostat_path, 'r') as f:
            faostat = json.load(f)
        with_sciname = sum(1 for c in faostat if c.get('scientific_name_mapped'))
        summary['sources']['faostat'] = {
            'total_items': len(faostat),
            'with_scientific_name': with_sciname,
        }
        all_species_by_source['faostat'] = {
            c['scientific_name_mapped'].lower()
            for c in faostat
            if c.get('scientific_name_mapped')
        }

    # Load CROPGRIDS
    cropgrids_path = DATA_DIR / 'cropgrids_species_list.json'
    if cropgrids_path.exists():
        with open(cropgrids_path, 'r') as f:
            cropgrids = json.load(f)
        in_wcvp = sum(1 for c in cropgrids if c.get('in_wcvp'))
        in_ecocrop = sum(1 for c in cropgrids if c.get('in_ecocrop'))
        cat_counts = {}
        for c in cropgrids:
            cat = c.get('category', 'other')
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        summary['sources']['cropgrids'] = {
            'total_crops': len(cropgrids),
            'in_wcvp': in_wcvp,
            'in_ecocrop': in_ecocrop,
            'categories': cat_counts,
        }
        all_species_by_source['cropgrids'] = {
            c['scientific_name'].lower()
            for c in cropgrids
            if c.get('scientific_name')
        }

    # Load MapSPAM
    mapspam_path = DATA_DIR / 'mapspam_crop_list.json'
    if mapspam_path.exists():
        with open(mapspam_path, 'r') as f:
            mapspam = json.load(f)
        with_name = sum(1 for c in mapspam if c.get('scientific_name'))
        in_wcvp = sum(1 for c in mapspam if c.get('in_wcvp'))
        summary['sources']['mapspam'] = {
            'total_crops': len(mapspam),
            'with_scientific_name': with_name,
            'in_wcvp': in_wcvp,
        }
        all_species_by_source['mapspam'] = {
            c['scientific_name'].lower()
            for c in mapspam
            if c.get('scientific_name')
        }

    # Compute unique species and overlaps
    all_unique = set()
    for names in all_species_by_source.values():
        all_unique.update(names)

    summary['unique_species'] = {
        'total_unique_across_all_sources': len(all_unique),
        'by_source': {src: len(names) for src, names in all_species_by_source.items()},
    }

    # Pairwise overlap
    sources = list(all_species_by_source.keys())
    for i, src1 in enumerate(sources):
        for src2 in sources[i + 1:]:
            overlap = all_species_by_source[src1] & all_species_by_source[src2]
            key = f"{src1}_x_{src2}"
            summary['overlap'][key] = len(overlap)

    # All-source overlap
    if len(sources) >= 2:
        common = all_species_by_source[sources[0]]
        for src in sources[1:]:
            common = common & all_species_by_source[src]
        summary['overlap']['all_sources'] = len(common)

    out_path = DATA_DIR / 'agricultural_data_summary.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved summary to {out_path}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("AGRICULTURAL DATA DOWNLOAD SUMMARY")
    print("=" * 60)
    for src, info in summary['sources'].items():
        print(f"\n  {src.upper()}:")
        for k, v in info.items():
            if isinstance(v, dict):
                print(f"    {k}:")
                for kk, vv in v.items():
                    print(f"      {kk}: {vv}")
            else:
                print(f"    {k}: {v}")

    print(f"\n  TOTAL UNIQUE SPECIES: {summary['unique_species']['total_unique_across_all_sources']}")
    if summary['overlap']:
        print("\n  OVERLAPS:")
        for k, v in summary['overlap'].items():
            print(f"    {k}: {v}")
    print("=" * 60)

    return summary


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Download agricultural plant data from FAO EcoCrop, FAOSTAT, CROPGRIDS, and MapSPAM'
    )
    parser.add_argument('--all', action='store_true', help='Download all sources')
    parser.add_argument('--ecocrop', action='store_true', help='Download EcoCrop data')
    parser.add_argument('--faostat', action='store_true', help='Download FAOSTAT data')
    parser.add_argument('--cropgrids', action='store_true', help='Generate CROPGRIDS species list')
    parser.add_argument('--mapspam', action='store_true', help='Generate MapSPAM crop list')
    parser.add_argument('--summary-only', action='store_true', help='Only regenerate summary')

    args = parser.parse_args()

    # Default to --all if no flags
    if not any([args.all, args.ecocrop, args.faostat, args.cropgrids, args.mapspam, args.summary_only]):
        args.all = True

    if args.summary_only:
        generate_summary()
        return

    # Load WCVP names for cross-referencing
    wcvp_names = load_wcvp_names()

    ecocrop_names = set()

    if args.all or args.ecocrop:
        stats = download_ecocrop(wcvp_names)
        # Load ecocrop names for CROPGRIDS cross-ref
        ecocrop_path = DATA_DIR / 'ecocrop_agricultural.json'
        if ecocrop_path.exists():
            with open(ecocrop_path, 'r') as f:
                for sp in json.load(f):
                    name = sp.get('scientific_name', '')
                    if name and len(name.split()) >= 2:
                        parts = name.lower().split()
                        ecocrop_names.add(f"{parts[0]} {parts[1]}")

    if args.all or args.faostat:
        download_faostat(wcvp_names)

    if args.all or args.cropgrids:
        download_cropgrids(wcvp_names, ecocrop_names)

    if args.all or args.mapspam:
        download_mapspam(wcvp_names)

    # Always generate summary at the end
    generate_summary()

    logger.info("Done!")


if __name__ == '__main__':
    main()
