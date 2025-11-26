# EchoScope

**GEO Engine for AI Visibility**  
*Powered by AN2B*

EchoScope is a web application that helps businesses understand how often they're being recommended by AI assistants like ChatGPT. It analyzes "AI visibility" by running predefined queries against OpenAI's models and measuring whether your business is mentioned and recommended.

## Features

- **Tenant-based Analysis**: Select from configured business tenants (A-D Roofing or Better Pak)
- **AI Visibility Scoring**: Automated scoring system (0-2 scale) for each query
- **Competitor Tracking**: See which competitors are being recommended alongside or instead of your business
- **GEO Recommendations**: Receive 5-10 actionable content recommendations to improve AI visibility

## Scoring System

Each query is scored on a 0-2 scale:

- **0**: Your business was NOT mentioned in the AI recommendations
- **1**: Your business was mentioned, but NOT as the primary/first recommendation
- **2**: Your business was the PRIMARY (first) recommendation

## Setup and Installation

### Prerequisites

- Python 3.11+
- OpenAI API key

### Installation Steps

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your OpenAI API key**:
   
   On Replit, use the Secrets manager to add:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
   
   Or set it as an environment variable:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

4. **Run the application**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 5000
   ```

5. **Open the web interface**:
   Navigate to the provided URL and select a tenant, then click "Run GEO Analysis"

## Configuration

### Editing Tenants

You can add or modify business tenants by editing `data/tenants.json`. Each tenant requires:

- `id`: Unique identifier
- `display_name`: Human-readable name shown in the UI
- `domains`: List of website URLs for the business
- `brand_aliases`: List of name variations to match in AI recommendations
- `geo_focus`: Geographic areas of operation
- `priority_queries`: List of "money questions" to test

Example:
```json
{
  "my_business": {
    "id": "my_business",
    "display_name": "My Business Name",
    "domains": ["https://mybusiness.com"],
    "brand_aliases": ["My Business", "MyBusiness"],
    "geo_focus": ["New York, NY"],
    "priority_queries": [
      "best service provider in New York",
      "top rated company in NYC"
    ]
  }
}
```

## How It Works

1. **Query Execution**: For each priority query, EchoScope asks OpenAI to recommend 3-5 businesses as if responding to a customer
2. **Brand Matching**: The system compares AI recommendations against your brand aliases (case-insensitive)
3. **Scoring**: Each query receives a 0-2 score based on mention status and ranking
4. **Analysis Summary**: Aggregate metrics show overall AI visibility
5. **Recommendations**: OpenAI generates 5-10 GEO optimization suggestions based on the results

## Project Structure

```
/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── data/
│   └── tenants.json       # Tenant configuration
├── services/
│   └── analysis.py        # OpenAI integration and scoring logic
├── templates/
│   └── index.html         # Main web interface
├── static/
│   └── styles.css         # Application styling
└── README.md              # This file
```

## Technology Stack

- **FastAPI**: Modern Python web framework
- **Uvicorn**: ASGI server
- **Jinja2**: Template engine
- **OpenAI API**: AI-powered business recommendations
- **Python 3.11**: Programming language

## License

This is a V1 production prototype. All rights reserved.
