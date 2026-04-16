# Bookstore API

A small Flask bookstore backend with user accounts, a book catalog, orders and
personalised recommendations.

Modules:

- `src/auth/` - login, session, password hashing, two-factor authentication
- `src/models/` - SQLAlchemy ORM models (user, book, author, order, review)
- `src/api/` - Flask blueprints exposing REST endpoints
- `src/services/` - email delivery, payments, search, recommendations
- `src/utils/` - shared helpers (validators, formatters, structured logging)
- `tests/` - pytest suite covering each feature area
