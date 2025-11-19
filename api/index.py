from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests
import re
import time
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
geolocator = Nominatim(user_agent="citation-map-app-v6")

# Cache for geocoding results
geocode_cache = {}

# OpenAlex API base URL
OPENALEX_API = "https://api.openalex.org"

def geocode_institution(institution):
    """Geocode an institution name to coordinates."""
    if not institution or institution.strip() == '':
        return None

    institution = institution.strip()

    # Check cache first
    if institution in geocode_cache:
        return geocode_cache[institution]

    try:
        time.sleep(0.3)  # Rate limiting for Nominatim
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

def extract_author_id_from_url(url):
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

def search_author_openalex(name):
    """Search for an author by name using OpenAlex API."""
    try:
        url = f"{OPENALEX_API}/authors"
        params = {
            'search': name,
            'per_page': 1,
            'mailto': 'citation-map@example.com'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('results') and len(data['results']) > 0:
            return data['results'][0]
        return None
    except Exception as e:
        logger.error(f"Error searching author: {e}")
        return None

def get_author_works(author_id, limit=10):
    """Get works (papers) by an author."""
    try:
        url = f"{OPENALEX_API}/works"
        params = {
            'filter': f'author.id:{author_id}',
            'sort': 'cited_by_count:desc',
            'per_page': limit,
            'mailto': 'citation-map@example.com'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        logger.error(f"Error getting author works: {e}")
        return []

def get_citing_works(work_id, limit=10):
    """Get works that cite a specific work."""
    try:
        url = f"{OPENALEX_API}/works"
        params = {
            'filter': f'cites:{work_id}',
            'per_page': limit,
            'mailto': 'citation-map@example.com'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        logger.warning(f"Error getting citing works: {e}")
        return []

def extract_institution_from_authorship(authorship):
    """Extract institution name from authorship data."""
    institutions = authorship.get('institutions', [])
    if institutions:
        return institutions[0].get('display_name', '')
    return ''

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'api': 'OpenAlex'
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
def analyze():
    """Analyze an author's citations using OpenAlex API."""
    data = request.json
    query = data.get('url', '').strip()
    max_papers = min(data.get('max_papers', 5), 10)
    max_citations_per_paper = min(data.get('max_citations', 10), 20)

    if not query:
        return jsonify({'error': 'Please enter an author name or Google Scholar URL'}), 400

    # Check if it's a Google Scholar URL
    gs_id = extract_author_id_from_url(query)
    if gs_id:
        # It's a Google Scholar URL - inform user to use author name instead
        return jsonify({
            'error': 'Google Scholar URLs cannot be used directly due to access restrictions. Please enter the author\'s name instead (e.g., "Geoffrey Hinton").'
        }), 400

    # Treat as author name and search in OpenAlex
    logger.info(f"Searching for author: {query}")

    author = search_author_openalex(query)
    if not author:
        return jsonify({
            'error': f'Could not find author: {query}. Please check the spelling or try a different name.'
        }), 404

    # Get author info
    author_id = author.get('id', '').replace('https://openalex.org/', '')
    author_name = author.get('display_name', 'Unknown')

    # Get affiliation
    last_known_institution = author.get('last_known_institution', {})
    affiliation = last_known_institution.get('display_name', 'Unknown') if last_known_institution else 'Unknown'

    result = {
        'author': {
            'name': author_name,
            'affiliation': affiliation,
            'citations': author.get('cited_by_count', 0),
            'h_index': author.get('summary_stats', {}).get('h_index', 0),
        },
        'publications': [],
        'citing_authors': [],
        'locations': []
    }

    # Get author's works
    works = get_author_works(author_id, max_papers)

    all_citing_authors = []
    affiliations_map = {}

    for i, work in enumerate(works):
        logger.info(f"Processing work {i + 1}/{len(works)}")

        pub_info = {
            'title': work.get('title', 'Unknown'),
            'year': str(work.get('publication_year', 'Unknown')),
            'citations': work.get('cited_by_count', 0)
        }
        result['publications'].append(pub_info)

        # Get citing works
        work_id = work.get('id', '').replace('https://openalex.org/', '')
        if work_id and pub_info['citations'] > 0:
            citing_works = get_citing_works(work_id, max_citations_per_paper)

            for citing_work in citing_works:
                # Get authors from citing work
                authorships = citing_work.get('authorships', [])

                # Only get first author
                if authorships:
                    authorship = authorships[0]
                    citing_author_name = authorship.get('author', {}).get('display_name', '')
                    citing_institution = extract_institution_from_authorship(authorship)

                    if citing_author_name:
                        citing_info = {
                            'name': citing_author_name,
                            'affiliation': citing_institution,
                            'paper_title': citing_work.get('title', 'Unknown'),
                            'year': str(citing_work.get('publication_year', 'Unknown'))
                        }
                        all_citing_authors.append(citing_info)

                        # Track affiliations for map
                        if citing_institution:
                            if citing_institution not in affiliations_map:
                                affiliations_map[citing_institution] = {
                                    'count': 0,
                                    'authors': []
                                }
                            affiliations_map[citing_institution]['count'] += 1
                            if citing_author_name not in affiliations_map[citing_institution]['authors']:
                                affiliations_map[citing_institution]['authors'].append(citing_author_name)

            time.sleep(0.1)  # Small rate limiting

    result['citing_authors'] = all_citing_authors

    # Geocode affiliations
    locations = []
    for institution, info in affiliations_map.items():
        coords = geocode_institution(institution)
        if coords:
            locations.append({
                'institution': institution,
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
