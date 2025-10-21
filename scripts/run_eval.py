# scripts/run_eval.py
import json
from src.eval_harness import run_smoke

if __name__ == "__main__":
    result = run_smoke(include_scheduler=True)
    print(json.dumps(result, indent=2))

