# Ollama Installation Guide

This guide covers how to install Ollama on Windows, WSL and Linux, as well as how to install models.

## 1. Install Ollama on Windows

1. Go to the [Ollama downloads page](https://ollama.com/download).
2. Download the Windows installer (`OllamaSetup.exe` file).
3. Run the installer and follow the prompts.
4. After installation, open a new terminal (Command Prompt or PowerShell) and verify installation:

	```sh
	ollama --version
	```

## 2. Install Ollama on Windows WSL (Ubuntu)

1. Open your WSL terminal (e.g. Ubuntu).
2. Download and run the Ollama installation script:

	```sh
	curl -fsSL https://ollama.com/install.sh | sh
	```

3. Start the Ollama service:

	```sh
	sudo systemctl start ollama
	```

	If `systemctl` is not available, start Ollama manually:

	```sh
	ollama serve &
	```

4. Verify installation:

	```sh
	ollama --version
	```

## 3. Install Ollama on Linux (Ubuntu/Debian)

1. Open a terminal.
2. Download and run the Ollama installation script:

	```sh
	curl -fsSL https://ollama.com/install.sh | sh
	```

3. Start the Ollama service:

	```sh
	sudo systemctl start ollama
	```

	Or manually:

	```sh
	ollama serve &
	```

4. Verify installation:

	```sh
	ollama --version
	```

## 4. Installing Models

To install (pull) a model, use the following command:

```sh
ollama pull <model-name>
```

For example, to install the Qwen 3 model:

```sh
ollama pull qwen3:8b
```

You can find available models at [Ollama's model library](https://ollama.com/library).

---

For more details, visit the [official Ollama documentation](https://ollama.com/docs/).
