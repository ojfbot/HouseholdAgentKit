"""Pin the hello-world gate's date so the suite does not depend on the calendar (the gate tightens on Nov 25)."""
import os

os.environ.setdefault("DE_AS_OF", "2026-11-19")
