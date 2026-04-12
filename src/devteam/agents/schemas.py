from pydantic import BaseModel, Field, field_validator
from devteam.utils.sanitizer import normalize_workspace_content
from devteam.tools.schemas import LoadSkill, RetrieveContext, ReadFile, ListFiles, GlobFiles, GrepFiles

# pylint: disable=line-too-long

class ProductManagerResponse(BaseModel):
    clarification_question: str | None = Field(
        default=None,
        description="Provide exactly ONE clarifying question ONLY if the requirements are too vague to determine the tech stack or core features. Leave null if requirements are clear."
    )
    specs: str | None = Field(
        default=None,
        description="Provide detailed Technical Specifications ONLY if the requirements are clear. Must be formatted in clean Markdown with sections for architecture, features, acceptance criteria, constraints, and testing. MUST end with an '## Alignment Confirmation' section."
    )

class AskClarification(BaseModel):
    """Ask the stakeholder a clarifying question."""
    question: str = Field(description="A single clarifying question to ask the stakeholder.")

class SubmitSpecification(BaseModel):
    """Submit the completed Technical Specifications document."""
    specs: str = Field(
        description="Detailed Technical Specifications in clean Markdown with sections for architecture, features, acceptance criteria, constraints, and testing. MUST end with an '## Alignment Confirmation' section."
    )

class DevelopmentTask(BaseModel):
    task_name: str = Field(
        description="A clear, concise name for the task."
    )
    user_story: str = Field(
        description="The user story describing the 'why' and 'what' (e.g. 'As a user, I want to...')."
    )
    acceptance_criteria: list[str] = Field(
        min_length=1,
        description="A bulleted list of specific, testable conditions that must be met for this task to be considered complete."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="A list of task names that must be completed before this task can begin. Leave empty if this task has no dependencies."
    )

class SystemArchitectResponse(BaseModel):
    runtime: str = Field(description="The primary runtime environment for this project (e.g. 'python', 'node', 'java')")
    pending_tasks: list[DevelopmentTask] = Field(
        min_length=1,
        description="A sequential backlog of development tasks required to build the project."
    )

class SubmitArchitecture(SystemArchitectResponse):
    """Submit the development task backlog derived from the Technical Specifications."""

class CodeJudgeResponse(BaseModel):
    winner_index: int = Field(
        description="The integer index of the winning draft (e.g. 0, 1, or 2). Must be a valid index from the provided drafts."
    )

class SubmitWinner(CodeJudgeResponse):
    """Submit the index of the best code draft after evaluating all candidates."""

class WorkspaceFile(BaseModel):
    path: str = Field(
        description="The relative path to the file, including the filename and extension (e.g. 'src/main.py' or 'tests/test_main.py')."
    )
    content: str = Field(
        description="The ENTIRE, 100% complete source code or text for this file. NEVER use placeholders like '// ... existing code ...' or '# ... previous logic ...'. If you omit existing lines from a modified file, that logic will be permanently deleted."
    )

    @field_validator('content', mode='before')
    @classmethod
    def normalize_content(cls, value):
        if isinstance(value, str):
            return normalize_workspace_content(value)
        return value

class DeveloperResponse(BaseModel):
    workspace_files: list[WorkspaceFile] = Field(
        min_length=1,
        description="A list of files that were created or modified during this task. Do NOT include existing files from the workspace that do not need to be modified."
    )

class SubmitCode(DeveloperResponse):
    """Submit the code you have written or modified for the current task."""

class CodeReviewerResponse(BaseModel):
    review_feedback: str = Field(
        description="Must be exactly 'APPROVED' if the code perfectly meets all criteria. If it fails, provide a newline-separated list of bugs formatted exactly as: '- [File Path] - [Bug/Missing Logic]: Description of why it fails.'"
    )

class QAEngineerResponse(BaseModel):
    test_results: str = Field(
        description="Must be exactly 'PASSED' if the logic for the current task is completely sound, handles edge cases, and passes all simulated tests. If the logic fails, misses edge cases, or has poorly written tests, provide a detailed bug report containing failed test scenarios and referencing specific file paths, formatted with newlines."
    )

class FinalQAResponse(BaseModel):
    test_results: str = Field(
        description="Must be exactly 'PASSED' if the entire project meets all specifications, handles edge cases, and passes all integration checks. If it fails, provide a detailed bug report covering cross-module issues, missing features, and integration failures."
    )

class ApproveCode(BaseModel):
    """Approve the code when it perfectly meets all acceptance criteria for the current task."""

class ReportIssues(BaseModel):
    """Report issues when the code has bugs, missing logic, failing tests, or doesn't meet acceptance criteria."""
    feedback: str = Field(
        description="A detailed report of issues found, formatted as: '- [File Path] - [Issue]: Description of the problem.'"
    )

class ReporterResponse(BaseModel):
    final_report: str = Field(
        description="A detailed Final Markdown Report with sections for Executive Summary, Technical Architecture, Development & QA History, and Final Deliverables."
    )

class SubmitReport(ReporterResponse):
    """Submit the final stakeholder report after the project has concluded."""

class MigrationTask(BaseModel):
    task_name: str = Field(
        description="A short name for the task (e.g. 'Translate CALC-PAY paragraph')."
    )
    description: str = Field(
        description="What source unit to translate, what target file to produce and any key mapping decisions to apply."
    )
    acceptance_criteria: list[str] = Field(
        min_length=1,
        description="Specific, testable conditions the Migrator must satisfy (e.g. 'src/payroll.py exists', 'All edge cases covered by tests')."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="task_name values that must complete before this task can start. Leave empty when no dependency exists."
    )

class MigrationAnalysisResponse(BaseModel):
    runtime: str = Field(description="The target runtime environment for the migrated code (e.g. 'python', 'node', 'java')")
    specs: str = Field(description="A detailed Migration Analysis document in Markdown covering: source language/structure, target language, mapping decisions, idiom translations, and known risks.")
    pending_tasks: list[MigrationTask] = Field(
        min_length=1,
        description="A backlog of migration tasks, one per source unit (file, module, class or paragraph), designed for maximum parallel execution."
    )

class SubmitMigrationPlan(MigrationAnalysisResponse):
    """Submit the completed migration analysis and task backlog."""
