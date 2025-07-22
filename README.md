# Finks Naive

Natural language to MongoDB query converter using a multi-agent AI system. Transform plain English queries like "Find technology companies with high profit margins" into optimized MongoDB queries.

## Overview

Finks Naive uses a sophisticated multi-agent pipeline to understand natural language queries and convert them into precise MongoDB queries. The system employs five specialized AI agents working in concert:

1. **Field Extraction Agent** - Identifies relevant database fields from natural language
2. **Sorting Extraction Agent** - Determines sorting intent and direction
3. **Instruction Processing Agent** - Applies context-aware interpretation to fields
4. **Synthesis Agent** - Combines interpretations into a unified query structure
5. **Query Generation Agent** - Produces the final MongoDB query

## Tech Stack

- **Runtime**: Python 3.12
- **Framework**: FastAPI
- **AI**: Pydantic AI with Gemini/OpenAI models
- **Database**: MongoDB Atlas
- **Package Manager**: UV (ultra-fast Python package manager)
- **Deployment**: AWS Lambda + API Gateway (via Pulumi)
- **Architecture**: ARM64 (AWS Graviton2)

## Prerequisites

- Python 3.12+
- [UV](https://github.com/astral-sh/uv) package manager
- MongoDB Atlas cluster
- API keys for Gemini and/or OpenAI

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-org/finks-naive.git
cd finks-naive
```

### 2. Install UV (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Install dependencies
```bash
uv sync
```

### 4. Set up environment variables
Create a `.env` file in the project root:
```env
# AI API Keys
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# MongoDB Configuration
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net
MONGODB_DB_NAME=your_database_name

# AWS Configuration (for deployment)
AWS_REGION=ca-central-1
```

### 5. Run locally
```bash
# Start the FastAPI server
uv run uvicorn app.main:app --reload

# Or run the main script directly
uv run python main.py
```

The API will be available at `http://localhost:8000`

### 6. Test the API
```bash
# Test with a sample query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find technology companies with high profit margins",
    "max_results": 10
  }'
```

## Project Structure

```
finks-naive/
├── app/                      # Application code
│   ├── core/                # Core utilities (config, database, cache)
│   ├── modules/            
│   │   └── agents/         # AI agents implementation
│   │       ├── field_extraction/
│   │       ├── instruction_processing/
│   │       ├── sorting_extraction/
│   │       ├── synthesis/
│   │       └── query_generation/
│   └── main.py             # FastAPI application
├── config/                  # Configuration files
│   ├── field_mappings.yaml      # Field to collection mappings
│   ├── field_instructions.yaml  # Natural language interpretation rules
│   ├── field_categories.yaml    # Field categorization
│   └── unavailable_fields.yaml  # Fields pending implementation
├── scripts/                 # Utility scripts
│   ├── normalize_collections.py # Populate master_search collection
│   ├── process_vic_csv.py      # Generate field instructions from CSV
│   └── test_yaml_files.py      # Validate YAML configurations
├── tests/                   # Test files
├── deployment_config.yaml   # AWS Lambda deployment settings
└── pyproject.toml          # UV/Python dependencies
```

## Configuration

All configuration files use YAML format for better readability and documentation:

- **field_mappings.yaml**: Maps field names to MongoDB collections
- **field_instructions.yaml**: Provides AI guidance for interpreting user queries
- **field_categories.yaml**: Groups fields into categories with selection rules
- **unavailable_fields.yaml**: Lists fields that need future implementation

## Development

### Running Tests
```bash
# Run unit tests
uv run pytest

# Test YAML configuration validity
uv run python scripts/test_yaml_files.py

# Test the complete pipeline
uv run python test_sequential_simple.py --fresh
```

### Adding New Fields
1. Add field mapping to `config/field_mappings.yaml`
2. Add interpretation instructions to `config/field_instructions.yaml`
3. Categorize the field in `config/field_categories.yaml`
4. Run normalization to update master_search collection:
   ```bash
   uv run python scripts/normalize_collections.py
   ```

### Processing CSV Data
To update field instructions from a CSV file:
```bash
uv run python scripts/process_vic_csv.py
```

## Deployment with Pulumi

This project uses Pulumi for infrastructure as code deployment to AWS Lambda.

### Prerequisites
- AWS CLI configured with appropriate credentials
- Pulumi CLI installed
- AWS account with permissions for Lambda, API Gateway, and CloudWatch

### Initial Setup
```bash
# Install Pulumi
curl -fsSL https://get.pulumi.com | sh

# Login to Pulumi (using local backend)
pulumi login --local

# Or login to Pulumi Cloud
pulumi login
```

### Deploy to a Stack

#### Development Environment
```bash
cd pulumi
pulumi stack init dev
pulumi config set aws:region ca-central-1
pulumi up
```

#### Staging Environment
```bash
cd pulumi
pulumi stack select staging
pulumi config set aws:region ca-central-1
pulumi config set finks-naive:environment staging
pulumi up
```

#### Production Environment
```bash
cd pulumi
pulumi stack select production
pulumi config set aws:region ca-central-1
pulumi config set finks-naive:environment production
pulumi config set finks-naive:reservedConcurrency 10
pulumi up
```

### Stack Management
```bash
# List all stacks
pulumi stack ls

# Switch between stacks
pulumi stack select dev

# View stack outputs (API endpoint, etc.)
pulumi stack output

# Destroy stack resources
pulumi destroy
```

### Deployment Configuration
See `deployment_config.yaml` for detailed Lambda and API Gateway settings including:
- Memory allocation and timeout settings
- Environment variables
- Caching configuration
- Monitoring and alerting
- Cost optimization strategies

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Main Endpoints

#### POST /api/v1/query
Convert natural language to MongoDB query
```json
{
  "query": "Find profitable tech companies",
  "max_results": 10,
  "use_cache": true
}
```

#### GET /health
Health check endpoint

## Performance Optimization

The system includes several optimization strategies:

1. **Parallel Agent Execution**: Field and sorting extraction run concurrently
2. **Multi-level Caching**: In-memory and MongoDB-based query caching
3. **Query Fingerprinting**: Normalizes queries for better cache hits
4. **Connection Pooling**: Optimized MongoDB connections for Lambda
5. **ARM Architecture**: Uses AWS Graviton2 for cost efficiency

## Monitoring

When deployed, the system provides CloudWatch metrics:
- Query processing time
- Cache hit rate
- Concurrent queries
- Error rates

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary and confidential.

## Support

For issues and questions:
- Check the [deployment documentation](./deployment_config.yaml)
- Review the [API documentation](#api-documentation)
- Contact the development team