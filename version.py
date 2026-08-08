"""The running build's release string.

Release builds get PCEXPRESS_VERSION from the Dockerfile's VERSION build-arg,
which the shared release workflow supplies. Anything else is a local build and
says so.

The release scheme has exactly three shapes and all three describe something
that was published:

    26.8.1                       released
    26.8.1-rc.1                  candidate
    26.8.1-nightly.202608080642  built from a merge to main

A checkout on someone's laptop is none of those, so it claims no version rather
than inventing one. Mirrors internal/version in the Go services.
"""

import os

LOCAL_VERSION = "0.0.0-dev"

__version__ = os.getenv("PCEXPRESS_VERSION", "").strip() or LOCAL_VERSION
