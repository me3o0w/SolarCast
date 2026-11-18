"""Solar-themed loading feedback driven by actual application stages."""

from base64 import b64encode
from pathlib import Path
from html import escape
from time import monotonic, sleep

import streamlit as st


VILLAGE = b64encode(Path(__file__).with_name("loading-village.webp").read_bytes()).decode("ascii")
DAY_VILLAGE = b64encode(Path(__file__).with_name("loading-village-day.webp").read_bytes()).decode("ascii")
SCENE_DURATION = 12.0
LOADING_STAGES = {
    0: (0, "Connecting to live weather"),
    1: (33, "Estimating module temperature"),
    2: (67, "Preparing your solar outlook"),
    3: (100, "Your outlook is ready"),
}
SUN_RAYS = "".join(f'<i style="--ray-angle:{angle}deg"></i>' for angle in range(0, 360, 30))

PAGE_LOADERS = {
    "Overview": ("overview", "▦", "Preparing your solar generation outlook"),
    "Forgot password": ("recovery", "◇", "Opening password recovery"),
    "Next-day forecast": ("sunrise", "☀", "Preparing tomorrow’s solar outlook"),
    "Prediction history": ("archive", "◷", "Opening your saved predictions"),
    "Manual prediction": ("tuning", "⌘", "Preparing your prediction workspace"),
    "My Profile": ("profile", "◉", "Opening your profile"),
    "Power history": ("power", "ϟ", "Opening your generation history"),
    "Model performance": ("metrics", "▥", "Preparing model performance"),
    "Terms and Conditions": ("terms", "▤", "Opening Terms and Conditions"),
    "About this": ("about", "ⓘ", "Opening About SolarCast"),
}


class PageLoading:
    """A fresh, page-specific navigation scene; always clears on failure."""

    def __init__(self, page, enabled=True, minimum_duration=1.2, *, message=None):
        self.page = page
        self.enabled = enabled
        self.minimum_duration = minimum_duration
        self.message = message

    def __enter__(self):
        if self.enabled:
            variant, icon, message = PAGE_LOADERS[self.page]
            self.started = monotonic()
            self.placeholder = st.empty()
            segments = "".join(f'<i style="--segment:{index}"></i>' for index in range(10))
            self.placeholder.markdown(
                f'<section class="sc-page-loading sc-page-{variant}" role="status" '
                f'aria-live="polite" aria-busy="true" aria-label="Loading {escape(self.page)}">'
                '<div class="sc-page-loader-content">'
                f'<div class="sc-page-loader-icon" aria-hidden="true">{icon}</div>'
                f'<div class="sc-page-loader-title">{escape(self.page)}</div>'
                '<div class="sc-page-loader-label">Loading<span aria-hidden="true">...</span></div>'
                f'<div class="sc-page-loader-bar" aria-hidden="true">{segments}</div>'
                    f'<p>{escape(self.message or message)}</p></div></section>',
                unsafe_allow_html=True,
            )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.enabled:
            try:
                if exc_type is None:
                    sleep(max(0, self.minimum_duration - (monotonic() - self.started)))
            finally:
                self.placeholder.empty()
        return False


class SolarLoading:
    def __init__(self, minimum_duration=SCENE_DURATION, enabled=True):
        if minimum_duration <= 0:
            raise ValueError("Loading duration must be positive")
        self.minimum_duration = float(minimum_duration)
        self.enabled = enabled
        if not self.enabled:
            return
        self.placeholder = st.empty()
        self.status = st.empty()
        self.started = monotonic()
        self.last_update = None

    def update(self, stage=0):
        if type(stage) is not int or stage not in LOADING_STAGES:
            raise ValueError("Unknown loading stage")
        if not self.enabled:
            return
        progress, label = LOADING_STAGES[stage]
        # Status updates never replace the scenery, so crossfades keep running.
        if self.last_update is not None:
            sleep(max(0, .65 - (monotonic() - self.last_update)))
        if stage == 3:
            sleep(max(0, self.minimum_duration - .6 - (monotonic() - self.started)))
        self.status.markdown(
            f'<div class="sc-loading-copy" role="status" aria-live="polite" aria-label="{escape(label, quote=True)}">'
            f'<div class="sc-loading-count">{progress}<span>%</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        self.last_update = monotonic()

    def __enter__(self):
        if not self.enabled:
            return self
        self.started = monotonic()
        self.placeholder.markdown(
            f'<section class="sc-loading" style="--sc-cycle:{self.minimum_duration}s" aria-label="SolarCast day and night loading scene" aria-busy="true">'
            f'<div class="sc-loading-village sc-village-night" style="background-image:url(data:image/webp;base64,{VILLAGE})" aria-hidden="true"></div>'
            f'<div class="sc-loading-village sc-village-day" style="background-image:url(data:image/webp;base64,{DAY_VILLAGE})" aria-hidden="true"></div>'
            '<div class="sc-daybreak" aria-hidden="true"></div>'
            '<div class="sc-loading-heading"><div class="sc-loading-brand">Solar<span>Cast</span></div>'
            '<div class="sc-loading-label"><span>Loading</span>'
            '<span class="sc-loading-dots" aria-hidden="true"><i></i><i></i><i></i></span></div></div>'
            '<div class="sc-loading-art" aria-hidden="true"><div class="sc-solar-journey">'
            f'<div class="sc-sun-corona"></div><div class="sc-sun-rays">{SUN_RAYS}</div>'
            '<div class="sc-sun"><div class="sc-sun-surface"></div><div class="sc-sun-grain"></div></div></div></div>'
            '<div class="sc-loading-note">SOLARCAST by FEJ</div></section>',
            unsafe_allow_html=True,
        )
        self.update()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.enabled:
            return False
        # Let the introductory day/night cycle finish before clearing it.
        sleep(max(0, self.minimum_duration - (monotonic() - self.started)))
        if self.last_update is not None:
            sleep(max(0, .25 - (monotonic() - self.last_update)))
        self.status.empty()
        self.placeholder.empty()
        return False
