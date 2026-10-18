from app.naming import display_name
from app.timewindow import DEFAULT_WINDOW, WINDOW_OPTIONS, resolve_window
from app.tls import verify_arg


def test_display_name_prefers_hostname():
    assert display_name("laptop", "Apple", "AA:BB:CC:DD:EE:FF") == "laptop"


def test_display_name_falls_back_to_vendor_then_mac():
    assert display_name(None, "Apple", "AA:BB:CC:DD:EE:FF") == "Apple (AA:BB:CC:DD:EE:FF)"
    assert display_name(None, None, "AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"


def test_resolve_window_accepts_known_and_defaults_unknown():
    for window in WINDOW_OPTIONS:
        assert resolve_window(window) == window
    assert resolve_window("bogus") == DEFAULT_WINDOW
    assert resolve_window(None) == DEFAULT_WINDOW


def test_verify_arg_ca_file_wins_over_bool():
    assert verify_arg(False, "/ca.pem") == "/ca.pem"
    assert verify_arg(True, None) is True
    assert verify_arg(False, None) is False
