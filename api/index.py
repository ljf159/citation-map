from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from scholarly import scholarly, ProxyGenerator
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import re
import time
import logging
import os
import random

# Get the correct template folder path
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize geocoder with custom user agent
geolocator = Nominatim(user_agent="citation-map-app-v2")

# Cache for geocoding results
geocode_cache = {}

# Setup proxy for scholarly to avoid being blocked
def setup_scholarly_proxy():
    """Setup proxy for scholarly to bypass Google Scholar blocking."""
    try:
        pg = ProxyGenerator()
        # Use free proxies
        success = pg.FreeProxies()
        if success:
            scholarly.use_proxy(pg)
            logger.info("Proxy setup successful")
            return True
    except Exception as e:
        logger.warning(f"Could not setup proxy: {e}")
    return False

# Try to setup proxy on startup
proxy_enabled = setup_scholarly_proxy()

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

def geocode_institution(institution):
    """Geocode an institution name to coordinates."""
    if not institution or institution.strip() == '':
        return None

    # Clean the institution name
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

def get_author_info(author_id, retries=3):
    """Get author information from Google Scholar with retries."""
    for attempt in range(retries):
        try:
            logger.info(f"Fetching author {author_id}, attempt {attempt + 1}")
            author = scholarly.search_author_id(author_id)
            author = scholarly.fill(author, sections=['basics', 'publications'])
            logger.info(f"Successfully fetched author: {author.get('name', 'Unknown')}")
            return author
        except Exception as e:
            logger.error(f"Error fetching author info (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                # Try to reset proxy
                setup_scholarly_proxy()
    return None

def get_citing_authors_simple(publication, max_citations=5):
    """Get citing authors with simplified approach."""
    citing_authors = []

    try:
        # Fill publication to get citations
        pub_filled = scholarly.fill(publication)

        # Get citations for this publication
        citations = scholarly.citedby(pub_filled)

        count = 0
        for citation in citations:
            if count >= max_citations:
                break

            try:
                bib = citation.get('bib', {})
                author_str = bib.get('author', '')

                if author_str:
                    # Parse authors
                    authors = author_str.split(' and ')
                    for author_name in authors[:2]:  # Limit to first 2 authors
                        author_name = author_name.strip()
                        if author_name and len(author_name) > 1:
                            citing_author = {
                                'name': author_name,
                                'paper_title': bib.get('title', 'Unknown'),
                                'year': bib.get('pub_year', 'Unknown'),
                                'affiliation': ''
                            }
                            citing_authors.append(citing_author)

                count += 1
                time.sleep(0.3)  # Small delay between citations

            except Exception as e:
                logger.warning(f"Error processing citation: {e}")
                continue

    except Exception as e:
        logger.warning(f"Error getting citations: {e}")

    return citing_authors

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
    # Sample demo data
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
    max_papers = min(data.get('max_papers', 3), 5)  # Limit to 5 papers max
    max_citations_per_paper = min(data.get('max_citations', 5), 10)  # Limit to 10 citations max

    # Extract author ID from URL
    author_id = extract_author_id(scholar_url)
    if not author_id:
        return jsonify({'error': 'Invalid Google Scholar URL. Please use a URL like: https://scholar.google.com/citations?user=XXXXX'}), 400

    logger.info(f"Starting analysis for author ID: {author_id}")

    # Get author information
    author = get_author_info(author_id)
    if not author:
        return jsonify({
            'error': 'Could not fetch author information. Google Scholar may be blocking requests. Try the Demo button to see how the app works.'
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

    # Process publications
    publications = author.get('publications', [])[:max_papers]

    all_citing_authors = []
    affiliations = {}

    for i, pub in enumerate(publications):
        logger.info(f"Processing publication {i + 1}/{len(publications)}")

        pub_info = {
            'title': pub.get('bib', {}).get('title', 'Unknown'),
            'year': pub.get('bib', {}).get('pub_year', 'Unknown'),
            'citations': pub.get('num_citations', 0)
        }
        result['publications'].append(pub_info)

        # Get citing authors for this publication (only if it has citations)
        if pub.get('num_citations', 0) > 0:
            try:
                citing = get_citing_authors_simple(pub, max_citations_per_paper)
                for author_info in citing:
                    all_citing_authors.append(author_info)

                    # Track affiliations
                    affiliation = author_info.get('affiliation', '')
                    if affiliation:
                        if affiliation not in affiliations:
                            affiliations[affiliation] = {
                                'name': affiliation,
                                'count': 0,
                                'authors': []
                            }
                        affiliations[affiliation]['count'] += 1
                        affiliations[affiliation]['authors'].append(author_info['name'])
            except Exception as e:
                logger.warning(f"Error getting citations for publication: {e}")

        time.sleep(0.5)  # Delay between publications

    result['citing_authors'] = all_citing_authors

    # Geocode affiliations
    locations = []
    for affiliation, info in affiliations.items():
        coords = geocode_institution(affiliation)
        if coords:
            locations.append({
                'institution': affiliation,
                'lat': coords['lat'],
                'lng': coords['lng'],
                'count': info['count'],
                'authors': list(set(info['authors']))[:5]
            })

    result['locations'] = locations

    logger.info(f"Analysis complete. Found {len(all_citing_authors)} citing authors, {len(locations)} locations")

    return jsonify(result)

@app.route('/api/quick-analyze', methods=['POST'])
def quick_analyze():
    """Quick analysis - just get author info and publications."""
    data = request.json
    scholar_url = data.get('url', '')

    author_id = extract_author_id(scholar_url)
    if not author_id:
        return jsonify({'error': 'Invalid Google Scholar URL'}), 400

    # Get basic author info
    author = get_author_info(author_id)
    if not author:
        return jsonify({'error': 'Could not fetch author information. Google Scholar may be blocking requests.'}), 503

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

    # Get top publications
    publications = author.get('publications', [])[:10]
    for pub in publications:
        pub_info = {
            'title': pub.get('bib', {}).get('title', 'Unknown'),
            'year': pub.get('bib', {}).get('pub_year', 'Unknown'),
            'citations': pub.get('num_citations', 0)
        }
        result['publications'].append(pub_info)

    return jsonify(result)

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
