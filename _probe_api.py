import warnings; warnings.filterwarnings("ignore")
import inspect
from agent_framework import Workflow, WorkflowRunResult
print("Workflow methods:", [m for m in dir(Workflow) if not m.startswith("_")])
for m in ["run","run_stream"]:
    if hasattr(Workflow, m):
        try:
            print("  .%s%s" % (m, inspect.signature(getattr(Workflow,m))))
        except Exception as e:
            print("  err", m, e)
print("RunResult methods:", [m for m in dir(WorkflowRunResult) if not m.startswith("_")])
