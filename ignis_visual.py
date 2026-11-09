"""Componentes de presentación de IGNIS UY.

Solo cambia la UI. No altera importación de datos, armonización,
correspondencia de observaciones ni métricas científicas.
"""
import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def apply_visual_theme():
    st.markdown("""<style>
    /* IGNIS design system: panels almost flush to the viewport, crisp edges. */
    .stApp {
      --ignis-radius-panel: 4px;
      --ignis-radius-control: 5px;
      --ignis-border: rgba(88, 151, 186, .32);
      background:linear-gradient(155deg,#091324 0%,#070e1b 70%,#06101d 100%)!important;
    }
    .block-container,[data-testid="stMainBlockContainer"] {
      width:100%!important;
      max-width:none!important;
      box-sizing:border-box;
      padding: .9rem clamp(.6rem,1.15vw,1.35rem) 2.6rem!important;
    }
    /* Sidebar premium: marca compacta + navegación tipo producto. */
    section[data-testid="stSidebar"] {
      background:linear-gradient(175deg,#0b1b2e 0%,#0b182a 55%,#0a1424 100%)!important;
      border-right:1px solid #30516a;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
      padding:1.2rem .78rem 1.65rem!important;
    }
    .ignis-side-brand {
      display:flex;align-items:center;gap:.85rem;
      padding:0 .25rem .9rem;border-bottom:1px solid rgba(112,168,194,.17);
    }
    .ignis-side-logo {
      width:51px;height:51px;flex:0 0 51px;
      display:flex;align-items:center;justify-content:center;
      background:#0e263c;border:1px solid #426d87;border-radius:5px;
    }
    .ignis-side-logo img{width:43px;height:43px;object-fit:contain}
    .ignis-side-logo-fallback{font-size:27px;color:#60cbdc}
    .ignis-side-brand-copy{display:flex;flex-direction:column;min-width:0}
    .ignis-side-brand-copy strong{
      color:#f2f8fd;font-size:1.17rem;letter-spacing:.012em;line-height:1.2;
    }
    .ignis-side-brand-copy strong span{color:#64d7ec}
    .ignis-side-brand-copy small{
      color:#8daec2;font-size:.60rem;font-weight:750;
      letter-spacing:.115em;margin-top:.38rem;
    }
    .ignis-side-project{
      background:rgba(19,49,73,.48);border:1px solid rgba(83,141,170,.2);
      color:#a9d2e4;padding:8px 10px;margin:12px 0 19px;
      border-radius:4px;font-size:.68rem;font-weight:740;letter-spacing:.09em;
    }
    .ignis-side-project span{color:#4ecfe1;padding:0 .26rem}
    .ignis-side-section-title{
      border-top:1px solid rgba(123,166,190,.17);
      padding:17px 7px 9px;margin-top:8px;
      color:#85a8bf;font-weight:800;letter-spacing:.13em;font-size:.64rem;
    }
    /* Los radio buttons siguen siendo accesibles, pero su indicador
       nativo no se muestra; la selección se representa mediante una línea. */
    section[data-testid="stSidebar"] div[role="radiogroup"]{
      display:flex;flex-direction:column;gap:2px;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
      position:relative;display:flex;align-items:center;width:100%;
      box-sizing:border-box;min-height:38px;padding:8px 9px 8px 12px;
      border:1px solid transparent;border-radius:4px;
      background:transparent;color:#b7d0df;
      font-size:.81rem;font-weight:520;cursor:pointer;
      transition:background .15s ease,color .15s ease,border-color .15s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label
      > :first-child:not([data-testid="stMarkdownContainer"]):has(input[type="radio"]){
      position:absolute!important;opacity:0!important;
      width:1px!important;height:1px!important;overflow:hidden!important;
      pointer-events:none!important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label
      [data-testid="stMarkdownContainer"] p{
      margin:0!important;line-height:1.25!important;font-size:.81rem!important;
      white-space:normal;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
      background:linear-gradient(90deg,rgba(29,96,122,.48),rgba(13,41,66,.45));
      border-color:rgba(79,166,196,.37);color:#f7fbff;font-weight:700;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before{
      content:"";position:absolute;left:-1px;top:5px;bottom:5px;
      width:3px;background:#46d2e7;border-radius:1px;
      box-shadow:0 0 12px rgba(52,199,228,.34);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
      background:rgba(41,93,120,.22);color:#effaff;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:focus-within{
      outline:2px solid rgba(83,216,235,.72);outline-offset:1px;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"]{
      margin:0 0 .35rem!important;
    }
    section[data-testid="stSidebar"] label:not(:has(input[type="radio"])){
      color:#bbd5e2;font-size:.79rem;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"]>div{
      background:#102a41!important;border:1px solid #36536a!important;
      border-radius:4px!important;min-height:42px;
    }
    section[data-testid="stSidebar"] [data-testid="stSelectbox"],
    section[data-testid="stSidebar"] [data-testid="stMultiSelect"]{
      margin-bottom:.35rem;
    }
    section[data-testid="stSidebar"] [data-testid="stLinkButton"] a{
      width:100%;justify-content:flex-start;
      color:#c7e2f1!important;background:#0d253b!important;
      border:1px solid rgba(91,147,178,.35)!important;
      font-size:.77rem!important;min-height:39px!important;
      border-radius:4px!important;
    }
    section[data-testid="stSidebar"] [data-testid="stLinkButton"] a:hover{
      background:#173750!important;border-color:#6acadd!important;
    }
    .ignis-side-data-status,.ignis-side-empty{
      background:rgba(12,45,63,.55);
      border:1px solid rgba(68,160,184,.27);
      border-radius:4px;padding:10px 11px;
      color:#b7d8e5;font-size:.75rem;margin:9px 0 12px;
    }
    .ignis-side-status-dot{
      display:inline-block;width:6px;height:6px;background:#58c8d6;
      border-radius:50%;margin-right:8px;vertical-align:middle;
      box-shadow:0 0 7px rgba(68,186,208,.26);
    }
    .ignis-side-empty .ignis-side-status-dot{background:#7f9da9;box-shadow:none}
    .ignis-side-empty small{
      display:block;color:#88a7ba;line-height:1.5;
      padding-left:14px;margin-top:7px;font-size:.73rem;
    }
    .ignis-side-footer{
      margin:16px 2px 0;padding:12px 6px 4px;
      border-top:1px solid rgba(103,154,181,.25);
      font-size:.69rem;color:#8aa7b7;line-height:1.65;
    }
    .ignis-side-footer-accent{
      display:inline-block;width:18px;height:2px;background:#43c8db;
      vertical-align:middle;margin-right:7px;
    }

    [data-testid="stMetric"] {
      background:linear-gradient(125deg,#14283f,#0d2036)!important;
      border:1px solid var(--ignis-border)!important;
      border-radius:var(--ignis-radius-panel)!important;
      padding:16px!important;min-height:102px;
      box-shadow:none!important;
    }
    [data-testid="stMetricValue"]{color:#f0faff!important}
    .stButton>button,.stDownloadButton>button,.stLinkButton>a {
      border-radius:var(--ignis-radius-control)!important;
      box-shadow:none!important;
      min-height:43px;
      transition:border-color .17s ease,background-color .17s ease;
    }
    .stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"] {
      background:linear-gradient(95deg,#087eb8,#125fc5)!important;
      border:1px solid #2689db!important;color:white!important;
    }
    .stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover {
      border-color:#63c9e6!important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
      border-radius:var(--ignis-radius-panel)!important;
    }
    div[data-baseweb="select"]>div,div[data-baseweb="input"] {
      border-radius:var(--ignis-radius-control)!important;
    }
    .ignis-ui-kicker {
      font-size:.74rem;font-weight:800;letter-spacing:.15em;
      text-transform:uppercase;color:#67ddef;margin-bottom:.65rem;
    }
    .ignis-ui-header{margin:0 0 1.1rem}
    .ignis-ui-header h1 {
      font-size:clamp(1.8rem,3vw,2.55rem)!important;
      margin:.15rem 0 .45rem;line-height:1.2;
    }
    .ignis-ui-header p{color:#b8d2e2;margin:0;line-height:1.6}
    /* Continuous institutional header; no floating rounded container. */
    .ignis-ui-topbar {
      display:flex;align-items:center;justify-content:space-between;
      gap:15px;flex-wrap:wrap;padding:.75rem 1.15rem;margin:0;
      border:1px solid #315672;border-bottom:0;
      border-radius:0;background:rgba(7,19,34,.97);
    }
    .ignis-ui-wordmark {
      display:flex;align-items:center;gap:12px;
      font-size:1.15rem;font-weight:850;color:#f5faff;
    }
    .ignis-ui-wordmark img {
      width:43px;height:43px;object-fit:contain;border-radius:3px;
    }
    .ignis-ui-wordmark small {
      display:block;color:#a7c6d8;font-size:.75rem;font-weight:500;
    }
    .ignis-ui-links{display:flex;flex-wrap:wrap;gap:8px}
    .ignis-ui-links a {
      color:#d3ecff;text-decoration:none;border:1px solid #38617a;
      border-radius:4px;padding:9px 13px;font-size:.84rem;font-weight:650;
    }
    .ignis-ui-links a:hover{background:#163958;border-color:#62d5eb}
    .ignis-ui-hero {
      border:1px solid #315672;border-radius:0;
      min-height:370px;background-color:#0e294b;
      background-size:cover;background-position:center right;
      display:flex;flex-direction:column;justify-content:center;
      padding:clamp(24px,4.2vw,64px);
      margin:0 0 1rem;
      box-shadow:none;
    }
    .ignis-ui-hero h1 {
      font-size:clamp(2.6rem,5.8vw,5rem)!important;
      line-height:1.02;margin:.15rem 0 1rem;color:#f5faff!important;
    }
    .ignis-ui-hero h1 span{color:#6ad3ff!important}
    .ignis-ui-hero p {
      font-size:1.02rem;line-height:1.65;
      color:#d6e7f5;max-width:590px;margin:0;
    }
    .ignis-ui-hero-facts {
      display:flex;flex-wrap:wrap;gap:12px;
      margin-top:1.6rem;font-size:.82rem;color:#bddbea;
    }
    .ignis-ui-hero-facts span {
      padding:.55rem .85rem;border-radius:4px;
      background:rgba(8,24,43,.70);
      border:1px solid rgba(114,180,209,.28);
    }
    .ignis-ui-card {
      background:#10263c;border:1px solid var(--ignis-border);
      border-radius:var(--ignis-radius-panel);
      padding:18px;min-height:142px;margin-bottom:10px;
      box-shadow:none;
    }
    .ignis-ui-card b{font-size:1.02rem;color:#e9f8ff}
    .ignis-ui-card p{color:#bcd5e3;margin:.55rem 0 0;line-height:1.55}
    .ignis-ui-subtitle{color:#a9c9dc;font-size:.9rem}
    .ignis-ui-bar {
      height:2px;background:linear-gradient(90deg,#37c4db,transparent);
      margin:.6rem 0 1.25rem;
    }
    @media(max-width:850px) {
      .block-container,[data-testid="stMainBlockContainer"] {
        padding:.8rem .65rem 1.75rem!important;
      }
      .ignis-ui-topbar {padding:.65rem .75rem}
      .ignis-ui-hero {
        min-height:300px;background-position:66% center;
        padding:clamp(22px,5vw,36px);
      }
      .ignis-ui-links a{padding:7px 9px;font-size:.76rem}
      .ignis-ui-hero-facts{gap:6px}
      .ignis-ui-card{min-height:0}
    }
    </style>""",unsafe_allow_html=True)
    st.markdown(_reference_styles(),unsafe_allow_html=True)



def _reference_styles():
    """Ajustes visuales de la maqueta seleccionada: no modifica los datos."""
    from urllib.parse import quote
    css = r"""<style>
    .stApp{--ignis-aqua:#35e4ee;background:radial-gradient(ellipse at 50% 0%,#071c30,#04111e 70%)!important}
    .block-container,[data-testid="stMainBlockContainer"]{padding-top:.35rem!important}
    .ignis-ui-topbar{min-height:76px;padding:12px 20px!important;background:#061726!important;border-color:#306281!important}
    .ignis-ui-wordmark{font-size:1.16rem!important;gap:14px}
    .ignis-ui-wordmark img{width:52px!important;height:52px!important}
    .ignis-ui-wordmark small{font-size:.79rem!important;margin-top:5px}
    .ignis-ui-links a{padding:10px 15px!important;border-color:#386980!important;color:#e2f8ff!important}
    .ignis-ui-hero{
      position:relative;overflow:hidden;isolation:isolate;
      min-height:421px!important;padding:clamp(29px,3.3vw,62px)!important;
      background-size:cover!important;background-position:center right!important;
      margin-bottom:14px!important;border-color:#326782!important}
    .ignis-ui-hero::after{
      content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;
      background:linear-gradient(90deg,rgba(0,8,22,.58),rgba(0,14,27,.12) 70%)}
    .ignis-ui-hero .ignis-ui-kicker{
      font-size:.83rem!important;letter-spacing:.13em!important;
      color:#b9dbe5!important;max-width:680px;padding-left:16px;
      border-left:3px solid #22dced;margin-bottom:15px}
    .ignis-ui-hero h1{
      font-size:clamp(3.2rem,5.45vw,5.3rem)!important;line-height:1.03!important;
      font-weight:850!important;letter-spacing:-.035em!important;
      color:#fbfdff!important;text-shadow:0 4px 20px #031124}
    .ignis-ui-hero h1 span{
      background:linear-gradient(100deg,#52edf6,#47aaff);
      -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
    .ignis-ui-hero p{font-size:1.05rem!important;max-width:575px!important;color:#ecf8ff!important;text-shadow:0 2px 12px #021226}
    .ignis-ui-hero-facts{gap:12px!important;margin-top:20px!important}
    .ignis-ui-hero-facts span{
      display:inline-flex;align-items:center;gap:7px;font-size:.8rem!important;
      border:1px solid #3a8298!important;background:rgba(3,32,51,.76)!important;
      padding:9px 12px!important;border-radius:3px!important}
    .ignis-ui-hero-facts svg{height:17px;width:17px;stroke:#36e4ee;flex:none}
    div.st-key-hero_to_history button,div.st-key-hero_to_dashboard button,div.st-key-hero_to_upload button{
      min-height:60px!important;border-radius:3px!important;padding:0 18px!important;
      border:1px solid #3a829d!important;display:flex;align-items:center;gap:13px;
      background:linear-gradient(90deg,#06344a,#07192b)!important;
      font-size:1.02rem!important;font-weight:730!important}
    div.st-key-hero_to_history button{
      background:linear-gradient(105deg,#04bbcf,#028db1)!important;color:white!important;
      box-shadow:0 7px 25px rgba(0,207,239,.18)!important}
    div.st-key-hero_to_history button:hover,div.st-key-hero_to_dashboard button:hover,div.st-key-hero_to_upload button:hover{
      border-color:#65e7ef!important;transform:translateY(-1px)}
    div.st-key-hero_to_history button p,div.st-key-hero_to_dashboard button p,div.st-key-hero_to_upload button p{
      flex:1!important;text-align:left!important;font-size:1.01rem!important}
    div.st-key-hero_to_history button::after,div.st-key-hero_to_dashboard button::after,div.st-key-hero_to_upload button::after{
      content:"→";font-size:1.36rem;margin-left:auto;opacity:.88}
    div.st-key-hero_to_history button::before,div.st-key-hero_to_dashboard button::before,div.st-key-hero_to_upload button::before{
      content:"";width:21px;height:21px;flex:0 0 21px;background:#a6faff;
      -webkit-mask-size:contain;-webkit-mask-repeat:no-repeat;-webkit-mask-position:center;
      mask-size:contain;mask-repeat:no-repeat;mask-position:center}
    .ignis-home-section-title{
      position:relative;font-size:1.7rem;font-weight:790;color:#f4fcff;
      margin:16px 0;padding-left:20px;letter-spacing:-.02em}
    .ignis-home-section-title::before{
      content:"";position:absolute;left:0;top:4px;bottom:4px;width:4px;background:#0fd6e8}
    .ignis-ui-card{
      position:relative;isolation:isolate;overflow:hidden;min-height:195px!important;
      padding:20px 22px!important;border-radius:3px!important;
      border:1px solid #28627c!important;background:linear-gradient(125deg,#092c42,#061c2f)!important}
    .ignis-ui-card::after{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;opacity:.64}
    .ignis-ui-card--heat::after{
      background:radial-gradient(circle at 94% 79%,#d78028 0 2px,transparent 13px),
      radial-gradient(circle at 82% 68%,#f57d28 0 3px,transparent 20px),
      radial-gradient(circle at 95% 78%,rgba(234,99,36,.64),transparent 32%),
      repeating-linear-gradient(23deg,transparent 0 29px,#24879f28 30px,transparent 31px)}
    .ignis-ui-card--atlas::after{
      background:repeating-radial-gradient(ellipse at 91% 65%,transparent 0 11px,#05a7ca4d 12px,transparent 13px,transparent 24px)}
    .ignis-ui-card--trace::after{
      background:repeating-linear-gradient(90deg,transparent 0 24px,rgba(5,197,224,.09) 25px 33px,transparent 34px 38px)}
    .ignis-feature-icon{
      display:flex;align-items:center;justify-content:center;width:42px;height:42px;
      border:1px solid #2e7f96;border-radius:6px;background:#083d53;margin-bottom:14px}
    .ignis-feature-icon svg{width:25px;height:25px;stroke:#37e9f4;fill:none;stroke-width:1.8}
    .ignis-ui-card b{font-size:1.15rem!important;color:#f6fbff!important}
    .ignis-ui-card p{font-size:.94rem!important;max-width:320px;color:#d2e4ed!important}
    .ignis-side-brand{gap:14px!important;border-bottom:0!important}
    .ignis-side-logo{width:64px!important;height:64px!important;flex-basis:64px!important}
    .ignis-side-logo img{width:56px!important;height:56px!important}
    .ignis-side-brand-copy strong{font-size:1.35rem!important}
    .ignis-side-brand-copy small{font-size:.68rem!important;color:#a9d0df!important}
    .ignis-side-project{border-color:#25738d!important;background:#093047!important;color:#c2f3ff!important;padding:11px 12px!important;font-size:.71rem!important}
    .ignis-side-section-title{font-size:.72rem!important;color:#a8d6e4!important}
    section[data-testid="stSidebar"] div[role="radiogroup"] label{
      min-height:38px!important;padding:8px 8px 8px 44px!important;border-radius:3px!important}
    section[data-testid="stSidebar"] div[role="radiogroup"] label::after{
      content:"";position:absolute;left:13px;top:50%;transform:translateY(-50%);
      width:19px;height:19px;background:#9fcadf;pointer-events:none;
      -webkit-mask-repeat:no-repeat;-webkit-mask-size:contain;-webkit-mask-position:center;
      mask-repeat:no-repeat;mask-size:contain;mask-position:center}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::after{background:#38e7f1}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:linear-gradient(90deg,#0d4a61b5,#0b28404d)!important;border-color:#287e91!important}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before{top:0!important;bottom:0!important;width:4px!important;border-radius:0!important}
    section[data-testid="stSidebar"] div[role="radiogroup"] label [data-testid="stMarkdownContainer"] p{font-size:.86rem!important;color:#e0f0f5!important}
    section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child:has(input[type=radio]),
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child{
      width:1px!important;height:1px!important;position:absolute!important;
      clip-path:inset(50%)!important;overflow:hidden!important;opacity:0!important;
      pointer-events:none!important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:focus-within{
      outline:2px solid #33ddec!important;outline-offset:2px!important;
    }
    /* Reemplaza los controles radio por navegación real con 15 botones:
       iconos específicos y sin círculos de selección. */
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button{
      position:relative!important;display:flex!important;align-items:center!important;
      justify-content:flex-start!important;gap:9px!important;
      background:transparent!important;border:1px solid transparent!important;
      border-radius:3px!important;box-shadow:none!important;
      color:#d6e9f2!important;font-weight:500!important;font-size:.84rem!important;
      min-height:37px!important;width:100%!important;
      padding:7px 10px 7px 48px!important;text-align:left!important;
      transition:background-color .14s ease,border-color .14s ease!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button p{
      text-align:left!important;line-height:1.25!important;
      white-space:normal!important;color:inherit!important;
      font-weight:inherit!important;font-size:.84rem!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button::before{
      content:""!important;display:block!important;position:absolute!important;
      left:14px;top:50%;transform:translateY(-50%);
      width:21px;height:21px;background:#bcd9e9!important;
      -webkit-mask-position:center;-webkit-mask-repeat:no-repeat;-webkit-mask-size:contain;
      mask-position:center;mask-repeat:no-repeat;mask-size:contain;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button::after{
      display:none!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button[kind="primary"],
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button[data-testid="stBaseButton-primary"]{
      background:linear-gradient(90deg,rgba(3,137,165,.51),rgba(8,53,80,.48))!important;
      border:1px solid #21cce4!important;
      box-shadow:inset 3px 0 #20f0f1,0 0 15px rgba(16,205,225,.10)!important;
      color:#ffffff!important;font-weight:740!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button[kind="primary"]::before{
      background:#51f6fb!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button:hover{
      background:rgba(20,91,119,.28)!important;border-color:rgba(48,190,213,.43)!important;
    }
    section[data-testid="stSidebar"] div[class*="st-key-ignis_nav_"] button:focus-visible{
      outline:2px solid #36e9f6!important;outline-offset:2px!important;
    }
    .ignis-ui-hero h1{
      -webkit-text-fill-color:#f8fbff!important;background:none!important;
    }
    .ignis-ui-hero h1 span{
      -webkit-text-fill-color:transparent!important;
    }
    .ignis-ui-hero{
      min-height:423px!important;background-position:center center!important;
    }
    /* Los fondos de portada se cargan localmente en render_project_home. */
    /* Chip/icono de sección: HUD discreto, no más tarjetas infladas. */
    .ignis-ui-card{min-height:205px!important}
    .ignis-ui-topbar{background:rgba(2,13,25,.98)!important}
    @media(max-width:900px){.ignis-ui-hero{min-height:385px!important;padding:27px!important}.ignis-ui-hero h1{font-size:clamp(2.7rem,8vw,4rem)!important}}
    @media(max-width:600px){.ignis-ui-hero{min-height:410px!important}.ignis-ui-hero::after{background:linear-gradient(90deg,#001023d9,#00102388)}.ignis-ui-hero-facts{gap:5px!important}.ignis-ui-hero-facts span{font-size:.69rem!important;padding:7px!important}.ignis-ui-card{min-height:164px!important}}
    </style>"""
    strokes = [
      '<path d="m3 10 9-7 9 7v10h-6v-6H9v6H3z"/>',
      '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
      '<path d="M5 18H4a3 3 0 0 1-.5-5.96A7 7 0 0 1 17 8a5 5 0 0 1 3 9h-2M12 13v8m0-8-4 4m4-4 4 4"/>',
      '<path d="M4 19V10m5 9V4m5 15v-8m5 8V7"/>',
      '<path d="m3 17 6-7 4 4 7-9M15 5h5v5"/>',
      '<path d="M8 8a4 4 0 0 1 7-2l2 2m0-3v3h-3M16 16a4 4 0 0 1-7 2l-2-2m0 3v-3h3"/>',
      '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15"/>',
      '<path d="M12 3 2 21h20L12 3zM12 9v5m0 4h.01"/>',
      '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
      '<path d="M6 2h9l5 5v15H6zM15 2v6h5M9 12h8M9 16h8"/>',
      '<path d="M2 12h4l3-7 4 14 3-7h6"/>',
      '<rect x="8" y="7" width="8" height="10" rx="2"/><path d="m8 9-5-5-2 2 5 5m10-2 5-5 2 2-5 5m-9 5-6 4m13-4 6 4M12 3v4m0 10v4"/>',
      '<path d="M4 5h16v13H9l-5 4V5zM8 10h8m-8 4h5"/>',
      '<path d="m3 9 9-6 9 6-9 6zM3 15l9 6 9-6M3 12l9 6 9-6"/>',
      '<path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 20v-2a4 4 0 0 0-3-3.9M16 2.1a4 4 0 0 1 0 7.8"/>',
    ]
    icons = []
    for i, shape in enumerate(strokes, 1):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               'stroke="black" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
               + shape + '</svg>')
        url = quote(svg, safe="")
        # Estilo por clave estable: no depende del DOM interno de Streamlit.
        selector = (f'section[data-testid="stSidebar"] '
                    f'div.st-key-ignis_nav_{i - 1:02d} button::before')
        icons.append(f'<style>{selector}{{-webkit-mask-image:url("data:image/svg+xml,{url}");'
                     f'mask-image:url("data:image/svg+xml,{url}");}}</style>')
    for key, shape in (
        ("hero_to_history",strokes[1]),
        ("hero_to_dashboard",'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>'),
        ("hero_to_upload",strokes[2]),
    ):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               'stroke="black" stroke-width="1.8">' + shape + '</svg>')
        url = quote(svg, safe="")
        icons.append('<style>div.st-key-' + key + ' button::before'
                     + '{-webkit-mask-image:url("data:image/svg+xml,' + url +
                     '");mask-image:url("data:image/svg+xml,' + url + '");}</style>')
    return css + "".join(icons)


def _feature_icon(kind):
    shapes = {
        "sat": '<rect x="5" y="8" width="14" height="8" rx="1"/><path d="m1 3 5 5m-5 6 5 5m12-11 5-5m-5 11 5 5"/>',
        "map": '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15"/>',
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
        "location": '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="2.5"/>',
    }
    return ('<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            'stroke-linejoin="round">' + shapes[kind] + '</svg>')


def _header(kicker, title, subtitle):
    st.markdown(
        '<div class="ignis-ui-header">'
        f'<div class="ignis-ui-kicker">{escape(kicker)}</div>'
        f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>'
        '<div class="ignis-ui-bar"></div>',
        unsafe_allow_html=True,
    )


def _empty_uruguay_outline(base, key):
    file = Path(base) / "uruguay_contorno.geojson"
    if not file.exists():
        st.info("El contorno de Uruguay no está disponible en este despliegue.")
        return
    geometry = json.loads(file.read_text(encoding="utf-8"))["features"][0]["geometry"]
    coords = geometry["coordinates"] if geometry["type"] == "Polygon" else geometry["coordinates"][0]
    ring = coords[0]
    fig = go.Figure(go.Scatter(
        x=[p[0] for p in ring],y=[p[1] for p in ring],
        mode="lines",fill="toself",fillcolor="rgba(15,138,169,.20)",
        line=dict(color="#49cfe4",width=3),hoverinfo="skip",
    ))
    fig.update_layout(height=510,showlegend=False,
        margin=dict(l=12,r=12,t=12,b=12),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#0b1c30",
        xaxis=dict(visible=False,scaleanchor="y"),
        yaxis=dict(visible=False))
    st.plotly_chart(fig,use_container_width=True,key=key)


def _apply_local_home_backgrounds(base, asset_uri):
    """Cargar los cuatro fondos locales de IGNIS de una sola vez.

    WebP optimizados, sin red/CDN. Si falta alguno, el componente conserva
    su diseño y fondo anteriores. Las imágenes son artísticas, no evidencia FIRMS.
    """
    assets = {
        "hero": "bg_portada.webp",
        "observaciones": "bg_observaciones.webp",
        "atlas": "bg_atlas.webp",
        "trazabilidad": "bg_trazabilidad.webp",
    }
    uris = {}
    for key, filename in assets.items():
        image_path = Path(base) / "assets" / filename
        if image_path.is_file():
            uris[key] = asset_uri(image_path, "image/webp")

    rules = []
    if "hero" in uris:
        rules.append(
            ".ignis-ui-hero {"
            "background-image:linear-gradient(90deg,"
            "rgba(1,9,22,.88) 0%,rgba(1,11,25,.71) 36%,"
            "rgba(1,12,27,.26) 70%,rgba(1,12,27,.12) 100%),"
            f"url('{uris['hero']}')!important;"
            "background-position:center 15%!important;"
            "background-repeat:no-repeat!important;"
            "background-size:cover!important;"
            "}"
        )

    card_rules = {
        "observaciones": (
            ".ignis-ui-card.ignis-ui-card--heat", "center 51%"
        ),
        "atlas": (
            ".ignis-ui-card.ignis-ui-card--atlas", "center 54%"
        ),
        "trazabilidad": (
            ".ignis-ui-card.ignis-ui-card--trace", "center 51%"
        ),
    }
    for key, (selector, position) in card_rules.items():
        if key not in uris:
            continue
        rules.append(
            f"{selector} {{"
            "background-image:linear-gradient(100deg,"
            "rgba(2,13,28,.94) 0%,rgba(2,14,28,.78) 43%,"
            "rgba(2,14,28,.38) 74%,rgba(2,14,28,.23) 100%),"
            f"url('{uris[key]}')!important;"
            f"background-position:{position}!important;"
            "background-size:cover!important;"
            "background-repeat:no-repeat!important;"
            "}"
            f"{selector}::after {{display:none!important;}}"
        )

    if rules:
        # La regla se limita al Inicio y tiene prioridad sobre la decoración
        # CSS anterior de las tarjetas, sin alterar filtros ni otras páginas.
        st.markdown(
            "<style>" + "\n".join(rules) + """
            @media(max-width:650px){
              .ignis-ui-hero{
                background-position:64% 18%!important;
                min-height:425px!important;
              }
              .ignis-ui-card{
                min-height:195px!important;
              }
            }
            </style>""",
            unsafe_allow_html=True,
        )
    return uris


def render_project_home(base, asset_uri, pages, navigate):
    """Portada institucional A: maqueta aprobada con SVG de alta resolución."""
    logo = Path(base) / "logo_ignis.png"
    logo_markup = (f'<img src="{asset_uri(logo)}" alt="Logo IGNIS UY">'
                   if logo.exists() else "◈")
    st.markdown(
        '<div class="ignis-ui-topbar"><div class="ignis-ui-wordmark">'
        f'{logo_markup}<div>IGNIS UY<small>Histórico · Uruguay</small></div></div>'
        '<div class="ignis-ui-links">'
        '<a href="https://ema.fau.mil.uy/" target="_blank" rel="noopener noreferrer">EMA ↗</a>'
        '<a href="https://www.spaceappschallenge.org/2026/" target="_blank" '
        'rel="noopener noreferrer">NASA Space Apps ↗</a></div></div>',
        unsafe_allow_html=True,
    )
    # Antes de renderizar la portada, aplicar los cuatro fondos WebP locales.
    _apply_local_home_backgrounds(base, asset_uri)
    hero_art = Path(base) / "assets" / "ignis_hero_premium.svg"
    fallback = Path(base) / "hero_espacio.jpg"
    if hero_art.exists():
        url = asset_uri(hero_art, "image/svg+xml")
    elif fallback.exists():
        url = asset_uri(fallback, "image/jpeg")
    else:
        url = ""
    background = (
        "background-image:linear-gradient(90deg,rgba(0,9,23,.62),"
        "rgba(0,8,22,.07) 72%),"
        f"url('{url}');"
    ) if url else ""
    st.markdown(
        f'<div class="ignis-ui-hero" style="{background}">'
        '<div class="ignis-ui-kicker">'
        'Análisis satelital de actividad térmica en Uruguay</div>'
        '<h1>IGNIS UY<br><span>Histórico</span></h1>'
        '<p>Explorá observaciones NASA FIRMS de los sensores MODIS y VIIRS, '
        'compará períodos históricos y consultá evidencia documental para '
        'interpretar la actividad térmica del territorio uruguayo.</p>'
        '<div class="ignis-ui-hero-facts">'
        '<span>' + _feature_icon("sat") + 'MODIS + VIIRS</span>'
        '<span>' + _feature_icon("calendar") + 'Estudio histórico 2000–2026</span>'
        '<span>' + _feature_icon("location") + 'Enfoque geoespacial</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1.08, 1, 1], gap="medium")
    with left:
        st.button("Explorar histórico", type="primary", use_container_width=True,
                  key="hero_to_history", on_click=navigate, args=(pages[4],))
    with center:
        st.button("Centro de control", use_container_width=True,
                  key="hero_to_dashboard", on_click=navigate, args=(pages[1],))
    with right:
        st.button("Cargar datos", use_container_width=True,
                  key="hero_to_upload", on_click=navigate, args=(pages[2],))
    st.markdown(
        '<h2 class="ignis-home-section-title">Qué podés hacer en IGNIS</h2>',
        unsafe_allow_html=True,
    )
    cards = [
        ("sat", "ignis-ui-card--heat", "Observaciones satelitales",
         "Explorá los registros originales y las diferencias entre los "
         "instrumentos MODIS y VIIRS."),
        ("map", "ignis-ui-card--atlas", "Atlas científico",
         "Localizá actividad térmica por región, fecha y sensor en los "
         "mapas del estudio."),
        ("shield", "ignis-ui-card--trace", "Trazabilidad",
         "Contrastá episodios con informes y fuentes externas, sin asumir "
         "que una detección confirma un incendio."),
    ]
    for col, (icon, variant, title, description) in zip(
        st.columns(3, gap="medium"), cards
    ):
        with col:
            st.markdown(
                f'<div class="ignis-ui-card {variant}">'
                f'<div class="ignis-feature-icon">{_feature_icon(icon)}</div>'
                f'<b>{escape(title)}</b><p>{escape(description)}</p></div>',
                unsafe_allow_html=True,
            )
    st.caption(
        "Investigación independiente en el contexto de NASA Space Apps "
        "Challenge 2026. La escena espacial es ilustrativa. Los fondos "
        "son ilustraciones digitales, no fotografías satelitales fechadas "
        "ni validaciones de incendios. Las anomalías térmicas no equivalen "
        "a incendios confirmados; la armonización sigue siendo experimental "
        "y la cobertura depende de los archivos suministrados."
    )


def render_control_center(combined,sample,selected,base,map_fn,pages,navigate):
    _header("Panel general · Uruguay","Centro de control",
            "Monitoreo exploratorio y análisis histórico de observaciones NASA FIRMS.")
    if isinstance(combined,pd.DataFrame) and not combined.empty and not sample.empty:
        view=sample[sample.anio==selected] if selected is not None else sample
    else:
        view=pd.DataFrame()
    cards=[
        ("Detecciones visibles",f"{len(view):,}" if not view.empty else "Sin datos"),
        ("Años con registros",str(sample.anio.nunique()) if not sample.empty else "—"),
        ("Sensores presentes",str(view.instrumento.nunique()) if not view.empty else "—"),
        ("Año seleccionado",str(selected) if selected is not None else "—"),
    ]
    for column,(title,value) in zip(st.columns(4,gap="small"),cards):
        column.metric(title,value)
    st.write("")
    left,right=st.columns([1.9,1],gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("#### 🗺️ Actividad térmica · Uruguay")
            if not view.empty:
                map_fn(view,"ignis_control_map")
            else:
                st.caption("Importá registros para visualizar las detecciones.")
                _empty_uruguay_outline(base,"ignis_control_empty")
    with right:
        with st.container(border=True):
            st.markdown("#### 📡 Instrumentos")
            if view.empty:
                st.info("No hay observaciones en esta selección.")
                st.button("📂 Importar datos",type="primary",
                          use_container_width=True,key="control_upload",
                          on_click=navigate,args=(pages[2],))
            else:
                counts=view.groupby("instrumento").size().sort_values()
                fig=go.Figure(go.Bar(
                    x=counts.values,y=counts.index.astype(str),orientation="h",
                    marker_color="#44d1e4"))
                fig.update_layout(height=245,margin=dict(l=12,r=12,t=15,b=28),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#dceffa"),xaxis_title="Registros")
                st.plotly_chart(fig,use_container_width=True,key="ignis_control_sensors")
                st.caption("Cantidad de detecciones por instrumento; no son incendios únicos.")
        with st.container(border=True):
            st.markdown("#### 🛡️ Validación externa")
            st.caption("Evidencias históricas y referencias originales para revisar posibles episodios.")
            st.button("Consultar fuentes",use_container_width=True,key="control_evidence",
                      on_click=navigate,args=(pages[7],))
        with st.container(border=True):
            st.markdown("#### 📚 Otras herramientas")
            st.button("Atlas científico",use_container_width=True,key="control_atlas",
                      on_click=navigate,args=(pages[6],))
            st.button("Armonización MODIS–VIIRS",use_container_width=True,
                      key="control_harmonization",on_click=navigate,args=(pages[5],))
    if not view.empty:
        st.markdown("#### 📈 Evolución mensual del año seleccionado")
        months=view.groupby("mes").size().sort_index()
        fig=go.Figure(go.Bar(
            x=months.index.tolist(),y=months.values.tolist(),
            marker=dict(color="#f28c52"),name="Detecciones"))
        fig.update_layout(height=290,margin=dict(l=15,r=15,t=12,b=35),
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e4f3ff"),xaxis=dict(title="Mes",dtick=1,range=[.5,12.5]),
            yaxis_title="Registros")
        st.plotly_chart(fig,use_container_width=True,key="ignis_control_months")
    st.caption("La ausencia de registros no significa ausencia de incendios ni confirma "
               "cobertura satelital completa. Esta plataforma no emite alertas oficiales.")


def render_scientific_atlas(sample,selected,base,map_fn,columns,pages,navigate):
    _header("Atlas científico · Exploración espacial",
            "Atlas de actividad térmica",
            "Elegí una escala temporal y explorá las observaciones térmicas cargadas para Uruguay.")
    if sample.empty:
        st.info("Importá archivos ZIP/CSV o el Maestro IGNIS antes de explorar el atlas.")
        left,right=st.columns([2,1],gap="medium")
        with left:
            _empty_uruguay_outline(base,"ignis_atlas_empty")
        with right:
            st.markdown("#### Empezá por cargar datos")
            st.button("📂 Ir a Carga de datos",type="primary",
                      use_container_width=True,key="atlas_upload",
                      on_click=navigate,args=(pages[2],))
        return
    selector=st.radio("Período del mapa",
                      ["Todo el histórico cargado","Año seleccionado"],
                      horizontal=True,key="ignis_atlas_period")
    mapped=sample if selector=="Todo el histórico cargado" else sample[sample.anio==selected]
    a,b,c=st.columns(3)
    a.metric("Detecciones en el recorte",f"{len(mapped):,}")
    b.metric("Años con registros",str(mapped.anio.nunique()))
    c.metric("Sensores presentes",str(mapped.instrumento.nunique()))
    st.write("")
    map_col,tools_col=st.columns([2.15,1],gap="medium")
    with map_col:
        with st.container(border=True):
            st.markdown("#### 🗺️ Distribución geográfica")
            if not mapped.empty:
                map_fn(mapped,"ignis_atlas_scientific")
            else:
                st.info("No hay puntos para el período seleccionado.")
                _empty_uruguay_outline(base,"ignis_atlas_selection_empty")
    with tools_col:
        with st.container(border=True):
            st.markdown("#### 🧰 Herramientas")
            st.button("🔄 Comparar MODIS–VIIRS",use_container_width=True,
                      key="atlas_harmonization",on_click=navigate,args=(pages[5],))
            st.button("🛡️ Fuentes externas",use_container_width=True,
                      key="atlas_sources",on_click=navigate,args=(pages[7],))
            if not mapped.empty:
                available=[c for c in columns if c in mapped.columns]
                csv=mapped[available].to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Descargar recorte CSV",csv,
                    file_name="IGNIS_atlas_registros.csv",mime="text/csv",
                    use_container_width=True,key="atlas_download")
        with st.container(border=True):
            st.markdown("#### 📊 Actividad por sensor")
            if not mapped.empty:
                counts=mapped.groupby("instrumento").size()
                fig=go.Figure(go.Pie(labels=counts.index.astype(str),
                                    values=counts.values,hole=.65,
                                    marker=dict(colors=["#3aa5e7","#f39c5c","#40d1c5","#ad91ff"])))
                fig.update_layout(height=245,margin=dict(l=8,r=8,t=4,b=4),
                    paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#ebf6ff"),
                    showlegend=True,legend=dict(orientation="h",y=-.12))
                st.plotly_chart(fig,use_container_width=True,key="atlas_instrument_pie")
            else:
                st.caption("No hay datos para comparar.")
        with st.container(border=True):
            st.markdown("#### 📈 Actividad por mes")
            if not mapped.empty:
                monthly=mapped.groupby("mes").size().sort_index()
                fig=go.Figure(go.Scatter(
                    x=monthly.index.tolist(),y=monthly.values.tolist(),
                    mode="lines+markers",line=dict(color="#4bd5eb",width=3),
                    marker=dict(size=7,color="#fd9356")))
                fig.update_layout(height=220,margin=dict(l=8,r=8,t=12,b=25),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#dceeff"),xaxis=dict(dtick=1,title="Mes"))
                st.plotly_chart(fig,use_container_width=True,key="atlas_month_line")
    st.caption("Mapa estadístico basado en los registros FIRMS importados; "
               "no utiliza imágenes satelitales como fondo. La densidad es ilustrativa "
               "y no corresponde a hectáreas quemadas. Los meses sin registros "
               "no demuestran ausencia de actividad.")
