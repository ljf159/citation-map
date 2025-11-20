"""
Citation Map Application.

This module defines a Flask web application for visualizing Google Scholar citation networks.
It provides endpoints to analyze author profiles, fetch publication data, and geocode
citing authors' affiliations to display them on a world map.

Attributes:
    app (Flask): The Flask application instance.
    logger (logging.Logger): Logger for the application.
    geolocator (Nominatim): Geocoding service instance.
    geocode_cache (dict): Cache for storing geocoded institution coordinates.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from scholarly import scholarly
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize geocoder with custom user agent
geolocator = Nominatim(user_agent="citation-map-app")

# Cache for geocoding results
geocode_cache = {}

def extract_author_id(url):
    """
    Extract the Google Scholar author ID from a given URL.

    Parses the provided URL to find the 'user' parameter which corresponds
    to the Google Scholar author ID.

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

@lru_cache(maxsize=1000)
def geocode_institution(institution):
    """
    Geocode an institution name to its geographical coordinates.

    Uses the Nominatim geocoding service to find the latitude and longitude
    of a given institution or address. Results are cached to improve performance
    and reduce API calls.

    Args:
        institution (str): The name of the institution or address to geocode.

    Returns:
        dict or None: A dictionary containing 'lat', 'lng', and 'address' if successful,
                      otherwise None.
    """
    if not institution or institution.strip() == '':
        return None

    # Clean the institution name
    institution = institution.strip()

    # Check cache first
    if institution in geocode_cache:
        return geocode_cache[institution]

    try:
        time.sleep(1)  # Rate limiting for Nominatim
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
    specified author ID.

    Args:
        author_id (str): The Google Scholar author ID.

    Returns:
        dict or None: A dictionary containing author details if successful,
                      otherwise None.
    """
    try:
        author = scholarly.search_author_id(author_id)
        author = scholarly.fill(author, sections=['basics', 'publications'])
        return author
    except Exception as e:
        logger.error(f"Error fetching author info: {e}")
        return None

def get_citing_authors(publication, max_citations=20):
    """
    Retrieve a list of authors who have cited a specific publication.

    Fetches the list of papers citing the given publication, extracts the
    authors of those papers, and attempts to determine their affiliations.

    Args:
        publication (dict): The publication object from scholarly.
        max_citations (int, optional): The maximum number of citing papers to process.
                                       Defaults to 20.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains
                    information about a citing author (name, paper_title,
                    year, affiliation).
    """
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
                # Get author information from citing paper
                if 'author' in citation:
                    authors = citation.get('author', '').split(' and ')
                    for author_name in authors[:3]:  # Limit to first 3 authors
                        author_name = author_name.strip()
                        if author_name:
                            citing_author = {
                                'name': author_name,
                                'paper_title': citation.get('bib', {}).get('title', 'Unknown'),
                                'year': citation.get('bib', {}).get('pub_year', 'Unknown'),
                                'affiliation': ''
                            }

                            # Try to find author profile for affiliation
                            try:
                                search_query = scholarly.search_author(author_name)
                                author_result = next(search_query, None)
                                if author_result:
                                    citing_author['affiliation'] = author_result.get('affiliation', '')
                            except:
                                pass

                            citing_authors.append(citing_author)

                count += 1
            except Exception as e:
                logger.warning(f"Error processing citation: {e}")
                continue

    except Exception as e:
        logger.warning(f"Error getting citations: {e}")

    return citing_authors

@app.route('/')
def index():
    """
    Render the main landing page of the application.

    Returns:
        str: The rendered HTML content of the index page.
    """
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_scholar():
    """
    Analyze a Google Scholar profile and return citation data.

    Endpoint to process a Google Scholar URL. It extracts the author's info,
    publications, and citing authors, then geocodes the affiliations of the
    citing authors.

    JSON Payload:
        url (str): The Google Scholar profile URL.
        max_papers (int, optional): Max number of papers to analyze. Defaults to 5.
        max_citations (int, optional): Max citations per paper to analyze. Defaults to 10.

    Returns:
        Response: A JSON response containing:
            - author (dict): Author details (name, affiliation, etc.).
            - publications (list): List of author's publications.
            - citing_authors (list): List of authors who cited the publications.
            - locations (list): Geocoded locations of citing institutions.
    """
    data = request.json
    scholar_url = data.get('url', '')
    max_papers = data.get('max_papers', 5)
    max_citations_per_paper = data.get('max_citations', 10)

    # Extract author ID from URL
    author_id = extract_author_id(scholar_url)
    if not author_id:
        return jsonify({'error': 'Invalid Google Scholar URL'}), 400

    # Get author information
    author = get_author_info(author_id)
    if not author:
        return jsonify({'error': 'Could not fetch author information'}), 404

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

    for pub in publications:
        pub_info = {
            'title': pub.get('bib', {}).get('title', 'Unknown'),
            'year': pub.get('bib', {}).get('pub_year', 'Unknown'),
            'citations': pub.get('num_citations', 0)
        }
        result['publications'].append(pub_info)

        # Get citing authors for this publication
        if pub.get('num_citations', 0) > 0:
            citing = get_citing_authors(pub, max_citations_per_paper)
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
                'authors': list(set(info['authors']))[:5]  # Unique authors, max 5
            })

    result['locations'] = locations

    return jsonify(result)

@app.route('/api/quick-analyze', methods=['POST'])
def quick_analyze():
    """
    Perform a quick analysis of a Google Scholar profile.

    This endpoint is similar to `analyze_scholar` but is optimized for speed
    or testing. It fetches basic author info and a limited number of publications
    without deep citation analysis.

    JSON Payload:
        url (str): The Google Scholar profile URL.

    Returns:
        Response: A JSON response containing author details and a list of publications.
    """
    data = request.json
    scholar_url = data.get('url', '')

    author_id = extract_author_id(scholar_url)
    if not author_id:
        return jsonify({'error': 'Invalid Google Scholar URL'}), 400

    # Get basic author info
    author = get_author_info(author_id)
    if not author:
        return jsonify({'error': 'Could not fetch author information'}), 404

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
