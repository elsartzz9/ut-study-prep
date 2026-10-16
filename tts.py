"""Browser-native text-to-speech control rendered inside Streamlit."""

from __future__ import annotations

import html
import json


def speech_controls(summary_text: str, language: str = "id-ID") -> str:
    """Return a self-contained Web Speech API player."""

    safe_text = json.dumps(summary_text, ensure_ascii=False).replace("</", "<\\/")
    safe_language = json.dumps(language)
    empty_note = "Generate a summary first, then press Listen."
    if not summary_text.strip():
        return f'<div class="empty">{html.escape(empty_note)}</div>'

    return f"""
    <div class="reader" role="group" aria-label="Summary audio reader">
      <div class="reader-head">
        <div>
          <span class="eyebrow">AUDIO READER</span>
          <strong>Listen to this summary</strong>
        </div>
        <select id="voice" aria-label="Choose a browser voice"></select>
      </div>
      <div class="controls">
        <button id="play" type="button">▶ Listen</button>
        <button id="pause" type="button">Ⅱ Pause / resume</button>
        <button id="stop" type="button">■ Stop</button>
      </div>
      <p id="status" aria-live="polite">Uses the voices already available in your browser.</p>
    </div>
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #172336; }}
      .reader {{ border: 1px solid #dfe4e2; border-radius: 16px; padding: 16px; background: #fffdf8; }}
      .reader-head {{ display: flex; gap: 12px; justify-content: space-between; align-items: center; }}
      .reader-head div {{ display: grid; gap: 3px; }}
      .eyebrow {{ color: #d45c3b; font-size: 10px; font-weight: 800; letter-spacing: .14em; }}
      strong {{ font-size: 16px; }}
      select {{ max-width: 48%; border: 1px solid #ccd4d1; border-radius: 9px; padding: 8px; background: white; }}
      .controls {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
      button {{ border: 0; border-radius: 9px; padding: 9px 13px; font-weight: 750; cursor: pointer; }}
      #play {{ color: white; background: #123d3a; }}
      #pause, #stop {{ color: #123d3a; background: #e8efec; }}
      p {{ margin: 10px 0 0; color: #65716f; font-size: 12px; }}
      .empty {{ padding: 15px; border-radius: 12px; background: #f4f0e8; color: #65716f; font: 14px system-ui; }}
    </style>
    <script>
      const text = {safe_text};
      const language = {safe_language};
      const synth = window.speechSynthesis;
      const voiceSelect = document.getElementById('voice');
      const status = document.getElementById('status');
      let utterance = null;

      function loadVoices() {{
        const voices = synth.getVoices();
        voiceSelect.innerHTML = '';
        voices.forEach((voice, index) => {{
          const option = document.createElement('option');
          option.value = String(index);
          option.textContent = `${{voice.name}} (${{voice.lang}})`;
          if (voice.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase())) option.selected = true;
          voiceSelect.appendChild(option);
        }});
      }}

      loadVoices();
      if ('onvoiceschanged' in synth) synth.onvoiceschanged = loadVoices;

      document.getElementById('play').addEventListener('click', () => {{
        synth.cancel();
        utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = language;
        const voices = synth.getVoices();
        const selected = voices[Number(voiceSelect.value)];
        if (selected) utterance.voice = selected;
        utterance.rate = 0.96;
        utterance.onstart = () => status.textContent = 'Reading the summary…';
        utterance.onend = () => status.textContent = 'Finished. Replay whenever you are ready.';
        utterance.onerror = () => status.textContent = 'This browser could not start speech. Try another voice.';
        synth.speak(utterance);
      }});

      document.getElementById('pause').addEventListener('click', () => {{
        if (synth.paused) {{ synth.resume(); status.textContent = 'Reading the summary…'; }}
        else {{ synth.pause(); status.textContent = 'Paused.'; }}
      }});

      document.getElementById('stop').addEventListener('click', () => {{
        synth.cancel();
        status.textContent = 'Stopped.';
      }});
    </script>
    """
