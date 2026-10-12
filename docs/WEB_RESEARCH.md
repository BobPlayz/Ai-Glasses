# Web research for AI Glasses

AI Glasses stays **local-first**. Stable questions are answered by the local Ollama model without a web request. Questions containing freshness cues such as “latest”, “today”, “news”, “current”, or “past few days” trigger a small web search before the local model answers.

## What it does

- Searches up to five public web results using DuckDuckGo's text-search interface.
- Passes titles, source domains, dates, snippets, and URLs to the local model as untrusted research context.
- Shows the source URLs in the dashboard after the answer.
- Keeps web search separate from camera and microphone data. Only the text of the current question is sent to the search provider; saved memories, conversation history, photos, and audio are not sent.
- If search fails, the answer is marked as having no live sources instead of pretending the current facts were verified.
- The model still runs locally through Ollama. An internet connection is needed only for web research.

## Explicit research endpoint

The dashboard PIN dependency applies when LAN mode is enabled. From the same laptop, run:

```bat
curl -X POST http://127.0.0.1:8000/api/research -H "Content-Type: application/json" -d "{\"query\":\"India news today\",\"max_results\":5}"
```

If `GLASSES_LAN_MODE=1`, add `-H "X-Dashboard-Pin: YOUR_DASHBOARD_PIN"` to the command. Keep the PIN private.

## Install and test

From the repository directory in Windows Command Prompt:

```bat
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_web_research.py" -v
python -m unittest discover -s tests -v
```

The web-research unit tests mock the search provider, so they do not require live internet. The actual research endpoint does require internet access.
