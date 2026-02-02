"""
Smoke tests to verify all modules can be imported.
"""

def test_import_funsearch_core():
    import funsearch_core
    assert hasattr(funsearch_core, '__version__')


def test_import_llm():
    import llm
    assert hasattr(llm, '__version__')


def test_import_evaluator():
    import evaluator
    assert hasattr(evaluator, '__version__')


def test_import_sandbox():
    import sandbox
    assert hasattr(sandbox, '__version__')


def test_import_store():
    import store
    assert hasattr(store, '__version__')


def test_import_experiments():
    import experiments
    assert hasattr(experiments, '__version__')


def test_import_ui():
    import ui
    assert hasattr(ui, '__version__')
