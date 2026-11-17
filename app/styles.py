from base64 import b64encode
from pathlib import Path

import streamlit as st


def apply_styles():
    asset = Path(__file__).with_name("solar-array.jpg")
    photo = b64encode(asset.read_bytes()).decode("ascii") if asset.is_file() else ""
    st.markdown("""
<style>
.stApp, [data-testid="stHeader"] {background:#0c1420;color:#edf2f7;}
.stMainBlockContainer,.block-container {max-width:1220px;padding-top:3.25rem;padding-bottom:3rem;}
[data-testid="stSidebar"] {background:#101b29;border-right:1px solid #26354a;}
[data-testid="stSidebarUserContent"] {padding:0.95rem 1rem 1.5rem;}
.sc-brand {
 display:flex;align-items:center;gap:11px;padding:5px 0 20px;margin:0 0 11px;
 border-bottom:1px solid #2a394d;
}
.sc-wordmark {
 color:#f1f5f9;font-size:32px;font-weight:800;line-height:1.04;
 letter-spacing:-.055em;white-space:nowrap;
}
.sc-wordmark > span {color:#ffbe6b;}
.sc-wordmark small {
 display:block;color:#b4c3d3;font-size:12px;font-weight:500;letter-spacing:0;margin-top:6px;
}
.sc-mark {
 position:relative;width:46px;height:46px;flex:0 0 46px;
 background:#253245;border:1px solid #3c4c61;border-radius:12px;
}
.sc-mark::before {
 content:"";position:absolute;left:19px;top:6px;width:11px;height:11px;
 background:#ffbf70;border-radius:50%;
}
.sc-mark::after {
 content:"";position:absolute;left:9px;top:20px;width:25px;height:16px;
 border:1px solid #9ebce0;border-radius:2px;transform:skewX(-18deg);
 background:
  linear-gradient(90deg,transparent calc(33% - .5px),#9ebce0 calc(33% - .5px),#9ebce0 calc(33% + .5px),transparent calc(33% + .5px),transparent calc(66% - .5px),#9ebce0 calc(66% - .5px),#9ebce0 calc(66% + .5px),transparent calc(66% + .5px)),
  linear-gradient(transparent calc(50% - .5px),#9ebce0 calc(50% - .5px),#9ebce0 calc(50% + .5px),transparent calc(50% + .5px)),
  #395678;
}
.sc-hero {background-color:#172532;background-image:linear-gradient(90deg,#0a131ff7 0%,#0a131fe0 28%,#0a131f45 67%,#0a131f15 100%),url("data:image/jpeg;base64,PHOTO");background-size:cover;background-position:center 55%;border:1px solid #46515d;border-radius:13px;padding:32px 36px;min-height:305px;display:flex;flex-direction:column;justify-content:space-between;}
.sc-title {margin:0;font-size:clamp(24px,4vw,35px);line-height:1.12;letter-spacing:-.05em;color:#f4f6f8;}
.sc-hero time {display:block;margin-top:6px;color:#bfcedd;font-size:13px;}
.sc-power-label {font-size:13px;font-weight:650;color:#d3dfeb;}
.sc-number {font-size:clamp(46px,7vw,79px);letter-spacing:-.065em;line-height:1;font-weight:760;font-variant-numeric:tabular-nums;color:#fff;overflow-wrap:anywhere;}
.sc-status {margin-top:9px;color:#ffd29a;font-size:13px;font-weight:650;}
.sc-readings {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px;}
.sc-reading {background:#141f2e;border:1px solid #2d3c50;border-radius:9px;padding:15px 17px;display:flex;flex-direction:column;gap:5px;}
.sc-reading span {color:#bac8d9;font-size:13px;}
.sc-reading strong {color:#edf2f7;font-size:23px;font-variant-numeric:tabular-nums;}
.sc-reading.sc-solar strong {color:#ffbe6b;}
.sc-source {color:#acbdd0;margin:12px 0 3px;font-size:12px;}

.sc-loading {--sc-cycle:12s;position:fixed;inset:0;margin:0;z-index:10000000;isolation:isolate;overflow:hidden;width:100vw;max-width:none;padding:0;height:100vh;height:100dvh;border:0;border-radius:0;background:radial-gradient(ellipse at 50% 76%,#17395655,transparent 53%),linear-gradient(#070c18 0%,#0b1733 48%,#102951 85%,#142d42);text-align:center;box-shadow:0 0 0 100vmax #080f1d;animation:sc-reveal .6s ease-out;}
.sc-loading > .sc-loading-village {position:absolute;inset:0;display:block;width:100%;height:100%;min-height:100%;margin:0;padding:0;border:0;background-size:100% 100%;background-position:center bottom;background-repeat:no-repeat;pointer-events:none;z-index:0;}
.sc-loading::before {content:"";position:absolute;inset:0;background:linear-gradient(#060b1866,transparent 55%,#060b181a);z-index:1;pointer-events:none;}
.sc-loading::after {content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;box-shadow:inset 0 0 95px #02071166;z-index:4;}
.sc-loading-heading {position:absolute;top:8%;left:0;right:0;z-index:3;text-align:center;}
.sc-loading-brand {color:#f2f5f9;font-size:26px;font-weight:750;line-height:1.2;letter-spacing:-.06em;}
.sc-loading-brand > span {color:#ffcd87;}
.sc-loading-label {display:flex;align-items:center;justify-content:center;gap:9px;margin-top:14px;color:#edf2f7;font-size:12px;font-weight:500;letter-spacing:.18em;text-transform:uppercase;line-height:1.5;}
.sc-loading-dots {display:inline-flex;align-items:center;gap:4px;height:12px;}
.sc-loading-dots > i {width:4px;height:4px;border-radius:50%;background:#ffd494;opacity:.35;animation:sc-dots 1.65s ease-in-out infinite;}
.sc-loading-dots > i:nth-child(2) {animation-delay:.18s;}
.sc-loading-dots > i:nth-child(3) {animation-delay:.36s;}
.sc-loading-art {position:absolute;top:21%;left:50%;width:230px;height:230px;transform:translateX(-50%);z-index:2;}
.sc-sun {position:absolute;inset:10.4%;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 39% 34%,#fff4ba 0%,#ffd075 39%,#ffac42 70%,#e87829 100%);box-shadow:inset -4px -5px 17px #b84d2440,0 0 3px 2px #ffe1a9aa,0 0 22px #ffbe6b66,0 0 65px #ffb95e38,0 0 120px #ffb95e16;animation:sc-breathe 6s ease-in-out infinite;}
.sc-sun-corona {position:absolute;inset:-15px;border-radius:50%;background:radial-gradient(circle,transparent 42%,#ffcd7421 49%,#ffb95e12 54%,transparent 69%);animation:sc-corona 6s ease-in-out infinite;}
.sc-sun-surface {position:absolute;inset:-35%;opacity:.5;background:radial-gradient(ellipse at 35% 25%,#fff6cf 0 9%,transparent 20%),radial-gradient(ellipse at 58% 65%,#d98a27 0 8%,transparent 21%),radial-gradient(ellipse at 25% 57%,#fff0a9 0 10%,transparent 21%),radial-gradient(ellipse at 74% 38%,#ffc064 0 12%,transparent 24%),radial-gradient(ellipse at 51% 41%,#ffedb1 0 8%,transparent 19%);filter:blur(6px);animation:sc-solar-turn 80s linear infinite;}
.sc-sun-grain {position:absolute;inset:0;opacity:.19;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.18' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.8'/%3E%3C/svg%3E");mix-blend-mode:soft-light;}
.sc-sun-rays {position:absolute;inset:0;animation:sc-solar-turn 60s linear infinite;filter:drop-shadow(0 0 6px #ffbd6366);}
.sc-sun-rays > i {position:absolute;inset:0;transform:rotate(var(--ray-angle));}
.sc-sun-rays > i::before {content:"";position:absolute;left:46%;top:-9%;width:8%;height:23%;background:linear-gradient(#ffe9a9,#ffb955);clip-path:polygon(50% 0,100% 100%,0 100%);}
.sc-sun-rays > i:nth-child(even)::before {top:-5%;height:19%;background:linear-gradient(#ffdc8c,#f69b3d);}

.sc-loading-copy {position:fixed;top:63vh;top:63dvh;left:50%;transform:translateX(-50%);z-index:10000001;width:max-content;padding:0;border:0;background:none;box-shadow:none;text-align:center;pointer-events:none;text-shadow:0 2px 14px #07172e;}
.sc-loading-count {color:#f6e4cf;font-size:23px;font-weight:400;font-variant-numeric:tabular-nums;letter-spacing:.01em;line-height:1.2;}
.sc-loading-count > span {font-size:17px;margin-left:2px;color:#d7c4ac;}
.sc-loading-note {position:absolute;bottom:17px;left:15px;right:15px;z-index:3;color:#9bafc6;font-size:8px;letter-spacing:.17em;}
.sc-village-day {opacity:0;animation:sc-daylight var(--sc-cycle) cubic-bezier(.4,0,.2,1) both;}
.sc-daybreak {position:absolute;inset:0;z-index:1;pointer-events:none;opacity:0;background:radial-gradient(ellipse at 50% 85%,#ffc07466,transparent 65%),linear-gradient(transparent 30%,#ffad7238);mix-blend-mode:screen;animation:sc-dawn var(--sc-cycle) ease-in-out both;}
.sc-solar-journey {position:absolute;inset:0;opacity:0;animation:sc-solar-journey var(--sc-cycle) cubic-bezier(.4,0,.2,1) both;}
.sc-loading-heading {text-shadow:0 2px 18px #07172e88;}
.sc-loading-note {padding-bottom:env(safe-area-inset-bottom);text-shadow:0 1px 8px #07172e;color:#e1eaf3;}
@keyframes sc-daylight {0%,8% {opacity:0;}32%,64% {opacity:1;}94%,100% {opacity:0;}}
@keyframes sc-solar-visibility {0%,8% {opacity:0;}32%,64% {opacity:1;}94%,100% {opacity:0;}}
@keyframes sc-dawn {0%,8%,40%,55%,90%,100% {opacity:0;}24%,73% {opacity:.8;}}
@keyframes sc-solar-journey {
 0%,8% {opacity:0;transform:translate3d(24vw,32vh,0) scale(.65);}
 25% {opacity:1;transform:translate3d(8vw,7vh,0) scale(.9);}
 40%,54% {opacity:1;transform:translate3d(0,0,0) scale(1);}
 73% {opacity:.85;transform:translate3d(-14vw,18vh,0) scale(.85);}
 88%,100% {opacity:0;transform:translate3d(-24vw,36vh,0) scale(.6);}
}
@keyframes sc-solar-journey-mobile {
 0%,8% {opacity:0;transform:translate3d(18vw,24vh,0) scale(.65);}
 25% {opacity:1;transform:translate3d(7vw,5vh,0) scale(.9);}
 40%,54% {opacity:1;transform:translate3d(0,0,0) scale(1);}
 73% {opacity:.8;transform:translate3d(-10vw,10vh,0) scale(.85);}
 88%,100% {opacity:0;transform:translate3d(-18vw,24vh,0) scale(.6);}
}
@media (max-width:700px) and (prefers-reduced-motion:no-preference) {
 .sc-solar-journey {animation-name:sc-solar-journey-mobile;}
}
@keyframes sc-solar-turn {to {transform:rotate(360deg);}}
@keyframes sc-breathe {50% {transform:scale(1.025);}}
@keyframes sc-corona {50% {transform:scale(1.07);opacity:.65;}}
@keyframes sc-twinkle {to {opacity:.3;}}
@keyframes sc-dots {0%,70%,100% {opacity:.3;transform:scale(.8);}35% {opacity:1;transform:scale(1.15);}}
@keyframes sc-energy {from {transform:translateX(-100%);}to {transform:translateX(390%);}}
@keyframes sc-reveal {from {opacity:0;}to {opacity:1;}}
@media (prefers-reduced-motion:reduce) {
 .sc-solar-journey,.sc-loading,.sc-sun,.sc-sun-corona,.sc-sun-rays,.sc-sun-surface,.sc-loading-dots > i {animation:none;}
 .sc-solar-journey {animation:sc-solar-visibility var(--sc-cycle) ease-in-out both;}
 /* Keep the gentle background crossfade; only remove spatial movement. */
}
[data-testid="stButton"] button {background:#ffb95e;color:#181e28;border:1px solid #ffb95e;border-radius:7px;font-weight:650;}
[data-testid="stButton"] button:hover {background:#ffd097;color:#181e28;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:5px;}
[data-testid="stSidebar"] [data-testid="stButton"] button {
 display:flex;flex-direction:row;justify-content:flex-start !important;align-items:center;
 gap:10px;min-height:44px;width:100%;padding:8px 13px;
 background:transparent;color:#beccdb;border:1px solid transparent;border-radius:8px;
 text-align:left;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
 background:#1a293a;color:#f1f5f9;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
 background:#30271f;color:#ffcf92;border-color:#5d4630;
 box-shadow:inset 3px 0 #ffb95e;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:focus-visible {
 outline:2px solid #ffb95e;outline-offset:2px;
}
[data-testid="stSidebar"] [data-testid="stButton"] button > div,
[data-testid="stSidebar"] [data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
 justify-content:flex-start !important;text-align:left !important;margin-inline:0 !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button [data-testid="stIconMaterial"] {
 flex:0 0 23px;width:23px;text-align:center;
}
[data-testid="stSidebar"] [data-testid="stButton"] button p {
 font-size:14px;font-weight:600;text-align:left !important;
}
@media (max-width: 700px) {
 .sc-loading {position:fixed;inset:0;width:100vw;max-width:none;height:100vh;height:100dvh;margin:0;border:0;border-radius:0;touch-action:none;overscroll-behavior:none;}
 .sc-loading-heading {top:max(7vh,calc(env(safe-area-inset-top,0px) + 16px));top:max(7dvh,calc(env(safe-area-inset-top,0px) + 16px));padding:0 max(16px,env(safe-area-inset-right,0px)) 0 max(16px,env(safe-area-inset-left,0px));}
 .sc-loading-brand {font-size:clamp(22px,7vw,28px);}
 .sc-loading-label {font-size:11px;margin-top:10px;gap:8px;}
 .sc-loading-art {--sc-sun-size:clamp(116px,min(46vw,27vh),210px);--sc-sun-size:clamp(116px,min(46vw,27dvh),210px);top:calc(42% - var(--sc-sun-size) / 2);width:var(--sc-sun-size);height:var(--sc-sun-size);}
 .sc-loading > .sc-loading-village {background-size:cover;background-position:74% bottom;}
 .sc-loading-copy {top:66vh;top:66dvh;max-width:calc(100vw - 32px);}
 .sc-loading-count {font-size:clamp(20px,6vw,25px);}
 .sc-loading-count > span {font-size:15px;}
 .sc-loading-note {bottom:max(16px,env(safe-area-inset-bottom,0px));padding:0;left:max(16px,env(safe-area-inset-left,0px));right:max(16px,env(safe-area-inset-right,0px));font-size:8px;letter-spacing:.1em;line-height:1.5;}
 .sc-sun-surface {filter:blur(4px);}
 .stMainBlockContainer,.block-container {
  box-sizing:border-box;width:100%;padding:3.75rem 1rem 2rem;
 }
 .sc-hero {
  min-height:265px;padding:20px;background-position:62% center;
  background-image:linear-gradient(90deg,#0a131ff5,#0a131f78),url("data:image/jpeg;base64,PHOTO");
 }
 .sc-title {font-size:clamp(24px,7vw,32px);}
 .sc-number {font-size:clamp(44px,14vw,64px);}
 .sc-readings {grid-template-columns:minmax(0,1fr);gap:8px;}
 .sc-reading {flex-direction:row;justify-content:space-between;align-items:center;gap:12px;}
 .sc-reading strong {font-size:19px;white-space:nowrap;}
 .sc-source {font-size:12px;line-height:1.5;}
 [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
  flex-direction:column;gap:0.75rem;
 }
 [data-testid="stMain"] [data-testid="stHorizontalBlock"] > :is([data-testid="stColumn"],[data-testid="column"]) {
  flex:0 0 auto;width:100%;min-width:0;
 }
 [data-testid="stMain"] [data-testid="stButton"] button,
 [data-testid="stMain"] [data-testid="stNumberInput"] input {
  min-height:44px;
 }
}
/* Landscape phones and short windows share one compact, non-overlapping layout. */
@media (max-height:540px) {
 .sc-loading-heading {top:max(12px,env(safe-area-inset-top,0px));}
 .sc-loading-brand {font-size:20px;}
 .sc-loading-label {margin-top:6px;font-size:10px;}
 .sc-loading-art {--sc-sun-size:clamp(76px,28vh,145px);--sc-sun-size:clamp(76px,28dvh,145px);top:27%;width:var(--sc-sun-size);height:var(--sc-sun-size);}
 .sc-loading-copy {top:auto;bottom:max(7vh,calc(env(safe-area-inset-bottom,0px) + 10px));bottom:max(7dvh,calc(env(safe-area-inset-bottom,0px) + 10px));padding:0;}
 .sc-loading-count {font-size:19px;}
 .sc-loading-count > span {font-size:13px;}
 .sc-loading-note {display:none;}
 .sc-loading > .sc-loading-village {background-size:cover;background-position:center bottom;}
}
html:has(.sc-loading),body:has(.sc-loading) {overflow:hidden;overscroll-behavior:none;}
</style>
""".replace("PHOTO", photo), unsafe_allow_html=True)
