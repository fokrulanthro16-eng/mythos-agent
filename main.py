import os
import shutil
import psutil
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mythos Autonomous Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "Healthy"}

@app.post("/diagnose")
async def run_diagnostics():
    return {
        "cpu_usage": f"{psutil.cpu_percent()}%",
        "ram_usage": f"{psutil.virtual_memory().percent}%",
        "disk_free": f"{shutil.disk_usage('C:/').free // (2**30)} GB free",
        "message": "System diagnostics completed successfully."
    }

@app.post("/clean")
async def run_cleanup():
    temp_dir = os.environ.get('TEMP')
    count = 0
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                count += 1
        except:
            continue
    return {"message": f"Successfully deleted {count} temporary files."}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mythos Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-12">
        <h1 class="text-4xl font-bold text-emerald-400 mb-8">Mythos Dashboard</h1>
        <div class="grid grid-cols-3 gap-6">
            <button onclick="checkHealth()" class="bg-blue-600 p-6 rounded-xl font-bold">Check Health</button>
            <button onclick="runDiagnostics()" class="bg-amber-600 p-6 rounded-xl font-bold">Run Diagnostics</button>
            <button onclick="runCleanup()" class="bg-rose-600 p-6 rounded-xl font-bold">Start Clean</button>
        </div>
        <pre id="output" class="mt-8 bg-slate-900 p-6 rounded-xl text-emerald-400 font-mono"></pre>

        <script>
            async function fetchAction(endpoint, method='GET') {
                const res = await fetch(endpoint, { method });
                const data = await res.json();
                document.getElementById('output').innerText = JSON.stringify(data, null, 2);
            }
            const checkHealth = () => fetchAction('/health');
            const runDiagnostics = () => fetchAction('/diagnose', 'POST');
            const runCleanup = () => fetchAction('/clean', 'POST');
        </script>
    </body>
    </html>
    """