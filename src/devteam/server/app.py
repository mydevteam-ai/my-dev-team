"""Flask server for MyDevTeam GUI."""
import asyncio
import json
import logging
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

import aiosqlite
import yaml
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from devteam import settings
from devteam.crew import CrewFactory
from devteam.extensions import HumanInTheLoopGUI, StreamlitLogger
from devteam.utils import LLMFactory, StreamHandler, generate_thread_id, parse_spec_from_string, setup_logging, add_file_handler, remove_file_handler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project execution registry
# ---------------------------------------------------------------------------

@dataclass
class ProjectContext:
    thread_id: str
    queue: Queue
    hitl_ext: HumanInTheLoopGUI | None
    result_holder: dict
    worker: threading.Thread
    events: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def drain_queue(self):
        """Move all pending queue items into the events buffer."""
        while True:
            try:
                event = self.queue.get_nowait()
                with self._lock:
                    self.events.append(event)
            except Empty:
                break

    def snapshot(self) -> list:
        with self._lock:
            return list(self.events)


_projects: dict[str, ProjectContext] = {}
_projects_lock = threading.Lock()


def _get_project(thread_id: str) -> ProjectContext | None:
    with _projects_lock:
        return _projects.get(thread_id)


def _register_project(ctx: ProjectContext):
    with _projects_lock:
        _projects[ctx.thread_id] = ctx


# ---------------------------------------------------------------------------
# Crew execution helpers (mirrors gui/execution.py)
# ---------------------------------------------------------------------------

def get_providers_from_config() -> list[str]:
    config_path = settings.config_dir / 'llms.yaml'
    if not config_path.exists():
        return ['ollama', 'groq', 'openai']
    try:
        data = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        return list(data['providers'].keys())
    except Exception:  # pylint: disable=broad-exception-caught
        return ['ollama', 'groq', 'openai']


def _run_crew_in_thread(
    thread_id: str,
    requirements: str,
    provider: str,
    rpm: int,
    event_queue: Queue,
    result_holder: dict,
    hitl_extension: HumanInTheLoopGUI | None = None,
    thinking: bool = False,
):
    """Async crew execution inside a dedicated thread / event loop."""
    async def _inner():
        project_folder = settings.workspace_dir / thread_id
        project_folder.mkdir(parents=True, exist_ok=True)
        db_path = project_folder / 'state.db'

        callbacks = []
        settings.llm_streaming = thinking
        if thinking:
            callbacks.append(StreamHandler(queue=event_queue))

        llm_factory = LLMFactory(provider=provider, callbacks=callbacks)
        crew_factory = CrewFactory(llm_factory=llm_factory)
        extensions = [StreamlitLogger(event_queue)]
        if hitl_extension:
            extensions.append(hitl_extension)

        async with aiosqlite.connect(db_path) as conn:
            checkpointer = AsyncSqliteSaver(conn)
            crew = crew_factory.create(project_folder, checkpointer=checkpointer, rpm=rpm, extensions=extensions)
            final_state = await crew.execute(thread_id=thread_id, requirements=requirements)
            result_holder['final_state'] = final_state
            result_holder['thread_id'] = thread_id

    project_folder = settings.workspace_dir / thread_id
    project_folder.mkdir(parents=True, exist_ok=True)
    exec_log_handler = add_file_handler(project_folder / 'execution.log')
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_inner())
    except Exception as exc:  # pylint: disable=broad-exception-caught
        msg = str(exc)
        logger.exception("Worker thread failed: %s", msg)
        result_holder['error'] = msg
        event_queue.put({'type': 'error', 'ts': time.time(),
                         'state': {'error': True, 'error_message': msg}})
    finally:
        loop.close()
        remove_file_handler(exec_log_handler)


def _run_resume_in_thread(
    thread_id: str,
    feedback: str,
    feedback_source: str,
    checkpoint_id: str | None,
    event_queue: Queue,
    result_holder: dict,
    hitl_extension: HumanInTheLoopGUI | None = None,
):
    """Resume an existing crew execution in a dedicated thread."""
    async def _inner():
        project_folder = settings.workspace_dir / thread_id
        db_path = project_folder / 'state.db'
        llm_factory = LLMFactory()
        crew_factory = CrewFactory(llm_factory=llm_factory)
        extensions = [StreamlitLogger(event_queue)]
        if hitl_extension:
            extensions.append(hitl_extension)
        async with aiosqlite.connect(db_path) as conn:
            checkpointer = AsyncSqliteSaver(conn)
            crew = crew_factory.create(project_folder, checkpointer=checkpointer, extensions=extensions)
            final_state = await crew.execute(
                thread_id=thread_id,
                feedback=feedback,
                feedback_source=feedback_source,
                checkpoint_id=checkpoint_id,
            )
            result_holder['final_state'] = final_state
            result_holder['thread_id'] = thread_id

    exec_log_handler = add_file_handler(settings.workspace_dir / thread_id / 'execution.log')
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_inner())
    except Exception as exc:  # pylint: disable=broad-exception-caught
        msg = str(exc)
        logger.exception("Resume thread failed: %s", msg)
        result_holder['error'] = msg
        event_queue.put({'type': 'error', 'ts': time.time(),
                         'state': {'error': True, 'error_message': msg}})
    finally:
        loop.close()
        remove_file_handler(exec_log_handler)


def _fetch_history(thread_id: str) -> list[dict]:
    async def _inner():
        db_path = settings.workspace_dir / thread_id / 'state.db'
        project_folder = settings.workspace_dir / thread_id
        async with aiosqlite.connect(db_path) as conn:
            checkpointer = AsyncSqliteSaver(conn)
            crew_factory = CrewFactory()
            crew = crew_factory.create(project_folder, checkpointer=checkpointer)
            return await crew.get_history(thread_id)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_inner())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

def create_app(gui_dist: Path | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=None)

    if gui_dist is None:
        # Bundled inside the installed package (built by: cd gui && npm run build)
        gui_dist = Path(__file__).resolve().parent.parent / 'gui' / 'dist'

    # ------------------------------------------------------------------ #
    # Static files — serve the React build                                 #
    # ------------------------------------------------------------------ #

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        dist = gui_dist
        if path and (dist / path).exists():
            return send_from_directory(str(dist), path)
        return send_from_directory(str(dist), 'index.html')

    # ------------------------------------------------------------------ #
    # REST API                                                             #
    # ------------------------------------------------------------------ #

    @app.get('/api/providers')
    def api_providers():
        return jsonify(get_providers_from_config())

    @app.get('/api/threads')
    def api_threads():
        if not settings.workspace_dir.exists():
            return jsonify([])
        threads = [d.name for d in settings.workspace_dir.iterdir() if d.is_dir()]
        return jsonify(sorted(threads, reverse=True))

    @app.post('/api/projects')
    def api_start_project():
        data = request.get_json(force=True)
        requirements = data.get('requirements', '').strip()
        if not requirements:
            return jsonify({'error': 'requirements is required'}), 400

        provider = data.get('provider', 'ollama')
        rpm = int(data.get('rpm', 0))
        timeout = int(data.get('timeout', 120))
        thinking = bool(data.get('thinking', False))
        ask_approval = bool(data.get('ask_approval', False))

        settings.llm_timeout = timeout
        settings.ask_approval = ask_approval

        project_name, requirements = parse_spec_from_string(requirements)
        thread_id = generate_thread_id(project_name)

        event_queue: Queue = Queue()
        result_holder: dict = {}
        # Always present — handles PM clarification questions regardless of ask_approval.
        # ask_approval only controls graph routing (whether spec/plan review pauses happen).
        hitl_ext = HumanInTheLoopGUI(event_queue)

        worker = threading.Thread(
            target=_run_crew_in_thread,
            args=(thread_id, requirements, provider, rpm, event_queue, result_holder, hitl_ext, thinking),
            daemon=True,
        )
        worker.start()

        ctx = ProjectContext(
            thread_id=thread_id,
            queue=event_queue,
            hitl_ext=hitl_ext,
            result_holder=result_holder,
            worker=worker,
        )
        _register_project(ctx)

        return jsonify({'thread_id': thread_id})

    @app.post('/api/projects/<thread_id>/resume')
    def api_resume_project(thread_id: str):
        data = request.get_json(force=True)
        feedback = data.get('feedback', '')
        feedback_source = data.get('feedback_source', 'reviewer')
        checkpoint_id = data.get('checkpoint_id') or None
        ask_approval = bool(data.get('ask_approval', False))

        workspace_path = settings.workspace_dir / thread_id
        if not workspace_path.exists():
            return jsonify({'error': 'Thread not found'}), 404

        event_queue: Queue = Queue()
        result_holder: dict = {}
        hitl_ext = HumanInTheLoopGUI(event_queue)

        worker = threading.Thread(
            target=_run_resume_in_thread,
            args=(thread_id, feedback, feedback_source, checkpoint_id, event_queue, result_holder, hitl_ext),
            daemon=True,
        )
        worker.start()

        ctx = ProjectContext(
            thread_id=thread_id,
            queue=event_queue,
            hitl_ext=hitl_ext,
            result_holder=result_holder,
            worker=worker,
        )
        _register_project(ctx)

        return jsonify({'thread_id': thread_id})

    @app.post('/api/projects/<thread_id>/hitl')
    def api_hitl(thread_id: str):
        ctx = _get_project(thread_id)
        if not ctx or not ctx.hitl_ext:
            return jsonify({'error': 'No HITL extension active'}), 404

        data = request.get_json(force=True)
        if data.get('abort'):
            ctx.hitl_ext.abort()
        else:
            ctx.hitl_ext.submit_response(data.get('response', ''))

        return jsonify({'ok': True})

    @app.get('/api/projects/<thread_id>/history')
    def api_history(thread_id: str):
        workspace_path = settings.workspace_dir / thread_id
        if not workspace_path.exists():
            return jsonify({'error': 'Thread not found'}), 404
        try:
            history = _fetch_history(thread_id)
            return jsonify(history)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return jsonify({'error': str(exc)}), 500

    @app.get('/api/projects/<thread_id>/state')
    def api_project_state(thread_id: str):
        ctx = _get_project(thread_id)
        if not ctx:
            return jsonify({'error': 'Not found'}), 404
        ctx.drain_queue()
        events = ctx.snapshot()
        # Return the latest full_state if available
        full_state = {}
        for ev in reversed(events):
            if ev.get('full_state'):
                full_state = ev['full_state']
                break
        return jsonify({
            'thread_id': thread_id,
            'running': ctx.worker.is_alive(),
            'events_count': len(events),
            'full_state': full_state,
            'result': ctx.result_holder,
        })

    # ------------------------------------------------------------------ #
    # Server-Sent Events stream                                            #
    # ------------------------------------------------------------------ #

    @app.get('/api/projects/<thread_id>/stream')
    def api_stream(thread_id: str):
        ctx = _get_project(thread_id)
        if not ctx:
            return jsonify({'error': 'Not found'}), 404

        last_index = int(request.args.get('from', 0))

        def generate():
            # Immediate ping so the browser knows the connection is alive
            yield ": connected\n\n"
            idx = last_index
            heartbeat_counter = 0
            while True:
                ctx.drain_queue()
                snapshot = ctx.snapshot()

                while idx < len(snapshot):
                    event = snapshot[idx]
                    idx += 1
                    try:
                        payload = _serialize_event(event)
                        yield f"data: {json.dumps(payload)}\n\n"
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                # Stop streaming when the worker is done and no pending events
                if not ctx.worker.is_alive() and idx >= len(ctx.snapshot()):
                    yield "data: {\"type\": \"__done__\"}\n\n"
                    break

                # Heartbeat comment every ~15 s to keep proxies from closing idle connections
                heartbeat_counter += 1
                if heartbeat_counter >= 60:
                    yield ": heartbeat\n\n"
                    heartbeat_counter = 0

                time.sleep(0.25)

        return Response(
            stream_with_context(generate()),
            content_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    return app


def _serialize_event(event: dict) -> dict:
    """Convert an event dict to a JSON-serialisable form."""
    result = {}
    for key, value in event.items():
        if key in ('state', 'full_state', 'state_update'):
            result[key] = _serialize_state(value)
        elif isinstance(value, (str, int, float, bool, list, type(None))):
            result[key] = value
        else:
            result[key] = str(value)
    return result


def _serialize_state(state) -> dict:
    if not isinstance(state, dict):
        return {}
    safe = {}
    for k, v in state.items():
        if k == 'messages':
            # Serialize LangChain messages
            safe[k] = [_msg_to_dict(m) for m in (v or [])]
        elif isinstance(v, (str, int, float, bool, type(None))):
            safe[k] = v
        elif isinstance(v, list):
            safe[k] = [str(i) if not isinstance(i, (str, int, float, bool, type(None), dict)) else i for i in v]
        elif isinstance(v, dict):
            safe[k] = {str(kk): str(vv) if not isinstance(vv, (str, int, float, bool, type(None))) else vv for kk, vv in v.items()}
        else:
            safe[k] = str(v)
    return safe


def _msg_to_dict(msg) -> dict:
    try:
        return {'type': msg.__class__.__name__, 'content': str(msg.content)}
    except Exception:  # pylint: disable=broad-exception-caught
        return {'type': 'unknown', 'content': str(msg)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(host: str = '127.0.0.1', port: int = 5000, open_browser: bool = True):
    """Start the Flask server."""
    from dotenv import load_dotenv
    load_dotenv()

    # File-only logging — no console output while GUI is running
    setup_logging(console_level=None)
    logging.getLogger('werkzeug').propagate = True  # let it go to the file handler only

    gui_dist = Path(__file__).resolve().parent.parent / 'gui' / 'dist'
    if not gui_dist.exists():
        print(f"⚠  React build not found at {gui_dist}")
        print("   Run: cd gui && npm install && npm run build")

    app = create_app(gui_dist)

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f'http://{host}:{port}')).start()

    print(f"🚀 MyDevTeam UI → http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
