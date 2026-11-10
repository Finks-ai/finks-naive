import json
import re
import sys
import traceback

from loguru import logger

# Finks Signals run id (header `x-finks-run`), bound as `run_id` for the request in app/main.py.
# Anything else is ignored.
RUN_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def _json_line(message):
    """One JSON object per line on stdout (CloudWatch; Finks Signals reads the fields)."""
    record = message.record
    line = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": f"{record['name']}:{record['function']}:{record['line']}",
        "message": record["message"],
        **record["extra"],
    }
    if record["exception"]:
        line["exception"] = "".join(traceback.format_exception(*record["exception"]))
    sys.stdout.write(json.dumps(line, default=str) + "\n")
    sys.stdout.flush()


logger.remove()
logger.add(_json_line, level="DEBUG")
