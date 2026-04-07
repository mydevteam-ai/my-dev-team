from pydantic import BaseModel, Field

class LoadSkill(BaseModel):
    """Call this tool to load specialized framework rules and architectural best practices before writing code. You can load multiple skills at once."""
    skill_names: list[str] = Field(
        min_length=1,
        description="The exact name(s) of the module(s) to load, as listed in the <skills> section of your prompt (e.g. ['python-expert'] or ['react-expert', 'tailwind-expert'])."
    )

class RetrieveContext(BaseModel):
    """Retrieve relevant context from the knowledge base (documents, Jira tickets, Confluence pages, etc.)."""
    query: str = Field(description="Natural language description of the information you need.")
    source: str | None = Field(
        default=None,
        description="Restrict search to a specific source, e.g. 'jira', 'confluence', or 'files'. Sources with a dedicated MCP server are queried directly; others are used as a filter against the default knowledge base. Omit to search all sources."
    )

class ReadFile(BaseModel):
    """Read the contents of a file from the project workspace. Use this when you need to see a file that is not shown in your current context."""
    path: str = Field(
        description="The relative path to the file in the workspace (e.g. 'src/main.py' or 'tests/test_main.py')."
    )

class ListFiles(BaseModel):
    """List all files currently available in the project workspace."""

class GlobFiles(BaseModel):
    """Find workspace files matching a glob pattern (e.g. '*.py', 'src/**/*.test.js', 'config/*.yaml')."""
    pattern: str = Field(
        description="Glob pattern to match file paths against (e.g. '*.py', 'src/**/*.ts', 'tests/*')."
    )

class GrepFiles(BaseModel):
    """Search workspace file contents for a regex pattern and return matching lines."""
    pattern: str = Field(
        description="Regex pattern to search for in file contents."
    )
    glob: str | None = Field(
        default=None,
        description="Optional glob pattern to filter which files to search (e.g. '*.py'). Omit to search all files."
    )
