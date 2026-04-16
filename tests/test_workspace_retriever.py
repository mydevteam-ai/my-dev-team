import pytest
from devteam.utils.retriever import retrieve_workspace_context, retrieve_skills_context, _tokenize


def _materialize(root, files: dict[str, str]) -> str:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    return str(root)


WORKSPACE_FILES = {
    'src/auth/login.py': 'def authenticate_user(username, password):\n    return check_credentials(username, password)\n',
    'src/auth/permissions.py': 'def check_role(user, role):\n    return role in user.roles\n',
    'src/models/user.py': 'class User:\n    def __init__(self, name, email):\n        self.name = name\n        self.email = email\n',
    'src/models/product.py': 'class Product:\n    def __init__(self, title, price):\n        self.title = title\n        self.price = price\n',
    'src/api/routes.py': 'def register_routes(app):\n    app.route("/users")(list_users)\n    app.route("/products")(list_products)\n',
    'src/api/middleware.py': 'def cors_middleware(request):\n    return add_cors_headers(request)\n',
    'src/utils/helpers.py': 'def format_currency(amount):\n    return f"${amount:.2f}"\n',
    'src/utils/validators.py': 'def validate_email(email):\n    return "@" in email\n',
    'tests/test_auth.py': 'def test_authenticate_user():\n    assert authenticate_user("admin", "pass")\n',
    'tests/test_models.py': 'def test_user_creation():\n    user = User("Alice", "alice@example.com")\n    assert user.name == "Alice"\n',
    'tests/test_api.py': 'def test_list_users():\n    response = client.get("/users")\n    assert response.status_code == 200\n',
    'tests/test_validators.py': 'def test_validate_email():\n    assert validate_email("a@b.com")\n',
    'README.md': '# My App\nA web application with auth and products.\n',
    'config/settings.yaml': 'debug: true\nport: 8080\n',
    'requirements.txt': 'flask\npydantic\n',
}


@pytest.fixture
def workspace_path(tmp_path):
    return _materialize(tmp_path, WORKSPACE_FILES)


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_splits_snake_case(self):
        tokens = _tokenize('authenticate_user')
        assert 'authenticate' in tokens
        assert 'user' in tokens

    def test_splits_camel_case(self):
        tokens = _tokenize('authenticateUser')
        assert 'authenticate' in tokens
        assert 'user' in tokens

    def test_splits_upper_camel_case(self):
        tokens = _tokenize('AuthenticateUser')
        assert 'authenticate' in tokens
        assert 'user' in tokens

    def test_splits_acronym_boundary(self):
        tokens = _tokenize('parseHTTPResponse')
        assert 'parse' in tokens
        assert 'http' in tokens
        assert 'response' in tokens

    def test_drops_short_tokens(self):
        tokens = _tokenize('a b cc dd')
        assert 'a' not in tokens
        assert 'b' not in tokens
        assert 'cc' in tokens
        assert 'dd' in tokens

    def test_lowercases(self):
        tokens = _tokenize('HELLO World')
        assert 'hello' in tokens
        assert 'world' in tokens


# ---------------------------------------------------------------------------
# retrieve_workspace_context
# ---------------------------------------------------------------------------

class TestRetrieveWorkspaceContext:
    def test_relevant_files_rank_higher(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'authenticate user login password', top_k=3)
        assert '--- FILE: src/auth/login.py ---' in result
        assert 'authenticate_user' in result

    def test_other_files_listed(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'authenticate user login', top_k=3)
        assert 'Other workspace files' in result
        assert 'paths only' in result

    def test_all_files_accounted_for(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'authenticate', top_k=3)
        retrieved_count = result.count('--- FILE:')
        assert retrieved_count == 3
        assert 'Other workspace files' in result

    def test_empty_workspace(self, tmp_path):
        result = retrieve_workspace_context(str(tmp_path), 'anything')
        assert 'No files exist' in result

    def test_empty_query_returns_all(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, '', top_k=5)
        file_count = result.count('--- FILE:')
        assert file_count == len(WORKSPACE_FILES)
        assert 'Other workspace files' not in result

    def test_top_k_limits_full_content(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'user model email', top_k=2)
        retrieved_count = result.count('--- FILE:')
        assert retrieved_count == 2

    def test_top_k_exceeds_file_count(self, tmp_path):
        files = {'a.py': 'hello', 'b.py': 'world'}
        path = _materialize(tmp_path, files)
        result = retrieve_workspace_context(path, 'hello', top_k=10)
        assert result.count('--- FILE:') == 2
        assert 'Other workspace files' not in result

    def test_product_query_finds_product_files(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'product title price catalog', top_k=3)
        assert '--- FILE: src/models/product.py ---' in result

    def test_no_workspace_path(self):
        result = retrieve_workspace_context('', 'anything')
        assert 'No files exist' in result

    def test_validator_query(self, workspace_path):
        result = retrieve_workspace_context(workspace_path, 'validate email address', top_k=3)
        assert '--- FILE: src/utils/validators.py ---' in result


# ---------------------------------------------------------------------------
# retrieve_skills_context
# ---------------------------------------------------------------------------

SKILLS_CATALOG = [
    {'name': 'python-expert', 'description': 'Python programming best practices and debugging'},
    {'name': 'react-expert', 'description': 'React components, hooks and state management'},
    {'name': 'flask-api', 'description': 'Flask REST API patterns and authentication middleware'},
    {'name': 'django-orm', 'description': 'Django models, querysets and database migrations'},
    {'name': 'docker-deploy', 'description': 'Docker containers, compose files and deployment'},
    {'name': 'sql-expert', 'description': 'SQL queries, indexing and database optimization'},
    {'name': 'typescript-expert', 'description': 'TypeScript types, generics and compiler configuration'},
    {'name': 'tailwind-css', 'description': 'Tailwind CSS utility classes and responsive design'},
    {'name': 'jest-testing', 'description': 'Jest unit testing, mocking and test coverage'},
    {'name': 'kubernetes', 'description': 'Kubernetes pods, services and cluster management'},
]


class TestRetrieveSkillsContext:
    def test_relevant_skills_rank_higher(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'Flask REST API authentication', top_k=3)
        assert '`flask-api`' in result
        assert 'Relevant skills' in result

    def test_other_skills_listed(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'Flask REST API', top_k=3)
        assert 'Other available skills' in result

    def test_all_skills_accounted_for(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'python', top_k=3)
        relevant_count = result.split('## Other')[0].count('- `')
        assert relevant_count == 3

    def test_empty_catalog(self):
        result = retrieve_skills_context([], 'anything')
        assert 'No skills available' in result

    def test_empty_query_returns_all(self):
        result = retrieve_skills_context(SKILLS_CATALOG, '')
        for skill in SKILLS_CATALOG:
            assert f"`{skill['name']}`" in result
        assert 'Other available skills' not in result

    def test_top_k_exceeds_catalog_size(self):
        small = [{'name': 'a', 'description': 'desc a'}, {'name': 'b', 'description': 'desc b'}]
        result = retrieve_skills_context(small, 'something', top_k=10)
        assert '`a`' in result
        assert '`b`' in result
        assert 'Other available skills' not in result

    def test_database_query_finds_sql_and_django(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'database queries and migrations', top_k=3)
        assert '`sql-expert`' in result or '`django-orm`' in result

    def test_react_query(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'React components hooks state', top_k=2)
        assert '`react-expert`' in result

    def test_top_k_limits_relevant_section(self):
        result = retrieve_skills_context(SKILLS_CATALOG, 'python testing', top_k=2)
        relevant_section = result.split('## Other')[0]
        relevant_count = relevant_section.count('- `')
        assert relevant_count == 2
