import os
import tempfile

# app.config instantiates Settings (and app.floors loads the floor config) at
# import time, so the environment has to be set before any `app` import.
_tmp = tempfile.mkdtemp(prefix="mdf-tests-")
os.environ["FLOORS_CONFIG_PATH"] = "config/floors.example.json"
os.environ["DB_PATH"] = os.path.join(_tmp, "history.db")
os.environ["OPNSENSE_API_KEY"] = "key"
os.environ["OPNSENSE_API_SECRET"] = "secret"
