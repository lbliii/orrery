"""Railway entry point that avoids re-executing ``runs.worker`` as a module.

``runs`` exports worker classes for the rest of the application.  Launching
``python -m runs.worker`` therefore loads the module during package import and
then asks Python to execute it again.  This tiny entry module keeps the public
imports intact while giving Railway one unambiguous process target.
"""

from __future__ import annotations

from .worker import main

if __name__ == "__main__":  # pragma: no cover - process launcher
    raise SystemExit(main())
