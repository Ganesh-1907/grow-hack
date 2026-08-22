FastAPI is a joy to build with. Render is a joy to deploy to. Put them together and you can go from a local prototype to a live URL in under ten minutes — assuming you know the one configuration gotcha that trips up nearly everyone on their first try.

That gotcha is the `--host 0.0.0.0` flag. Miss it, and your app will start fine but be unreachable from the internet. We'll cover that and everything else you need.

## Before you deploy: what Render needs from your app

Render is opinionated about a few things, but they're simple. Your repo should contain:

- A Python file (usually `main.py`) that defines a module-level `app` object: `app = FastAPI()`.
- A `requirements.txt` that includes **all** your dependencies, and critically, `uvicorn`. FastAPI itself doesn't include a server; you need an ASGI server like Uvicorn to run it.
- A Git repository hosted on GitHub or GitLab. Render pulls from these directly.

That's the minimum. If you have a database, static files, or background tasks, you'll need a bit more — we'll get to those.

## The dashboard path: connect your repo and configure the service

1. Log in to Render and click **New +** → **Web Service**.
2. Connect your GitHub or GitLab account if you haven't, then pick the repo and branch you want to deploy.
3. Render will detect Python and suggest a build command. Use:

   ```bash
   pip install -r requirements.txt
   ```

4. For the start command, use exactly this:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

   Two things here matter a lot:

   - `--host 0.0.0.0` binds the server to all network interfaces. Without it, Uvicorn defaults to `127.0.0.1`, which means it only listens on the container's loopback — invisible to the outside world. Your app will deploy successfully, show as healthy in the dashboard, and still return connection refused when you visit the URL. This is the #1 cause of "why is my FastAPI not working on Render?"
   - `$PORT` is an environment variable Render injects into every web service. Your app must listen on that port, not a hardcoded one. Render routes external traffic to it.

5. Click **Create Web Service** and wait for the build. The first build can take a few minutes as it installs dependencies.

Once the deploy finishes, Render gives you a URL like `https://your-app.onrender.com`. Visit it, and you should see your FastAPI app responding. The automatic OpenAPI docs will be at `/docs`.

## Environment variables and secrets

Never hardcode secrets in your code. In the Render dashboard, go to your service's **Environment** tab and add variables like `DATABASE_URL`, `API_KEY`, or `SECRET_KEY`. They're available to your app via `os.environ`.

If you're using a frontend hosted elsewhere, you'll also want to configure CORS. In FastAPI, add the `CORSMiddleware` with the allowed origins — and set those origins via environment variables so you can change them without redeploying.

## Databases and migrations: the part people forget

If your app uses a database, Render offers managed Postgres. Create one from the dashboard and copy its internal connection string into your `DATABASE_URL` environment variable.

Here's the catch: **Render does not run your migrations automatically.** Your app will start, try to query a table that doesn't exist, and fail. You have a few options:

- Run migrations manually from your local machine against the production database (fine for small projects, but risky).
- Add a pre-deploy command in Render's settings that runs `alembic upgrade head` or `python manage.py migrate` before the start command.
- Or, if you're using a simple SQLite or a schema that can be created at startup, do it in your app's startup event. For anything serious, use a proper migration tool like Alembic.

The cleanest approach is the pre-deploy command. It runs once, before your service starts, and if it fails, the deploy fails — which is exactly what you want.

## Going further: Docker, render.yaml, and background workers

The dashboard approach works, but for anything beyond a hobby project, consider infrastructure as code. Render supports a `render.yaml` file in your repo that defines your services, databases, environment variables, and even cron jobs. Commit it, and you can recreate your entire environment from scratch — a huge win for reproducibility.

If you need more control over the runtime — say, a specific system library or a non-Python build step — you can add a `Dockerfile`. Render detects it automatically and builds from it instead of using the default Python buildpack.

And if your app has background tasks (sending emails, processing uploads), don't run them in the web service. Create a separate **Background Worker** service that runs the same code but with a different start command, like `python worker.py`. This keeps your web service responsive.

## Common pitfalls and how to avoid them

- **Cold starts on the free tier.** Render's free web services spin down after 15 minutes of inactivity. The first request after that takes several seconds to wake up. It's fine for demos, but for production, consider a paid instance.
- **CORS misconfiguration.** Symptoms: your frontend can call the API from Postman but the browser blocks it. Double-check the allowed origins and that you're not using `*` with credentials.
- **Static files and uploads.** Render's filesystem is ephemeral — anything written to disk disappears on redeploy. For uploads or persistent files, use a persistent disk (paid) or an external service like S3.
- **Debugging.** When something goes wrong, check the **Logs** tab in your service dashboard. The logs show the full startup output, including any Python tracebacks. That's your first stop.

## The takeaway

The core loop is simple: push to git, Render builds, you get a URL. The first deploy is the hardest because of the little things — the `0.0.0.0` binding, the `$PORT`, the missing migration. Get those right once, and every subsequent deploy is just a `git push` away.

Start with the dashboard, get a working URL, then add `render.yaml` and a Dockerfile as your project grows. FastAPI makes the app side easy; Render makes the hosting side easy. The only real work is connecting the two — and now you know how.