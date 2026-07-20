"""Regression tests for app.services.import_check — catches the real bug
where generated code imports sibling components that were never actually
generated (e.g. BillingScreen.tsx importing './InvoiceTable' when no
InvoiceTable.tsx exists), which otherwise only surfaces later as a wall of
tsc "Cannot find module" errors with no recovery path.
"""
from app.services.import_check import find_missing_local_imports


def test_detects_missing_sibling_import():
    files = [
        {
            "path": "src/components/BillingScreen.tsx",
            "content": "import InvoiceTable from './InvoiceTable'\nimport Payments from './Payments'\n",
        }
    ]
    missing = find_missing_local_imports(files)
    resolved = {m.resolved_hint for m in missing}
    assert resolved == {"src/components/InvoiceTable", "src/components/Payments"}


def test_does_not_flag_imports_that_resolve_to_a_generated_file():
    files = [
        {"path": "src/components/BillingScreen.tsx", "content": "import Invoice from './Invoice'\n"},
        {"path": "src/components/Invoice.tsx", "content": "export default function Invoice() { return null }\n"},
    ]
    assert find_missing_local_imports(files) == []


def test_extension_differences_do_not_cause_false_positives():
    files = [
        {"path": "src/App.tsx", "content": "import Utils from './utils/helpers'\n"},
        {"path": "src/utils/helpers.ts", "content": "export const x = 1\n"},
    ]
    assert find_missing_local_imports(files) == []


def test_ignores_non_relative_npm_package_imports():
    files = [
        {"path": "src/App.tsx", "content": "import React from 'react'\nimport { z } from 'zod'\n"},
    ]
    assert find_missing_local_imports(files) == []


def test_ignores_relative_asset_and_stylesheet_imports():
    files = [
        {"path": "src/App.tsx", "content": "import './App.css'\nimport logo from './logo.svg'\n"},
    ]
    assert find_missing_local_imports(files) == []


def test_reports_importer_and_specifier():
    files = [{"path": "src/components/BillingScreen.tsx", "content": "import X from './InvoiceTable'\n"}]
    missing = find_missing_local_imports(files)
    assert len(missing) == 1
    assert missing[0].importer == "src/components/BillingScreen.tsx"
    assert missing[0].specifier == "./InvoiceTable"


def test_resolves_parent_directory_traversal():
    files = [
        {"path": "src/pages/Billing.tsx", "content": "import Card from '../shared/Card'\n"},
    ]
    missing = find_missing_local_imports(files)
    assert missing[0].resolved_hint == "src/shared/Card"
