"""Use the selected installed engine for the same browser regression suite."""
import os


def browser_engine():
    engine = os.environ.get("ENGINE", "chromium")
    if engine not in ("chromium", "firefox", "webkit"):
        raise ValueError("ENGINE must be chromium, firefox, or webkit")
    return engine


def launch_browser(playwright):
    return getattr(playwright, browser_engine()).launch()
