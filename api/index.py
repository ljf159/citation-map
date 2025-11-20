"""
Citation Map API Module.

This module provides the backend logic for the Citation Map application, specifically
tailored for serverless deployment (e.g., Vercel, Render). It handles Google Scholar
data extraction, proxy management, geocoding of institutions, and API endpoints for
analyzing citation networks.

Attributes:
    app (Flask): The Flask application instance.
    logger (logging.Logger): Logger for the application.
    geolocator (Nominatim): Geocoding service instance.
    geocode_cache (dict): Cache for storing geocoded institution coordinates.
    author_cache (dict): Cache for storing author affiliations.
    proxy_enabled (bool): Flag indicating if the proxy setup was successful.
"""

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
    """
    Configure a proxy for the `scholarly` library to bypass Google Scholar restrictions.

    Attempts to find and set up free proxies using `ProxyGenerator`.

    Returns:
        bool: True if proxy setup was successful, False otherwise.
    """
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
    """
    Clean and extract the institution name from an affiliation string.

    Removes titles, positions, and other noise to isolate the institution's name.

    Args:
        affiliation_string (str): The raw affiliation string (e.g., "Professor at MIT").

    Returns:
        str: The cleaned institution name, or the original string if no cleaning was applicable.
    """
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
    """
    Geocode an institution name to its geographical coordinates.

    Uses the Nominatim geocoding service to find the latitude and longitude
    of a given institution. Results are cached.

    Args:
        institution (str): The name of the institution to geocode.

    Returns:
        dict or None: A dictionary containing 'lat', 'lng', and 'address' if successful,
                      otherwise None.
    """
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
    """
    Fetch detailed information about an author from Google Scholar.

    Retrieves basic profile information and the list of publications for the
    specified author ID. Includes a random delay to avoid rate limiting.

    Args:
        author_id (str): The Google Scholar author ID.

    Returns:
        dict or None: A dictionary containing author details if successful,
                      otherwise None.
    """
    try:
        time.sleep(random.uniform(1, 3))  # Random delay to avoid blocking
        author = scholarly.search_author_id(author_id)
        author = scholarly.fill(author, sections=['basics', 'publications'])
        return author
    except Exception as e:
        logger.error(f"Error fetching author info: {e}")
        return None

def get_publication_details(pub):
    """
    Retrieve full details for a specific publication.

    Fills in additional details for a publication object using `scholarly`.
    Includes a random delay to avoid rate limiting.

    Args:
        pub (dict): The partial publication object.

    Returns:
        dict: The fully filled publication object, or the original object on error.
    """
    try:
        time.sleep(random.uniform(1, 3))
        return scholarly.fill(pub)
    except Exception as e:
        logger.warning(f"Error filling publication: {e}")
        return pub

def get_citing_papers(publication, max_citations=10):
    """
    Retrieve a list of papers that cite a given publication.

    Args:
        publication (dict): The publication object.
        max_citations (int, optional): The maximum number of citing papers to retrieve.
                                       Defaults to 10.

    Returns:
        list[dict]: A list of citing paper objects.
    """
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
    """
    Determine the affiliation of an author by name.

    Searches for the author on Google Scholar to find their affiliation.
    Results are cached and cleaned.

    Args:
        author_name (str): The name of the author.

    Returns:
        str: The cleaned affiliation string, or an empty string if not found.
    """
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
    """
    Extract the Google Scholar author ID from a given URL.

    Args:
        url (str): The full URL of the Google Scholar profile.

    Returns:
        str or None: The extracted author ID if found, otherwise None.
    """
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
    """
    Render the main landing page of the application.

    Returns:
        str: The rendered HTML content of the index page.
    """
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """
    Perform a health check of the API.

    Returns:
        Response: A JSON response indicating the status ('ok') and whether
                  the proxy is enabled.
    """
    return jsonify({
        'status': 'ok',
        'proxy_enabled': proxy_enabled
    })

@app.route('/api/demo', methods=['POST'])
def demo_analyze():
    """
    Provide a demo analysis with pre-defined sample data.

    This endpoint simulates the `analyze_scholar` response without making
    external API calls, useful for testing or demonstration purposes.

    Returns:
        Response: A JSON response containing sample author, publication,
                  citing authors, and location data.
    """
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
    """
    Analyze a Google Scholar profile and return citation data.

    This is the main analysis endpoint. It takes a profile URL, extracts data,
    finds citing papers and authors, and geocodes their affiliations.

    JSON Payload:
        url (str): The Google Scholar profile URL.
        max_papers (int, optional): Max number of papers to analyze. Defaults to 3 (capped at 5).
        max_citations (int, optional): Max citations per paper to analyze. Defaults to 5 (capped at 10).

    Returns:
        Response: A JSON response with comprehensive citation and location data.

    status codes:
        200: Success.
        400: Invalid URL.
        503: Service unavailable (e.g., Google Scholar blocking).
    """
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
