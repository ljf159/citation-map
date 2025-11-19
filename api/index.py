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
geolocator = Nominatim(user_agent="citation-map-app-v3")

# Cache for geocoding results
geocode_cache = {}

# Semantic Scholar API base URL
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

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

def search_author_by_name(name):
    """Search for an author by name using Semantic Scholar API."""
    try:
        url = f"{SEMANTIC_SCHOLAR_API}/author/search"
        params = {
            'query': name,
            'limit': 1,
            'fields': 'authorId,name,affiliations,paperCount,citationCount,hIndex'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('data') and len(data['data']) > 0:
            return data['data'][0]
        return None
    except Exception as e:
        logger.error(f"Error searching author: {e}")
        return None

def get_author_by_id(author_id):
    """Get author details by Semantic Scholar author ID."""
    try:
        url = f"{SEMANTIC_SCHOLAR_API}/author/{author_id}"
        params = {
            'fields': 'authorId,name,affiliations,paperCount,citationCount,hIndex,papers.paperId,papers.title,papers.year,papers.citationCount'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting author by ID: {e}")
        return None

def get_paper_citations(paper_id, limit=10):
    """Get citations for a paper."""
    try:
        url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
        params = {
            'fields': 'authors,authors.name,authors.affiliations,title,year',
            'limit': limit
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get('data', [])
    except Exception as e:
        logger.warning(f"Error getting citations for paper {paper_id}: {e}")
        return []

def extract_author_identifier(url_or_name):
    """Extract author identifier from URL or use as name."""
    # Check if it's a Semantic Scholar URL
    ss_match = re.search(r'semanticscholar\.org/author/[^/]+/(\d+)', url_or_name)
    if ss_match:
        return ('id', ss_match.group(1))

    # Check if it's a Google Scholar URL (extract name from it or use ID)
    gs_match = re.search(r'user=([a-zA-Z0-9_-]+)', url_or_name)
    if gs_match:
        # We can't use Google Scholar ID directly, return None to show error
        return ('gs_id', gs_match.group(1))

    # Treat as author name
    return ('name', url_or_name.strip())

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'api': 'Semantic Scholar'
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
    """Analyze an author's citations using Semantic Scholar API."""
    data = request.json
    query = data.get('url', '').strip()
    max_papers = min(data.get('max_papers', 3), 10)
    max_citations_per_paper = min(data.get('max_citations', 5), 20)

    if not query:
        return jsonify({'error': 'Please enter an author name or Semantic Scholar URL'}), 400

    identifier_type, identifier = extract_author_identifier(query)

    # Handle Google Scholar URL
    if identifier_type == 'gs_id':
        return jsonify({
            'error': 'Google Scholar URLs are not supported due to access restrictions. Please enter the author\'s name directly (e.g., "Geoffrey Hinton") or use a Semantic Scholar URL.'
        }), 400

    logger.info(f"Analyzing author: {identifier} (type: {identifier_type})")

    # Get author info
    author = None
    if identifier_type == 'id':
        author = get_author_by_id(identifier)
    else:
        # Search by name
        search_result = search_author_by_name(identifier)
        if search_result:
            author = get_author_by_id(search_result['authorId'])

    if not author:
        return jsonify({
            'error': f'Could not find author: {identifier}. Please check the spelling or try a different name.'
        }), 404

    # Get affiliation
    affiliations = author.get('affiliations', [])
    affiliation = affiliations[0] if affiliations else 'Unknown'

    result = {
        'author': {
            'name': author.get('name', 'Unknown'),
            'affiliation': affiliation,
            'citations': author.get('citationCount', 0),
            'h_index': author.get('hIndex', 0),
        },
        'publications': [],
        'citing_authors': [],
        'locations': []
    }

    # Get papers
    papers = author.get('papers', [])
    # Sort by citation count and take top papers
    papers = sorted(papers, key=lambda x: x.get('citationCount', 0) or 0, reverse=True)[:max_papers]

    all_citing_authors = []
    affiliations_map = {}

    for i, paper in enumerate(papers):
        logger.info(f"Processing paper {i + 1}/{len(papers)}: {paper.get('title', 'Unknown')[:50]}")

        pub_info = {
            'title': paper.get('title', 'Unknown'),
            'year': str(paper.get('year', 'Unknown')),
            'citations': paper.get('citationCount', 0) or 0
        }
        result['publications'].append(pub_info)

        # Get citations for this paper
        paper_id = paper.get('paperId')
        if paper_id and pub_info['citations'] > 0:
            citations = get_paper_citations(paper_id, max_citations_per_paper)

            for citation in citations:
                citing_paper = citation.get('citingPaper', {})
                authors = citing_paper.get('authors', [])

                for citing_author in authors[:2]:  # Limit to first 2 authors per paper
                    author_name = citing_author.get('name', '')
                    author_affiliations = citing_author.get('affiliations', [])
                    affiliation = author_affiliations[0] if author_affiliations else ''

                    if author_name:
                        citing_info = {
                            'name': author_name,
                            'affiliation': affiliation,
                            'paper_title': citing_paper.get('title', 'Unknown'),
                            'year': str(citing_paper.get('year', 'Unknown'))
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

            time.sleep(0.2)  # Rate limiting

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
