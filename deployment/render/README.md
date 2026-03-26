# Render Demo Blueprint

Use the included `render.yaml` to spin up a demo-grade Agentic Brain deployment on Render.

1. **Fork** `joseph-webber/agentic-brain` (Render needs repo access).
2. Go to https://render.com/deploy and paste the URL of your fork. Render detects `render.yaml` and
   provisions three services: the FastAPI web app, a private Neo4j service, and managed Redis.
3. Accept the defaults or customize the following demo credentials when prompted:
   - `NEO4J_PASSWORD` (defaults to `Brain2026`)
   - `JWT_SECRET` (auto-generated; copy it if you need API clients)
4. Click **Apply**. Render links the services on a private network (`bolt://neo4j:7687` and the
   injected Redis connection string) and builds from the repo.
5. After deploy, Render provides a URL such as `https://agentic-brain.onrender.com` that you can
   share for demos.

> Tip: The blueprint selects Render's Sydney region to match the project's latency assumptions.
> Change `region` in `render.yaml` if you need another geography.
