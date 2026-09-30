# Deploy Spend Coach online (free, Render)

1. Create a free account at github.com. Click New repository, name it `spend-coach`, create it.
2. On the repo page click "uploading an existing file", drag in EVERYTHING from this folder
   (app.py, static folder, requirements.txt, Procfile, render.yaml, README.md), then Commit.
   Check that `static/index.html` is inside the static folder on GitHub.
3. Go to render.com, sign up with GitHub. Click New + -> Web Service -> pick your `spend-coach` repo.
4. Set: Runtime = Python 3, Build Command = `pip install -r requirements.txt`,
   Start Command = `python app.py`, Instance type = Free. Click Deploy.
5. After 2-3 minutes Render shows a link like https://spend-coach.onrender.com. Open it.

Notes
- Free plan sleeps after inactivity: the first load can take about 30 seconds. Open it once before your demo.
- Free plan has no permanent disk, so the SQLite data resets when the service restarts. Fine for a demo.
