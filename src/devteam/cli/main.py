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
from devteam.tools.rag import init_retrieve_context_tool
from devteam.utils import setup_logging, get_valid_providers
from .runtime import async_main, show_history

_PROVIDERS = ['anthropic', 'free', 'groq', 'ollama', 'openai', 'google']

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run the AI Dev Team autonomous framework.')
    parser.add_argument('project_file', nargs='?', help='path to the text file containing your project requirements')
    parser.add_argument('--config', type=str, help='path to a custom configuration folder (overrides default one)')
    parser.add_argument('--settings', type=str, help='path to a custom config.yaml (default: ~/.devteam/config.yaml)')
    parser.add_argument('--verbose', action='store_true', help='enable debug logging')
    parser.add_argument('--resume', type=str, metavar='THREAD_ID', help='resume a specific thread ID')
    parser.add_argument('--provider', type=str, default=settings.provider, help='LLM provider to use (default: ollama)')
    parser.add_argument('--azure', action='store_true', help='use the Azure-hosted variant of the selected provider')
    parser.add_argument('--rpm', type=int, default=settings.rpm, help='API requests per minute (default: 0 = none)')
    parser.add_argument('--feedback', type=str, help='human feedback to inject into the state when resuming')
    parser.add_argument('--as-node', type=str, default='reviewer', choices=['pm', 'architect', 'reviewer', 'qa'], help='which agent should deliver this feedback (forces graph routing)')
    parser.add_argument('--history', type=str, metavar='THREAD_ID', help='print the timeline of checkpoints for the given thread and exit')
    parser.add_argument('--checkpoint', type=str, help='specific checkpoint ID to rewind to before injecting feedback')
    parser.add_argument('--timeout', type=int, default=settings.llm_timeout, help='maximum time (in seconds) to wait for an LLM response (default: 120)')
    parser.add_argument('--thinking', action='store_true', help='stream raw LLM thinking output to stderr')
    parser.add_argument('--no-docker', action='store_true', help='run QA engineer without Docker sandbox')
    parser.add_argument('--ask-approval', action='store_true', help='pause after planning to review and approve the plan before development starts')
    parser.add_argument('--rag-collection', type=str, help='collection name to use for RAG queries')
    parser.add_argument('--no-rag', action='store_true', help='disable RAG context retrieval for all agents')
    parser.add_argument('--seed', type=str, help='path to an existing directory or ZIP archive to pre-populate the workspace')
    parser.add_argument('--skills', type=str, help='path to the user\'s SKILLs folder')
    parser.add_argument('--workflow', type=str, default='development', help='workflow type to run (default: development)')
    parser.add_argument('--fanout', action='store_true', help='run two developers independently on each task and let a code judge pick the winner before code review')
    parser.add_argument('--no-ask', action='store_true', help='disable clarification questions - agents proceed directly to their output tool without asking the user')
    parser.add_argument('--no-complexity-routing', action='store_true', help='disable complexity-based LLM routing for all agents')
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
    if args.history:
        path = settings.workspace_dir / args.history
        if not path.exists():
            logging.error("❌ Error: Could not find workspace for thread '%s'", args.history)
            sys.exit(1)
        return
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
    if args.seed:
        if args.resume:
            parser.error('--seed cannot be used with --resume (workspace already exists).')
        seed_path = Path(args.seed)
        if not seed_path.exists():
            parser.error(f"--seed path '{seed_path}' does not exist.")
        if not (seed_path.is_dir() or (seed_path.is_file() and seed_path.suffix == '.zip')):
            parser.error(f"--seed must be a directory or a .zip file, got: '{seed_path}'.")

def main_ui():
    """Entry point for the devteam-ui command."""
    load_dotenv()
    settings.load()
    init_retrieve_context_tool()
    from devteam.server import run as run_server  # pylint: disable=import-outside-toplevel
    try:
        run_server()
    except KeyboardInterrupt:
        sys.exit(0)

def main():
    load_dotenv()

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--settings', type=str)
    pre_args, _ = pre.parse_known_args()
    settings.load(Path(pre_args.settings) if pre_args.settings else None)

    parser = _build_parser()
    args = parser.parse_args()

    if args.azure:
        if args.provider.startswith('azure-'):
            parser.error(f"--azure has no effect: '{args.provider}' is already an Azure provider.")
        args.provider = f'azure-{args.provider}'

    setup_logging(console_level=logging.DEBUG if args.verbose else logging.INFO)
    _apply_config(args.config)
    valid = get_valid_providers()
    if valid and args.provider not in valid:
        parser.error(f"invalid --provider '{args.provider}'. Valid providers from {settings.tools_config_dir / 'llms.yaml'}: {', '.join(sorted(valid))}")
    settings.llm_timeout = args.timeout
    settings.llm_streaming = args.thinking
    if args.no_docker:
        settings.no_docker = True
    if args.ask_approval:
        settings.ask_approval = True
    if args.rag_collection:
        settings.rag_collection = args.rag_collection
    if args.no_rag:
        settings.rag_enabled = False
    if args.no_ask:
        settings.no_ask = True
    if args.no_complexity_routing:
        settings.no_complexity_routing = True
    if settings.rag_enabled:
        init_retrieve_context_tool()
    if args.skills:
        settings.skills = Path(args.skills)
    _validate_inputs(parser, args)

    if args.history:
        asyncio.run(show_history(thread_id=args.history))
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
            seed_path=args.seed,
            workflow=args.workflow,
            fanout=args.fanout,
        )
    )
