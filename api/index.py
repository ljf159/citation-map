from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from scholarly import scholarly, ProxyGenerator
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests
import re
import time
import random
import logging
import os

# Get the correct template folder path
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize geocoder with custom user agent
geolocator = Nominatim(user_agent="citation-map-app-v5")

# Cache for geocoding results
geocode_cache = {}

# Cache for author affiliations
author_cache = {}

# Setup proxy for scholarly
def setup_proxy():
    """Setup proxy for scholarly to bypass Google Scholar blocking."""
    try:
        pg = ProxyGenerator()
        success = pg.FreeProxies()
        if success:
            scholarly.use_proxy(pg)
            logger.info("Proxy setup successful")
            return True
    except Exception as e:
        logger.warning(f"Could not setup proxy: {e}")
    return False

# Try to setup proxy on startup
proxy_enabled = setup_proxy()

def clean_affiliation(affiliation_string):
    """Clean affiliation string to extract institution name."""
    if not affiliation_string:
        return ''

    # Split by common delimiters
    parts = re.split(r'[;,]|\band\b', affiliation_string)

    # Take the first meaningful part
    for part in parts:
        part = part.strip()
        # Remove titles and positions
        cleaned = re.sub(r'.*?\bat\b|.*?@', '', part, flags=re.IGNORECASE).strip()
        # Skip if it's just a title
        if re.search(r'\b(director|manager|chair|engineer|professor|lecturer|phd|postdoc|student|researcher)\b',
                     cleaned, re.IGNORECASE):
            continue
        if len(cleaned) > 3:
            return cleaned

    return affiliation_string.strip()

def geocode_institution(institution):
    """Geocode an institution name to coordinates."""
    if not institution or institution.strip() == '':
        return None

    institution = institution.strip()

    # Check cache first
    if institution in geocode_cache:
        return geocode_cache[institution]

    try:
        time.sleep(0.5)  # Rate limiting for Nominatim
        location = geolocator.geocode(institution, timeout=10)
        if location:
            result = {
                'lat': location.latitude,
                'lng': location.longitude,
                'address': location.address
            }
            geocode_cache[institution] = result
            return result
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning(f"Geocoding failed for {institution}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error geocoding {institution}: {e}")

    geocode_cache[institution] = None
    return None

def get_author_info(author_id):
    """Get author information from Google Scholar with random delay."""
    try:
        time.sleep(random.uniform(1, 3))  # Random delay to avoid blocking
        author = scholarly.search_author_id(author_id)
        author = scholarly.fill(author, sections=['basics', 'publications'])
        return author
    except Exception as e:
        logger.error(f"Error fetching author info: {e}")
        return None

def get_publication_details(pub):
    """Fill publication details with random delay."""
    try:
        time.sleep(random.uniform(1, 3))
        return scholarly.fill(pub)
    except Exception as e:
        logger.warning(f"Error filling publication: {e}")
        return pub

def get_citing_papers(publication, max_citations=10):
    """Get papers that cite this publication."""
    citing_papers = []
    try:
        citations = scholarly.citedby(publication)
        count = 0
        for citation in citations:
            if count >= max_citations:
                break
            citing_papers.append(citation)
            count += 1
            time.sleep(random.uniform(0.5, 1.5))  # Small delay between citations
    except Exception as e:
        logger.warning(f"Error getting citations: {e}")
    return citing_papers

def get_author_affiliation(author_name):
    """Get affiliation for a citing author."""
    # Check cache first
    if author_name in author_cache:
        return author_cache[author_name]

    try:
        time.sleep(random.uniform(1, 3))
        search_query = scholarly.search_author(author_name)
        author_result = next(search_query, None)

        if author_result:
            affiliation = author_result.get('affiliation', '')
            # Clean the affiliation
            cleaned = clean_affiliation(affiliation)
            author_cache[author_name] = cleaned
            return cleaned
    except Exception as e:
        logger.warning(f"Error getting affiliation for {author_name}: {e}")

    author_cache[author_name] = ''
    return ''

def extract_author_id(url):
    """Extract Google Scholar author ID from URL."""
    patterns = [
        r'user=([a-zA-Z0-9_-]+)',
        r'citations\?.*user=([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'proxy_enabled': proxy_enabled
    })

@app.route('/api/demo', methods=['POST'])
def demo_analyze():
    """Demo endpoint with sample data."""
    result = {
        'author': {
            'name': 'Demo Author',
            'affiliation': 'Stanford University',
            'citations': 15000,
            'h_index': 45,
        },
        'publications': [
            {'title': 'Deep Learning for Natural Language Processing', 'year': '2020', 'citations': 500},
            {'title': 'Attention Mechanisms in Neural Networks', 'year': '2019', 'citations': 350},
            {'title': 'Transfer Learning in Computer Vision', 'year': '2018', 'citations': 280},
        ],
        'citing_authors': [
            {'name': 'John Smith', 'affiliation': 'MIT', 'paper_title': 'Advanced NLP', 'year': '2021'},
            {'name': 'Maria Garcia', 'affiliation': 'University of Oxford', 'paper_title': 'Neural Networks', 'year': '2021'},
            {'name': 'Wei Zhang', 'affiliation': 'Tsinghua University', 'paper_title': 'AI Research', 'year': '2020'},
            {'name': 'Anna Mueller', 'affiliation': 'ETH Zurich', 'paper_title': 'Machine Learning', 'year': '2020'},
            {'name': 'Takeshi Yamamoto', 'affiliation': 'University of Tokyo', 'paper_title': 'Deep Learning', 'year': '2019'},
        ],
        'locations': [
            {'institution': 'MIT', 'lat': 42.3601, 'lng': -71.0942, 'count': 5, 'authors': ['John Smith', 'Alice Brown']},
            {'institution': 'University of Oxford', 'lat': 51.7520, 'lng': -1.2577, 'count': 3, 'authors': ['Maria Garcia']},
            {'institution': 'Tsinghua University', 'lat': 40.0084, 'lng': 116.3266, 'count': 4, 'authors': ['Wei Zhang', 'Li Wang']},
            {'institution': 'ETH Zurich', 'lat': 47.3769, 'lng': 8.5417, 'count': 2, 'authors': ['Anna Mueller']},
            {'institution': 'University of Tokyo', 'lat': 35.7128, 'lng': 139.7621, 'count': 3, 'authors': ['Takeshi Yamamoto']},
            {'institution': 'Stanford University', 'lat': 37.4275, 'lng': -122.1697, 'count': 6, 'authors': ['Robert Lee']},
            {'institution': 'University of Cambridge', 'lat': 52.2053, 'lng': 0.1218, 'count': 2, 'authors': ['James Wilson']},
        ]
    }
    return jsonify(result)

@app.route('/api/analyze', methods=['POST'])
def analyze_scholar():
    """Analyze a Google Scholar profile and return citation data."""
    data = request.json
    scholar_url = data.get('url', '')
    max_papers = min(data.get('max_papers', 3), 5)  # Limit to reduce blocking risk
    max_citations_per_paper = min(data.get('max_citations', 5), 10)

    # Extract author ID from URL
    author_id = extract_author_id(scholar_url)
    if not author_id:
        return jsonify({
            'error': 'Invalid Google Scholar URL. Please use a URL like: https://scholar.google.com/citations?user=XXXXX'
        }), 400

    logger.info(f"Starting analysis for author ID: {author_id}")

    # Reset proxy before starting
    setup_proxy()

    # Get author information
    author = get_author_info(author_id)
    if not author:
        return jsonify({
            'error': 'Could not fetch author information. Google Scholar may be blocking requests. Please try again later or use Demo mode.'
        }), 503

    result = {
        'author': {
            'name': author.get('name', 'Unknown'),
            'affiliation': author.get('affiliation', 'Unknown'),
            'citations': author.get('citedby', 0),
            'h_index': author.get('hindex', 0),
        },
        'publications': [],
        'citing_authors': [],
        'locations': []
    }

    # Process publications (sorted by citations)
    publications = author.get('publications', [])
    publications = sorted(publications, key=lambda x: x.get('num_citations', 0), reverse=True)[:max_papers]

    all_citing_authors = []
    affiliations_map = {}

    for i, pub in enumerate(publications):
        logger.info(f"Processing publication {i + 1}/{len(publications)}")

        # Get full publication details
        pub_filled = get_publication_details(pub)

        pub_info = {
            'title': pub_filled.get('bib', {}).get('title', 'Unknown'),
            'year': pub_filled.get('bib', {}).get('pub_year', 'Unknown'),
            'citations': pub_filled.get('num_citations', 0)
        }
        result['publications'].append(pub_info)

        # Get citing papers
        if pub_info['citations'] > 0:
            citing_papers = get_citing_papers(pub_filled, max_citations_per_paper)

            for citing_paper in citing_papers:
                bib = citing_paper.get('bib', {})
                author_str = bib.get('author', '')

                if author_str:
                    # Parse first author
                    authors = author_str.split(' and ')
                    if authors:
                        author_name = authors[0].strip()

                        if author_name and len(author_name) > 1:
                            # Get affiliation for this author
                            affiliation = get_author_affiliation(author_name)

                            citing_info = {
                                'name': author_name,
                                'affiliation': affiliation,
                                'paper_title': bib.get('title', 'Unknown'),
                                'year': bib.get('pub_year', 'Unknown')
                            }
                            all_citing_authors.append(citing_info)

                            # Track affiliations for map
                            if affiliation:
                                if affiliation not in affiliations_map:
                                    affiliations_map[affiliation] = {
                                        'count': 0,
                                        'authors': []
                                    }
                                affiliations_map[affiliation]['count'] += 1
                                if author_name not in affiliations_map[affiliation]['authors']:
                                    affiliations_map[affiliation]['authors'].append(author_name)

    result['citing_authors'] = all_citing_authors

    # Geocode affiliations
    locations = []
    for affiliation, info in affiliations_map.items():
        coords = geocode_institution(affiliation)
        if coords:
            locations.append({
                'institution': affiliation,
                'lat': coords['lat'],
                'lng': coords['lng'],
                'count': info['count'],
                'authors': info['authors'][:5]
            })

    result['locations'] = locations

    logger.info(f"Analysis complete. Found {len(all_citing_authors)} citing authors, {len(locations)} locations")

    return jsonify(result)

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
