"""The "bright now covers your city" email sent to people who asked to be
notified about a region (see POST /admin/region-requests/notify-covered)."""
import html
import os

APP_STORE_URL = "https://apps.apple.com/app/id6797998962"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.racheltenenbaum.bright"

# Colors taken from the logo (public/logo.gif) and the app's light theme.
_BROWN = "#6e5204"
_CREAM = "#fffef0"
_BORDER = "#f1e3b3"


def build_region_live_email(
    first_name: str | None, region_name: str, app_url: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, plain text, html) for one recipient."""
    app_url = (app_url or os.getenv("APP_URL", "http://localhost:5173")).rstrip("/")
    # /plan is registered as a Universal Link (apple-app-site-association) and
    # an App Link (AndroidManifest), so on a phone with bright installed it
    # opens the app; anywhere else it opens bright on the web.
    open_url = f"{app_url}/plan"
    logo_url = f"{app_url}/logo.gif"
    name = (first_name or "").strip()
    greeting = f"Hi {name}," if name else "Hi,"

    subject = f"bright covers {region_name}"

    text = (
        f"{greeting}\n\n"
        f"You asked us to let you know when bright reaches {region_name}, and it's here: "
        f"you can now plan sunny and shady walks there.\n\n"
        f"Open bright: {open_url}\n\n"
        f"Don't have the app on this phone?\n"
        f"App Store: {APP_STORE_URL}\n"
        f"Google Play: {PLAY_STORE_URL}\n\n"
        f"Enjoy the sunshine,\nbright\n"
    )

    safe_greeting = html.escape(greeting)
    safe_region = html.escape(region_name)
    html_body = f"""<!doctype html>
<html><body style="margin:0;padding:0;background:{_CREAM};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_CREAM};">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border:1px solid {_BORDER};border-radius:16px;">
<tr><td align="center" style="padding:32px 32px 8px;">
<img src="{logo_url}" width="180" alt="bright" style="display:block;width:180px;height:auto;border:0;">
</td></tr>
<tr><td style="padding:16px 32px 0;font-family:Georgia,'Times New Roman',serif;font-size:24px;line-height:1.3;color:{_BROWN};">
bright now covers {safe_region}
</td></tr>
<tr><td style="padding:16px 32px 0;font-family:Helvetica,Arial,sans-serif;font-size:16px;line-height:1.6;color:#3d3420;">
<p style="margin:0 0 12px;">{safe_greeting}</p>
<p style="margin:0;">You asked us to let you know when bright reaches {safe_region}, and it's here: you can now plan sunny and shady walks there.</p>
</td></tr>
<tr><td style="padding:24px 32px 8px;">
<a href="{open_url}" style="display:inline-block;background:{_BROWN};color:{_CREAM};font-family:Helvetica,Arial,sans-serif;font-size:16px;font-weight:bold;text-decoration:none;padding:14px 28px;border-radius:10px;">Open bright</a>
</td></tr>
<tr><td style="padding:16px 32px 32px;font-family:Helvetica,Arial,sans-serif;font-size:14px;line-height:1.6;color:#7a6d4f;">
Don't have the app on this phone? Get it on the
<a href="{APP_STORE_URL}" style="color:{_BROWN};">App Store</a> or
<a href="{PLAY_STORE_URL}" style="color:{_BROWN};">Google Play</a>.
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    return subject, text, html_body
