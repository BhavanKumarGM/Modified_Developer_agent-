"""Regression test for the file-write half of audit item 2.4: Orchestrator
used to have its own bespoke `path.write_text(...)` calls in `_write_files`
and `_apply_edits`, duplicating (and bypassing the resolve_safe() containment
in) `file_service.write_file`. Now both route through file_service.
"""
import inspect

from app.orchestrator import orchestrator as orchestrator_module


def test_orchestrator_has_no_bespoke_write_text_calls():
    source = inspect.getsource(orchestrator_module)
    assert ".write_text(" not in source, (
        "Orchestrator must write files through app.services.file_service, "
        "not its own path.write_text(...) calls"
    )


def test_orchestrator_routes_writes_through_file_service():
    source = inspect.getsource(orchestrator_module)
    assert "file_service.write_generated_file(" in source
    assert "file_service.write_file(" in source
