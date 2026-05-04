import asyncio
import logging
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich import print # pylint: disable=redefined-builtin
from devteam import settings
from devteam.crew import CrewFactory
from devteam.utils import LLMFactory, StreamHandler, TelemetryTracker, generate_thread_id, load_project_spec, add_file_handler, remove_file_handler, create_serde
from devteam.utils.workspace import hydrate_workspace
from .extensions import build_extensions
from .request import RunRequest, ResumeRequest, StartRequest

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

async def async_main(request: RunRequest):
    workflow = request.workflow
    fanout = request.fanout
    if workflow.endswith('-fanout'):
        workflow = workflow[:-7]
        fanout = True
    is_resume = isinstance(request, ResumeRequest)
    if is_resume:
        thread_id = request.resume_thread
        project_requirements = None
        print(f"🔄 Resuming existing project thread: {thread_id}")
    else:
        project_name, project_requirements = load_project_spec(request.project_file_path)
        thread_id = generate_thread_id(project_name)
        print(f"🚀 Starting NEW project: {project_name}")
    project_folder = settings.workspace_dir / thread_id
    project_folder.mkdir(parents=True, exist_ok=True)
    if isinstance(request, StartRequest) and request.seed_path:
        hydrate_workspace(request.seed_path, project_folder / 'workspace')
    db_path = project_folder / 'state.db'
    log_file_path = project_folder / 'execution.log'
    log_handler = add_file_handler(log_file_path)
    telemetry = TelemetryTracker()
    callbacks = [telemetry]
    if settings.llm_streaming:
        callbacks.append(StreamHandler())
    llm_factory = LLMFactory(provider=request.provider, callbacks=callbacks)
    crew_factory = CrewFactory(llm_factory=llm_factory)
    try:
        async with aiosqlite.connect(db_path) as conn:
            checkpointer = AsyncSqliteSaver(conn, serde=create_serde())
            crew = crew_factory.create(
                project_folder,
                checkpointer=checkpointer,
                rpm=request.rpm,
                extensions=build_extensions(),
                config_name=WORKFLOW_CREW.get(workflow, 'basic.yaml'),
                fanout=fanout,
            )
            print("🚀 Starting AI Dev Team...")
            print(f"📁 Workspace: {project_folder.absolute()}")
            final_state = await crew.execute(
                thread_id=thread_id,
                requirements=project_requirements,
                feedback=request.feedback if is_resume else None,
                feedback_source=request.feedback_source if is_resume else 'reviewer',
                checkpoint_id=request.checkpoint_id if is_resume else None,
            )
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
