"""Tool-edge caps. Keep aligned with ``application.investigation.state``.

Imported here so tools never load the investigation package (that package
imports the graph, which imports the gateway — a cycle).
"""

SIGNAL_CAP = 20
KNOWLEDGE_CAP = 4
