import asyncio
import logging
import aiosqlite
from pathlib import Path
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich import print # pylint: disable=redefined-builtin
from devteam import settings
from devteam.crew import CrewFactory
from devteam.extensions import ConsoleLogger, HumanInTheLoop
from devteam.utils import LLMFactory, StreamHandler, TelemetryTracker, generate_thread_id, load_project_spec, add_file_handler, remove_file_handler, create_serde
from devteam.utils.workspace import hydrate_workspace

STATE_DB_FILE = 'state.db'

def my_extensions() -> list:
    return [
        ConsoleLogger(),
        HumanInTheLoop(),
    ]

async def show_history(thread_id: str):
    project_folder = settings.workspace_dir / thread_id
    db_path = project_folder / STATE_DB_FILE
    llm_factory = LLMFactory(provider='ollama')
    crew_factory = CrewFactory(llm_factory=llm_factory)
    async with aiosqlite.connect(db_path) as conn:
        checkpointer = AsyncSqliteSaver(conn, serde=create_serde())
        crew = crew_factory.create(project_folder, checkpointer=checkpointer)
        logging.info("Fetching timeline history...")
        history_data = await crew.get_history(thread_id)
        for checkpoint in history_data:
            print(
                f"[{checkpoint['time']}] "
                f"Checkpoint: {checkpoint['c_id']} | Next: {checkpoint['node']}"
            )

WORKFLOW_CREW = {
    'development': 'basic.yaml',
    'migration': 'migration.yaml',
}

async def async_main(project_file_path: str, provider: str, rpm: int = 0, resume_thread: str = None, feedback: str = None, feedback_source: str = 'reviewer', checkpoint_id: str = None, seed_path: str = None, workflow: str = 'development'):
    if resume_thread:
        thread_id = resume_thread
        project_requirements = None
        logging.info('🔄 Resuming existing project thread: %s', thread_id)
    else:
        project_name, project_requirements = load_project_spec(project_file_path)
        thread_id = generate_thread_id(project_name)
        logging.info('🚀 Starting NEW project: %s', project_name)
    project_folder = settings.workspace_dir / thread_id
    project_folder.mkdir(parents=True, exist_ok=True)
    if seed_path:
        hydrate_workspace(seed_path, project_folder / 'workspace')
    db_path = project_folder / 'state.db'
    log_file_path = project_folder / 'execution.log'
    log_handler = add_file_handler(log_file_path)
    telemetry = TelemetryTracker()
    callbacks = [telemetry]
    if settings.llm_streaming:
        callbacks.append(StreamHandler())
    llm_factory = LLMFactory(provider=provider, callbacks=callbacks)
    crew_factory = CrewFactory(llm_factory=llm_factory)
    try:
        async with aiosqlite.connect(db_path) as conn:
            checkpointer = AsyncSqliteSaver(conn, serde=create_serde())
            crew = crew_factory.create(
                project_folder,
                checkpointer=checkpointer,
                rpm=rpm,
                extensions=my_extensions(),
                config_name=WORKFLOW_CREW.get(workflow, 'basic.yaml'),
            )
            logging.info('🚀 Starting AI Dev Team...')
            logging.info('📁 Workspace: %s', project_folder.absolute())
            final_state = await crew.execute(
                thread_id=thread_id,
                requirements=project_requirements,
                feedback=feedback,
                feedback_source=feedback_source,
                checkpoint_id=checkpoint_id,
            )
        if final_state.abort_requested:
            logging.error('❌ Workflow aborted by user or validation failure.')
            return
        if final_state.failed_tasks:
            logging.warning('⚠️  %d task(s) were skipped due to agent errors:', len(final_state.failed_tasks))
            for t in final_state.failed_tasks:
                print(f'   - {t}')
        if final_state.success:
            print('\n🎉 PROJECT COMPLETED SUCCESSFULLY!')
            print(final_state.final_report or 'No report generated.')
            return
        logging.error('🚨 RELEASE FAILED: Integration bugs found!')
        for bug in final_state.integration_bugs:
            print(f' - {bug}')
        print('\nNote: In a production system, these would be appended to the Phase 2 Backlog.')
    except KeyboardInterrupt:
        print(
            '\n\n🛑 Workflow interrupted by user (Ctrl+C)\n'
            '💡 You can resume this exact state later by running:\n'
            f'   devteam --resume {thread_id}'
        )
    except asyncio.CancelledError:
        logging.error('🛑 Async execution cancelled')
    finally:
        print()
        print(telemetry.get_receipt_panel())
        print(telemetry.get_optimization_panel())
        print()
        remove_file_handler(log_handler)
