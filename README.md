# HumanType

A Windows 10/11 desktop tool that types your text into whatever field is focused — slowly, with natural pauses, like a person at a keyboard.

## How it works

1. Paste text into HumanType.
2. Click the input you want filled (browser, Word, Discord, a game chat box, anywhere).
3. Start typing:
   - **Start typing** waits a few seconds so you can click the field.
   - **F8** types immediately into whatever is already focused. After **F9**, F8 continues from where it stopped.
4. **F9** pauses. It does not restart from the beginning.

It never pastes. It sends keystrokes one character at a time, with uneven timing based on keyboard distance, faster common words, short bursts, punctuation pauses, and optional slips (nearby key, double-tap, or swapped letters) that get corrected.

## Install (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and check **Add python.exe to PATH**.
2. Open PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

If a program ignores the keystrokes, run the same command from an **Administrator** PowerShell.

## Settings

| Control | What it does |
|---|---|
| WPM | Exact overall typing speed (30–140 words per minute). 62 WPM takes about as long as a 62 WPM typist |
| Humanize | How uneven the rhythm is around that WPM. **Even** is steady. **Natural** uses finger travel, word chunks, bursts, and pauses, but still finishes at the selected WPM |
| Countdown | Seconds to wait after **Start typing** so you can click the target |
| Occasional typos | Nearby-key misses, double letters, or swapped letters, then immediate correction |
| Always on top | Keeps the window visible while you click another app |
| Paste clipboard | Drops whatever you copied into the box |

## Make an .exe (optional)

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name HumanType main.py
```

The file lands in `dist\HumanType.exe`. Windows Defender sometimes flags keyboard tools; add an exclusion if needed.

## Notes

- Click the target field **before** F8, or during the countdown if you used Start.
- Works with most apps. Some elevated or anti-cheat windows block simulated keys.
- Linux/macOS can run it for testing; Windows is the intended target.
