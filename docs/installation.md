# Installation Guide

This guide will help you set up **My Dev Team** on your local machine.

## Prerequisites

Before installing, ensure you have the following:

* **Python 3.10+**: Verify by running `python --version`.
* **API Credentials**: You will need at least one of the following:
    * An OpenAI or Groq API Key set in your environment variables.
    * A local instance of **Ollama** running (for free, local execution).

## Standard Installation

We highly recommend using a virtual environment (`venv` or `conda`).

```sh
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the core package
pip install my-dev-team
```

## Optional Dependencies

### Web Dashboard (UI)

The web dashboard is a React application served by a Flask backend. To use it, install the UI extras:

```sh
pip install "my-dev-team[ui]"
```

Then build the React frontend (requires **Node.js 18+**):

```sh
cd gui
npm install
npm run build
```

The build output is written into the package directory and served automatically. After building once, simply run:

```sh
devteam-ui
```

> **Note:** The `npm run build` step is only needed once after cloning, and again after any GUI source changes. Node.js is not required at runtime.

### Sandboxed QA Execution

For the QA Engineer to execute code in a real, isolated environment (rather than just simulating it), you must have **Docker Engine** installed and running on your host machine.

* [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Build the image:**

```sh
docker build -t python:3.12-pytest -f src/devteam/config/docker/Dockerfile.python3.12-pytest .
```

- This will create an image named `python:3.12-pytest` with pytest preinstalled and `/workspace` as the working directory.
- You can customize the Dockerfile for other Python versions or additional dependencies as needed.

### LLM Provider Packages

The core `langchain` package is included as a dependency, but each provider requires its own integration package. Install only the ones you need:

```sh
pip install langchain-ollama      # Ollama (local models)
pip install langchain-groq        # Groq
pip install langchain-anthropic   # Anthropic Claude
pip install langchain-openai      # OpenAI
```

Set the corresponding API key in your `.env` file:

```
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### Ollama (Local LLMs)

To use local LLMs with Ollama, follow the [Ollama Installation Guide](./ollama.md) for setup instructions on Windows, WSL and Linux.

## Configuration

### Environment Variables

Create `.env` file in your project root to store your keys:

```
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
```

### Local Development

If you want to contribute or modify the agents, clone the repository and install in editable mode:

```sh
git clone https://github.com/bobrovsky420/my-dev-team.git
cd my-dev-team
pip install -e .
```

To also develop or rebuild the web dashboard:

```sh
cd gui
npm install
npm run build   # writes output to src/devteam/gui/dist/
```

For frontend hot-reload during development, run the Vite dev server alongside the Flask backend:

```sh
# Terminal 1 — Flask API
devteam-ui

# Terminal 2 — Vite dev server (proxies /api to Flask)
cd gui && npm run dev
# Open http://localhost:5173
```

## Verify Installation

Once installed, verify the CLI is working by checking the help command:

```sh
devteam --help
```
