# UT Study Prep

UT Study Prep is a lightweight Streamlit application for organizing eight UT tutorial sessions, turning pasted Tuton material into revision notes, and practicing active recall before a final exam.

The app works in two modes:

- **Local study engine (free, no API key):** extractive summaries, repeated-concept analysis, exam-focus signals, flashcards, and deterministic quizzes.
- **OpenAI mode (optional):** richer, schema-validated study packs using the Responses API. The default model is `gpt-6-luna`, selected for focused, cost-sensitive tasks.

Exam-focus predictions are study priorities inferred from your own notes, discussion questions, and assignments. They are not guaranteed or leaked exam questions.

## Features

- Session dashboard for Session 1 through Session 8
- Separate inputs for Tuton material, discussions, and assignments
- Local or AI-generated summary and key terms
- Evidence-based exam-focus predictions with confidence labels
- Expandable flashcards and interactive multiple-choice quizzes
- Browser-native Text-to-Speech with no audio service or file storage
- Markdown export for each session
- JSON backup and restore for all eight sessions
- Responsive, accessible Streamlit interface

## Project structure

```text
ut-study-prep/
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── tests/
│   └── test_analysis.py
├── ut_study_prep/
│   ├── __init__.py
│   ├── ai.py
│   ├── analysis.py
│   ├── models.py
│   └── tts.py
├── .dockerignore
├── .gitignore
├── app.py
├── Dockerfile.vercel
├── README.md
└── requirements.txt
```

## Run locally

Python 3.11 or 3.12 is recommended.

### 1. Create a virtual environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install and start

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`.

### 3. Optional: enable OpenAI mode

The local engine is the default fallback and needs no key. For OpenAI mode, copy the example secrets file:

Windows PowerShell:

```powershell
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

macOS or Linux:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then replace the placeholder value:

```toml
OPENAI_API_KEY = "your-api-key-here"
OPENAI_MODEL = "gpt-6-luna"
```

The real `.streamlit/secrets.toml` is ignored by Git. Never paste an API key into `app.py`, `README.md`, or a GitHub commit. The app uses the OpenAI Responses API with Pydantic Structured Outputs, so AI results conform to the same typed structure as local results. OpenAI API usage may incur charges; the local engine remains free.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Push to GitHub

Create an empty GitHub repository named `ut-study-prep` without adding a README or `.gitignore`, then run these commands from this project folder:

```bash
git init
git add .
git commit -m "Build UT Study Prep Streamlit app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/ut-study-prep.git
git push -u origin main
```

If the repository already contains a commit, clone that repository first, copy these project files into the clone, then run `git add .`, `git commit`, and `git push`. This avoids overwriting existing history.

## Deploy free on Streamlit Community Cloud (recommended)

Streamlit Community Cloud is the natural deployment target because it runs `streamlit run` from the repository root and supports the app's interactive session model.

1. Push this complete project to GitHub. Keep `app.py` and `requirements.txt` at the repository root.
2. Sign in at [share.streamlit.io](https://share.streamlit.io/) with GitHub.
3. Click **Create app** and choose **Yup, I have an app**.
4. Select the repository, the `main` branch, and `app.py` as the entrypoint.
5. Open **Advanced settings**, choose Python 3.12, and optionally paste the following into **Secrets**:

   ```toml
   OPENAI_API_KEY = "your-api-key-here"
   OPENAI_MODEL = "gpt-6-luna"
   ```

6. Click **Save**, then deploy. Future pushes to the selected branch automatically update the app.

Official references: [deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [organize project files](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), and [manage secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Deploy on Vercel (experimental)

`Dockerfile.vercel` is included so Vercel's Container Runtime can build the Streamlit process. Connect the GitHub repository to a new Vercel project and deploy with default project settings. Add `OPENAI_API_KEY` and `OPENAI_MODEL` under **Project settings → Environment Variables** if you want OpenAI mode.

This path is experimental for Streamlit. Vercel container Functions scale to zero and use Function limits. Streamlit depends on a long-lived WebSocket-backed session; on Vercel Hobby, a connection can be closed when the Function reaches its maximum duration, and reconnecting may lose in-memory session state. Use the JSON backup button often. For a stable free deployment, use Streamlit Community Cloud.

Official Vercel references: [Container Runtime](https://vercel.com/docs/functions/runtimes/container), [WebSockets](https://vercel.com/docs/functions/websockets), and [Function limits](https://vercel.com/docs/functions/limitations).

## Data and privacy notes

- Local mode does not call an AI provider, but a cloud deployment still processes pasted text on that host.
- OpenAI mode sends the pasted material, discussion prompts, and assignment text to the OpenAI API.
- Session data is kept in Streamlit session memory. It is not written to a database.
- Use **Back up all 8 sessions** before closing or refreshing a long study session.
- Browser Text-to-Speech uses voices installed or provided by the visitor's browser; voice availability varies by device.

## Troubleshooting

**The app says an OpenAI key is missing**  
Choose **Local** in the sidebar, or add `OPENAI_API_KEY` to Streamlit secrets.

**The browser does not speak**  
Try another voice in the Audio Reader, allow audio playback, or use Chrome/Edge/Safari with Web Speech API support.

**The summary is too literal**  
That is expected in Local mode because it extracts source sentences. Add discussion and assignment prompts for better signals, or use OpenAI mode for synthesis.

**Changes do not appear after deployment**  
Confirm the deployment is watching the correct repository, branch, and `app.py` path. On Streamlit Community Cloud, a dependency change can take longer because the environment must be rebuilt.
