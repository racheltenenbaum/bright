from src.region_emails import APP_STORE_URL, PLAY_STORE_URL, build_region_live_email


def test_greets_user_by_first_name_in_text_and_html():
    subject, text, html = build_region_live_email("Dana", "Stuttgart", app_url="https://app.example")
    assert text.startswith("Hi Dana,")
    assert "Hi Dana," in html


def test_falls_back_to_plain_greeting_without_a_name():
    for name in (None, "", "   "):
        _, text, html = build_region_live_email(name, "Stuttgart", app_url="https://app.example")
        assert text.startswith("Hi,")
        assert "Hi," in html


def test_escapes_name_in_html():
    _, _, html = build_region_live_email("<b>x</b>", "Stuttgart", app_url="https://app.example")
    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_names_the_city_in_subject_and_body():
    subject, text, html = build_region_live_email("Dana", "Stuttgart", app_url="https://app.example")
    assert "Stuttgart" in subject
    assert "Stuttgart" in text
    assert "Stuttgart" in html


def test_links_open_the_app_and_both_stores_and_shows_logo():
    _, text, html = build_region_live_email("Dana", "Stuttgart", app_url="https://app.example")
    # /plan is a Universal Link / App Link path, so it opens the installed app.
    assert "https://app.example/plan" in text
    assert 'href="https://app.example/plan"' in html
    assert 'src="https://app.example/logo.gif"' in html
    for url in (APP_STORE_URL, PLAY_STORE_URL):
        assert url in text
        assert f'href="{url}"' in html


def test_subject_wording():
    subject, _, _ = build_region_live_email("Dana", "Stuttgart", app_url="https://app.example")
    assert subject == "bright covers Stuttgart"


def test_html_has_no_separate_headline():
    _, _, html = build_region_live_email("Dana", "Stuttgart", app_url="https://app.example")
    assert "covers Stuttgart" not in html
