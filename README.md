# Citation Map

A web application that visualizes the global impact of academic research by mapping the locations of authors who cite a specific researcher's work on Google Scholar.

## Table of Contents

- [Description](#description)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [License](#license)

## Description

Citation Map allows researchers to see where their work is being cited around the world. By inputting a Google Scholar profile URL, the application analyzes the author's publications, retrieves citing papers, identifies the citing authors and their affiliations, and visualizes this data on an interactive world map.

## Features

- **Profile Analysis**: Automatically extracts author information from a Google Scholar profile URL.
- **Citation Network**: Retrieves data on publications and the authors who have cited them.
- **Affiliation Extraction**: Identifies the institutional affiliation of citing authors.
- **Geospatial Visualization**: Geocodes institution names to coordinates and displays them on a world map using Leaflet.js.
- **Statistics**: Provides summary statistics such as total citations and H-index.
- **Demo Mode**: Includes a demo mode to visualize sample data without making external API calls.

## Tech Stack

- **Backend**: Python, Flask
- **Data Retrieval**: `scholarly` (Google Scholar API wrapper)
- **Geocoding**: `geopy` + OpenStreetMap Nominatim
- **Frontend**: HTML5, CSS3, JavaScript
- **Maps**: Leaflet.js
- **Deployment**: Compatible with Vercel and Render

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Steps

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd citation-map
    ```

2.  **Create a virtual environment (Recommended)**:
    ```bash
    python -m venv venv
    # On Linux/macOS:
    source venv/bin/activate
    # On Windows:
    venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Local Development

1.  **Start the application**:
    ```bash
    python app.py
    ```

2.  **Access the app**:
    Open your web browser and navigate to `http://localhost:5000`.

3.  **Analyze a Profile**:
    - Go to Google Scholar (https://scholar.google.com).
    - Find the profile of the researcher you want to analyze.
    - Copy the URL from the browser address bar (e.g., `https://scholar.google.com/citations?user=XXXXXX`).
    - Paste the URL into the input box on the Citation Map app.
    - Click "Start Analysis".

### Notes
- The analysis process may take several minutes due to the need to scrape data from Google Scholar and geocode locations.
- Rate limiting is implemented to avoid being blocked by Google Scholar or the geocoding service.

## API Endpoints

### `POST /api/analyze`

Analyzes a Google Scholar profile.

**Request Body:**
```json
{
  "url": "https://scholar.google.com/citations?user=XXXXXX",
  "max_papers": 5,
  "max_citations": 10
}
```

**Response:**
```json
{
  "author": {
    "name": "Author Name",
    "affiliation": "Institution",
    "citations": 1234,
    "h_index": 25
  },
  "publications": [...],
  "citing_authors": [...],
  "locations": [
    {
      "institution": "University Name",
      "lat": 40.7128,
      "lng": -74.0060,
      "count": 5,
      "authors": ["Author A", "Author B"]
    }
  ]
}
```

### `POST /api/demo`

Returns sample data for demonstration purposes.

### `GET /api/health`

Health check endpoint to verify if the service is running and if the proxy is enabled.

## License

MIT License
