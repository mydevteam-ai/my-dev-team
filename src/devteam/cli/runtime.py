import asyncio
import logging
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich import print # pylint: disable=redefined-builtin
from devteam import settings
from devteam.crew import CrewFactory
from devteam.utils import LLMFactory, StreamHandler, TelemetryTracker, generate_thread_id, add_file_handler, remove_file_handler, create_serde
from devteam.utils.workspace import hydrate_workspace
from .extensions import build_extensions
from .request import RunHooks, RunRequest, ResumeRequest, StartRequest

logger = logging.getLogger(__name__)

STATE_DB_FILE = 'state.db'

async def show_history(thread_id: str):
    project_folder = settings.workspace_dir / thread_id
    db_path = project_folder / STATE_DB_FILE
    llm_factory = LLMFactory(provider='ollama')
    crew_factory = CrewFactory(llm_factory=llm_factory)
    async with aiosqlite.connect(db_path) as conn:
        checkpointer = AsyncSqliteSaver(conn, serde=create_serde())
        crew = crew_factory.create(project_folder, checkpointer=checkpointer)
        logger.info("Fetching timeline history...")
        history_data = await crew.get_history(thread_id)
        for checkpoint in history_data:
            print(
                f"[{checkpoint['time']}] "
                f"Checkpoint: {checkpoint['c_id']} | Next: {checkpoint['node']}"
            )

WORKFLOW_CREW = {
    'development': 'basic.yaml',
    'migration': 'migration.yaml'
}

def resolve_thread_id(request: RunRequest) -> str:
    if isinstance(request, ResumeRequest):
        return request.resume_thread
    return generate_thread_id(request.project_name)

async def run(request: RunRequest, thread_id: str, hooks: RunHooks | None = None):
    hooks = hooks or RunHooks()
    fanout = request.fanout or request.workflow.endswith('-fanout')
    workflow = request.workflow.removesuffix('-fanout')
    is_resume = isinstance(request, ResumeRequest)

    project_folder = settings.workspace_dir / thread_id
    project_folder.mkdir(parents=True, exist_ok=True)
    if isinstance(request, StartRequest) and request.seed_path:
        hydrate_workspace(request.seed_path, project_folder / 'workspace')

    llm_factory = LLMFactory(provider=request.provider, callbacks=hooks.callbacks)
    crew_factory = CrewFactory(llm_factory=llm_factory)
    async with aiosqlite.connect(project_folder / STATE_DB_FILE) as conn:
        checkpointer = AsyncSqliteSaver(conn, serde=create_serde())
        crew = crew_factory.create(
            project_folder,
            checkpointer=checkpointer,
            rpm=request.rpm,
            extensions=hooks.extensions,
            config_name=WORKFLOW_CREW.get(workflow, 'basic.yaml'),
            fanout=fanout,
        )
        return await crew.execute(
            thread_id=thread_id,
            requirements=None if is_resume else request.requirements,
            feedback=request.feedback if is_resume else None,
            feedback_source=request.feedback_source if is_resume else 'reviewer',
            checkpoint_id=request.checkpoint_id if is_resume else None,
        )

async def async_main(request: RunRequest):
    thread_id = resolve_thread_id(request)
    if isinstance(request, ResumeRequest):
        logger.info("Resuming existing project thread: %s", thread_id)
    else:
        logger.info("Starting new project: %s", request.project_name)

    project_folder = settings.workspace_dir / thread_id
    project_folder.mkdir(parents=True, exist_ok=True)
    log_handler = add_file_handler(project_folder / 'execution.log')
    telemetry = TelemetryTracker()
    callbacks = [telemetry]
    if settings.llm_streaming:
        callbacks.append(StreamHandler())
    hooks = RunHooks(callbacks=callbacks, extensions=build_extensions())

    logger.info("Starting AI Dev Team...")
    logger.info("Workspace: %s", project_folder.absolute())
    try:
        final_state = await run(request, thread_id, hooks)
        if final_state.abort_requested:
            print("❌ Workflow aborted by user or validation failure.")
            return
        if final_state.failed_tasks:
            print(f"⚠️  {len(final_state.failed_tasks)} task(s) were skipped due to agent errors:")
            for t in final_state.failed_tasks:
                print(f"   - {t}")
        if final_state.success:
            print("\n🎉 PROJECT COMPLETED SUCCESSFULLY!")
            print(final_state.final_report or "No report generated.")
            return
        print("🚨 RELEASE FAILED: Integration bugs found!")
        for bug in final_state.integration_bugs:
            print(f" - {bug}")
        print("\nNote: In a production system, these would be appended to the Phase 2 Backlog.")
    except KeyboardInterrupt:
        print(
            "\n\n🛑 Workflow interrupted by user (Ctrl+C)\n"
            "💡 You can resume this exact state later by running:\n"
            f"   devteam --resume {thread_id}"
        )
    except asyncio.CancelledError:
        print("🛑 Async execution cancelled")
    finally:
        print()
        print(telemetry.get_receipt_panel())
        print(telemetry.get_optimization_panel())
        print()
        remove_file_handler(log_handler)
