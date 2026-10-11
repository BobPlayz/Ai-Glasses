# Local AI runtime

The application uses Ollama's local HTTP API at 127.0.0.1:11434. It refuses a configured non-local host to prevent accidentally sending prompts to a remote service.

## Planned default models

- Primary: qwen2.5:1.5b
- Fallback: qwen2.5:0.5b

These are initial candidates, not benchmarks. Confirm model availability and performance on the target laptop before the exhibition. Ollama must be installed and both models downloaded before disconnecting the internet. The application never downloads models automatically during a question.

## Setup model cache

After installing Ollama, run these commands in PowerShell while online:

    ollama pull qwen2.5:1.5b
    ollama pull qwen2.5:0.5b

Then verify:

    ollama list

For a strict offline test, disconnect internet, leave Ollama running locally, and ask several questions. Model fallback only works if the fallback model has already been downloaded.

## Limitations

This does not yet integrate speech recognition, wake-word detection, TTS, camera, or OCR. Do not represent those as implemented. Model response speed depends on memory pressure and CPU performance.
