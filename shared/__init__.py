# shared/__init__.py
# Makes shared/ a proper Python package so worktrees can do:
#   from shared.config import EXCLUDED_DEALS
#   from shared.gatekeeper import LLMGatekeeper, CandidateDocument
#   from shared.telemetry import TelemetryLogger
