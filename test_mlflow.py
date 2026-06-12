# test_mlflow.py - run this standalone first
import os
os.environ["ENABLE_MLFLOW"] = "true"

from observability.tracker import tracker
tracker.configure(enabled=True, experiment_name="retrieval-agent")

print("enabled:", tracker._enabled)
print("mlflow:", tracker._mlflow)

tracker.set_tag("mode", "debug")
tracker.record("test_metric", 42.0)
tracker.flush(run_name="debug-run")

import os
print("mlruns exists:", os.path.exists("./mlruns"))