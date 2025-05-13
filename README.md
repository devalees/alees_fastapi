# FastAPI ERP Project

A modern, FastAPI-based enterprise resource planning system with a focus on best practices, scalability, and maintainability.

## Features

- FastAPI-based REST API with automated documentation
- Modular architecture following domain-driven design principles
- Standardized error handling and response formats
- Asynchronous database operations with SQLAlchemy
- Redis caching for improved performance
- Comprehensive logging with request tracking
- Health check endpoints for monitoring
- Security-first approach with proper headers and CORS configuration

## Project Structure

The project follows a feature-based structure with clear separation of concerns:

```
app/
├── core/           # Core infrastructure, configurations, base classes
├── features/       # Feature-specific modules (users, products, etc.)
├── common_services/# Shared business logic or utilities
└── main.py         # FastAPI application instance
```

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/devalees/alees_fastapi.git
   cd alees_fastapi
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements/dev.txt
   ```

4. Create a `.env` file based on `.env.example` and configure your environment variables.

5. Run the application:
   ```
   uvicorn app.main:app --reload
   ```

## Development

This project uses a clear set of strategies for caching, API design, validation, and monitoring that are documented in the `docs/` directory.

## License

[MIT License](LICENSE) 