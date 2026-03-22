import pytest
from core.state_manager import StateManager, AppState


@pytest.fixture
def sm():
    return StateManager()


def test_StateManager_initial_empty(sm):
    assert sm.is_active(AppState.LOADING_DATA) is False
    assert sm.any_of(AppState.LOADING_DATA, AppState.SAVING_DATA) is False


def test_StateManager_enter_context_manager(sm):
    with sm.enter(AppState.LOADING_DATA):
        assert sm.is_active(AppState.LOADING_DATA) is True
    # After context, state should be removed
    assert sm.is_active(AppState.LOADING_DATA) is False


def test_StateManager_enter_multiple_states(sm):
    with sm.enter(AppState.LOADING_DATA):
        with sm.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):
            assert sm.is_active(AppState.LOADING_DATA) is True
            assert sm.is_active(AppState.PROGRAMMATIC_TEXT_CHANGE) is True
        assert sm.is_active(AppState.PROGRAMMATIC_TEXT_CHANGE) is False
    assert sm.is_active(AppState.LOADING_DATA) is False


def test_StateManager_any_of(sm):
    with sm.enter(AppState.SAVING_DATA):
        assert sm.any_of(AppState.LOADING_DATA, AppState.SAVING_DATA) is True
        assert sm.any_of(AppState.LOADING_DATA, AppState.AUTO_FIXING) is False


def test_StateManager_set_active(sm):
    sm.set_active(AppState.AUTO_FIXING, True)
    assert sm.is_active(AppState.AUTO_FIXING) is True

    sm.set_active(AppState.AUTO_FIXING, False)
    assert sm.is_active(AppState.AUTO_FIXING) is False


def test_StateManager_clear(sm):
    sm.set_active(AppState.LOADING_DATA, True)
    sm.set_active(AppState.SAVING_DATA, True)
    sm.clear()
    assert sm.is_active(AppState.LOADING_DATA) is False
    assert sm.is_active(AppState.SAVING_DATA) is False


def test_StateManager_enter_exits_on_exception(sm):
    try:
        with sm.enter(AppState.CLOSING):
            assert sm.is_active(AppState.CLOSING) is True
            raise RuntimeError("Test error")
    except RuntimeError:
        pass
    # State should be cleaned up even after exception
    assert sm.is_active(AppState.CLOSING) is False


def test_AppState_all_states_exist():
    # Ensure all enum members are accessible
    required = [
        AppState.ADJUSTING_CURSOR, AppState.ADJUSTING_SELECTION,
        AppState.PROGRAMMATIC_TEXT_CHANGE, AppState.LOADING_DATA,
        AppState.SAVING_DATA, AppState.REVERTING_DATA, AppState.CLOSING,
        AppState.AUTO_FIXING, AppState.PASTING_BLOCK, AppState.UNDOING_PASTE,
    ]
    for state in required:
        assert isinstance(state, AppState)
