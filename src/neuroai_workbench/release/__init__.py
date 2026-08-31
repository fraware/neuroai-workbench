"""Candidate observatory-graph release compiler.

Mechanical verification is not authorization. This package must never set
``release_authorized=true`` or create a git tag.
"""

from .compiler import ReleaseCompiler, compile_candidate_release

__all__ = ["ReleaseCompiler", "compile_candidate_release"]
