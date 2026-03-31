import argparse
import asyncio
import logging
import sys
import warnings
warnings.filterwarnings('ignore', message="Core Pydantic V1 functionality", category=UserWarning, module='langchain_core')
from pathlib import Path
from dotenv import load_dotenv
from rich import print # pylint: disable=redefined-builtin
from devteam import settings
from devteam.utils import setup_logging
from .runtime import async_main, show_history

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run the AI Dev Team autonomous framework.')
    parser.add_argument('project_file', nargs='?', help='path to the text file containing your project requirements')
    parser.add_argument('--config', type=str, help='path to a custom configuration folder (overrides default one)')
    parser.add_argument('--verbose', action='store_true', help='enable debug logging')
    parser.add_argument('--resume', type=str, help='resume a specific thread ID')
    parser.add_argument('--provider', type=str, default='ollama', choices=['anthropic', 'free', 'groq', 'ollama', 'openai'], help='LLM provider to use (default: ollama)')
    parser.add_argument('--rpm', type=int, default=0, help='API requests per minute (default: 0 = none)')
    parser.add_argument('--feedback', type=str, help='human feedback to inject into the state when resuming')
    parser.add_argument('--as-node', type=str, default='reviewer', choices=['pm', 'architect', 'reviewer', 'qa'], help='which agent should deliver this feedback (forces graph routing)')
    parser.add_argument('--history', action='store_true', help='print the timeline of checkpoints for this thread and exit')
    parser.add_argument('--checkpoint', type=str, help='specific checkpoint ID to rewind to before injecting feedback')
    parser.add_argument('--timeout', type=int, default=120, help='maximum time (in seconds) to wait for an LLM response (default: 120)')
    parser.add_argument('--thinking', action='store_true', help='stream raw LLM thinking output to stderr')
    parser.add_argument('--no-docker', action='store_true', help='run QA engineer without Docker sandbox')
    parser.add_argument('--ask-approval', action='store_true', help='pause after planning to review and approve the plan before development starts')
    return parser

def _apply_config(custom_config_path: str):
    if not custom_config_path:
        return
    custom_path = Path(custom_config_path)
    if not custom_path.exists() or not custom_path.is_dir():
        print(f"❌ Error: Config directory '{custom_path}' not found.")
        sys.exit(1)
    settings.config_dir = custom_path

def _validate_inputs(parser: argparse.ArgumentParser, args):
    if args.resume:
        path = settings.workspace_dir / args.resume
        if not path.exists():
            logging.error("❌ Error: Could not find workspace for thread '%s'", args.resume)
            sys.exit(1)
    elif args.project_file:
        if not Path(args.project_file).exists():
            logging.error("❌ Error: Could not find project file '%s'", args.project_file)
            sys.exit(1)
    else:
        parser.error('You must provide either a project_file OR the --resume flag.')
    if args.history and not args.resume:
        parser.error('--history requires --resume <thread_id> to specify which project to inspect.')

def main_ui():
    """Entry point for the devteam-ui command."""
    load_dotenv()
    from devteam.server import run as run_server
    try:
        run_server()
    except KeyboardInterrupt:
        sys.exit(0)

def main():
    load_dotenv()

    parser = _build_parser()
    args = parser.parse_args()

    setup_logging(console_level=logging.DEBUG if args.verbose else logging.INFO)
    _apply_config(args.config)
    settings.llm_timeout = args.timeout
    settings.llm_streaming = args.thinking
    settings.no_docker = args.no_docker
    settings.ask_approval = args.ask_approval
    _validate_inputs(parser, args)

    if args.history:
        asyncio.run(show_history(thread_id=args.resume))
        return

    asyncio.run(
        async_main(
            args.project_file,
            args.provider,
            args.rpm,
            resume_thread=args.resume,
            feedback=args.feedback,
            feedback_source=args.as_node,
            checkpoint_id=args.checkpoint,
        )
    )
