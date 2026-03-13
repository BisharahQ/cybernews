#!/usr/bin/env python3
"""
IRANIAN HACKTIVIST TELEGRAM MONITOR
====================================
Wartime cyber intelligence collection tool for Jordanian Cyber Crimes Unit
Monitors Iranian-aligned hacktivist Telegram channels for:
  - Attack claims against Jordanian infrastructure
  - IOC extraction (IPs, domains, URLs)
  - Target coordination and vulnerability sharing
  - Operational timing analysis

SETUP:
1. Get Telegram API credentials from https://my.telegram.org/apps
2. pip install telethon aiohttp python-dateutil
3. Set environment variables or edit config below
4. python3 telegram_monitor.py

SECURITY NOTE: Run this from a dedicated VM with a burner Telegram account.
Do NOT use personal or official accounts.
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, InputChannel, PeerChannel
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
except ImportError:
    print("ERROR: Install telethon first: pip install telethon")
    exit(1)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Telegram API credentials - get from https://my.telegram.org/apps
API_ID = os.environ.get("TG_API_ID", "35545979")
API_HASH = os.environ.get("TG_API_HASH", "41240e3f451065a430692d2e1bc82453")
PHONE = os.environ.get("TG_PHONE", "+962791896483")

# Output directory for collected intelligence
OUTPUT_DIR = Path("./telegram_intel")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── SQLite Database Layer ────────────────────────────────────────────────────
import sys as _sys2
_sys2.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from app.database import init_db
    from app.config import DB_PATH
    from app import models as _db
    init_db(DB_PATH)
    _SQLITE_OK = True
except Exception as _e:
    logging.warning(f"SQLite init failed, falling back to JSONL: {_e}")
    _SQLITE_OK = False

# Log configuration
LOG_FILE = OUTPUT_DIR / "monitor.log"
import sys as _sys
try:
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(_sys.stdout),
    ]
)
log = logging.getLogger("TGMonitor")

# Iran Standard Time offset (UTC+3:30) - unique to Iran
IRST_OFFSET = timedelta(hours=3, minutes=30)

# ==============================================================================
# CHANNEL WATCHLIST - PRIORITY TARGETS
# ==============================================================================
# These are the known channels/groups identified through OSINT research.
# Channels get banned/recreated frequently. Update this list continuously.
# Format: "channel_username_or_id" or "t.me/channel_name" link
#
# TIER 1: Groups that have directly targeted Jordan
# TIER 2: Coordinating groups from the Iran hacktivist ecosystem
# TIER 3: Broader resistance-axis cyber groups
# ==============================================================================

WATCHLIST = {
    # =========== TIER 1: DIRECTLY TARGETING JORDAN ===========
    "TIER1_JORDAN_TARGETING": [
        # Fatemiyoun Cyber Team - confirmed JMI defacement
        "hak993",                   # Fatemiyoun main channel
        "hak994",                   # Fatemiyoun secondary channel
        "Fatimion310_bot",          # Fatemiyoun bot
        "fatimion110",              # Fatemiyoun community (4★ discovery 2026-03-03)
        "hkr313",                   # Fatemiyoun field team (discovered 2026-03-03)
        # FaD TeaM - confirmed Ministry of Finance breach
        # Handle rotates frequently - search Telegram for "FaD TeaM" regularly
        # 313 Team - confirmed DDoS on jordan.gov.jo
        "x313xTeam",               # 313 Team main channel (Iraqi Cyber Resistance)
        "xX313XxTeam",             # 313 Team alternate handle
        "Team313Official",         # 313 Team official backup
        "x313xTeamLeak",           # 313 Team leak channel
        "x313xTeamBackup",         # 313 Team backup
    ],

    # =========== TIER 2: IRAN-ALIGNED HACKTIVIST ECOSYSTEM ===========
    "TIER2_IRANIAN_HACKTIVISTS": [
        # Cyber Islamic Resistance - IRGC umbrella, "Electronic Operations Room"
        "Mhwear98",                # Cyber Islamic Resistance main (banned)
        "Mhwercyber4",             # Cyber Islamic Resistance secondary (banned)
        "mhwear0",                 # Cyber Islamic Resistance new handle (active 2026-03-03)
        # Cyber Fattah Team - Iranian cyber team, Saudi Games breach, anti-Gulf
        "fattahh_ir",              # Cyber Fattah main channel
        # Handala Hack Team - MOIS-affiliated (Void Manticore), wiper deployment
        "Handala_hack",            # Handala main (frequently banned/recreated)
        "handala_hack26",          # Handala backup
        "handal_a",                # Handala current active (confirmed 2025)
        "Handala_hack_iranian",    # Handala Iranian variant (discovered 2026-03-03)
        "Handala_Hack_Team",       # Handala team channel (discovered 2026-03-03)
        # Mr Hamza - most active group during June 2025 war
        "blackopmrhamza",          # Mr Hamza main channel
        # RipperSec - Malaysian pro-Palestinian, DDoS (MegaMedusa tool)
        "RipperSec",               # RipperSec news channel
        "TheRipperSec",            # RipperSec main channel
        # AnonGhost - reconnaissance/scanning, published US IP range scans
        "AnonGhostOfficialTeam",   # AnonGhost official
        # SYLHET GANG-SG - DDoS, amplifies DieNet attacks
        "sylhetgangsgofficial",    # Sylhet Gang official
        # Keymous+ - North Africa cyber team, mobilization calls
        "KeymousTeam",             # Keymous+ main
        "KMPteam",                 # Keymous+ alternate
        "Keymous_V2",              # Keymous+ backup
        # Islamic Hacker Army - new group discovered 2026-03-03
        "islamic_hacker_army1",    # Islamic Hacker Army main
    ],

    # =========== TIER 3: BROADER ECOSYSTEM ===========
    "TIER3_WIDER_ECOSYSTEM": [
        # NoName057(16) - Russian DDoS group allied with Iranian actors
        "noname05716eng",          # NoName057(16) English channel
        "noname05716",             # NoName057(16) Russian main
        "NoName05716",             # NoName057(16) alternate cap
        # DieNet - DDoS-as-a-service, most referenced channel June 2025
        "dienet3",                 # DieNet current active channel (confirmed)
        "DieNet_Network_V5",       # DieNet primary channel (current iteration)
        "DieNetAPI",               # DieNet API/Info channel (no underscore variant)
        "DieNet_API",              # DieNet API Information channel (underscore variant)
        "dienet_media",            # DieNet Media Corporation
        "DIeNlt",                  # DieNet direct attack claims channel
        "dienet1",                 # DieNet iteration 1 / attack claims
        "dnsupportbot",            # DieNet support/notification bot
        # LulzSec Black - Palestinian Islamic Jihad-affiliated cyber wing
        "LulzSecBlack",            # LulzSecBlack official channel
        "LulzSecHackers",          # LulzSec Hackers variant (discovered 2026-03-03)
        # Islamic Resistance in Iraq - forward channel for 313 Team content
        "ElamAlmoqawama",          # المقاومة الاسلامية في العراق (discovered 2026-03-03)
        # Al Toufan / Cyber Toufan - resistance axis aggregator
        "toufan_alaksa",           # طوفان الأقصى محور المقاومة (discovered 2026-03-03)
        # Islamic Hacker Army chat/community
        "Chat_Islamic_Hacker_Army", # Islamic Hacker Army discussion (discovered 2026-03-03)
        # Khamenei Arabic - Supreme Leader propaganda, used for cyber mobilization
        "Khamenei_arabi",          # Khamenei Arabic channel (discovered 2026-03-03)
        # DieNet attack notification bot
        "dnnmabot",                # DieNet Network APIs bot (discovered 2026-03-03 scan)
        # LulzSec Muslim variant - active in pro-Palestine operations
        "Luls_sec_muslims",        # LulzSec Muslims (discovered 2026-03-03 scan)
        # Operation Sword of Justice - hacktivist operation targeting Arab normalization
        "operationswordofjustice", # Op Sword of Justice (discovered 2026-03-03 scan)
        # Anonymous Islamic - global anonymous hacktivist Islamic branch
        "Anonymous0islamic",       # Anonymous Islamic (discovered 2026-03-03 scan)
        # Handala active handle (backup post-ban)
        "handala24",               # Handala 2024+ active channel (discovered 2026-03-03 scan)
        # 313 Team affiliated channel
        "tttteam313",              # 313 Team Affiliated (discovered 2026-03-03 scan)
        # Sabren News - resistance-axis news & ops channel
        "SabrenNewss",             # Sabren News (added 2026-03-03)
        # ── VERIFIED CONFIRMED USERNAMES (2026-03-03 research) ──────────────────
        # Dark Storm Team - active DDoS/defacement, US/EU/ME infrastructure attacks
        "DarkStormTeams",          # Dark Storm Team (CONFIRMED @DarkStormTeams)
        "DarkStormBackup",         # Dark Storm Team backup
        "darkstormchat",           # Dark Storm Team community chat
        # Arabian Ghosts - pro-Palestine, Gulf-region hacktivist
        "arabian_ghosts",          # Arabian Ghosts (CONFIRMED @arabian_ghosts)
        # APT Iran - IRGC research/tracking channel, cyber readiness posts
        "aptiran",                 # APT Iran (CONFIRMED @aptiran)
        # Golden Falcon - pro-Palestine DDoS/defacement
        "Golden_falcon_team",      # Golden Falcon (CONFIRMED @Golden_falcon_team)
        # Stucx Team - active defacement, multiple verified handles
        "stucxteam",               # Stucx Team (CONFIRMED @stucxteam)
        "stucxnet",                # Stucx Net (CONFIRMED)
        "xxstucxteam",             # Stucx Team alt (CONFIRMED)
        # Hand of Justice - affiliated with Cyber Isnaad Front
        "the_hand_of_justice",     # Hand of Justice (CONFIRMED @the_hand_of_justice)
        # Cyber Isnaad Front - Iranian-aligned, Syrian hacktivist
        "CyberIsnaadFront",        # Cyber Isnaad Front (CONFIRMED @CyberIsnaadFront)
        # Cyb3rDrag0nz / CyberDrag0nzz - defacement coalition
        "TeamCyb3rDrag0nz",        # CyberDrag0nzz (CONFIRMED @TeamCyb3rDrag0nz)
        "cyb3r_drag0nz_team",      # CyberDrag0nzz team alt
        # Hacktivist of Garuda / Garuda Eye - Indonesian hacktivist group
        "HacktivistOfGaruda",      # Garuda Eye (CONFIRMED @HacktivistOfGaruda)
        "HacktivistOfGarudaOfficial", # Garuda Eye official backup
        # Nation of Saviours - active pro-Palestine hacktivist
        "nation_of_saviors_public", # Nation of Saviours (CONFIRMED @nation_of_saviors_public)
        # EvilNet 3.0 - data exfiltration, defacement
        "EvilNet3",                # EvilNet 3.0 (CONFIRMED @EvilNet3)
        # Gaza Children's Group - Gaza-based hacktivist
        "Gaza_Children_Hackers",   # Gaza Children (CONFIRMED @Gaza_Children_Hackers)
        "gaza_children_ha",        # Gaza Children backup
        # Indohaxsec - Indonesian hacktivist, pro-Palestine
        "INDOHAXSEC",              # Indohaxsec (CONFIRMED @INDOHAXSEC)
        # Altoufan Team - resistance cyber operations
        "ALTOUFANTEAM",            # Altoufan Team (CONFIRMED @ALTOUFANTEAM)
        # Team Azrael (Angel of Death) - resistance-axis cyber team
        "anonymous_cr02x",         # Team Azrael main (CONFIRMED @anonymous_cr02x)
        "teamAzraelbackup",        # Team Azrael backup
        # BD Anonymous / The Anonymous BD - Bangladesh
        "anonymous_bangladesh",    # BD Anonymous (CONFIRMED @anonymous_bangladesh)
        "t_gray_hacker",           # The Anonymous BD alt
        # Moroccan Black Cyber Army - North Africa coalition
        "M0roccan_Black_CyberArmy", # MBCA (CONFIRMED @M0roccan_Black_CyberArmy, note: zero not O)
        "moroccan_blackcyberarmy", # MBCA alternate
        # Akatsuki Cyber Team - pro-Palestine, pro-Iran operations
        "akatsukicyberteam",       # Akatsuki (CONFIRMED @akatsukicyberteam)
        # FAD Team - claimed Ministry of Finance breach
        "r3_6j",                   # FAD Team (CONFIRMED @r3_6j via telemetr.io)
        # Cyber Av3ngers / Cyber4vengers - IRGC-affiliated, ICS/OT attacks
        "CyberAv3ngers",           # Cyber Av3ngers (CONFIRMED @CyberAv3ngers)
        "cyberaveng3rs",           # Cyber Av3ngers alternate handle
        # Iran Anonymous / Anonymous OpIran - Anonymous branch
        "anonopiran",              # Iran Anonymous (CONFIRMED @anonopiran)
        # Liwaa Mohammad (Mohamed Brigade) - Lebanese resistance cyber
        "liwaamohammad",           # Liwaa Mohammad (CONFIRMED @liwaamohammad)
        # Tharallah Brigade - resistance-axis, uses mhwear* namespace
        "mhwear10",                # Tharallah Brigade (CONFIRMED @mhwear10)
        # Sylhet Gang SG - DDoS ops (primary handle in TIER2 above)
        "SylhetGangSG",            # Sylhet Gang SG alt
        # Cyber32 - hacktivist defacement
        "Cyber32",                 # Cyber32 main
    ],
}

# Private channels (by numeric ID) — these have no public username
# Format: {channel_id: {"label": ..., "tier": ...}}
PRIVATE_CHANNELS = {
    3575098403: {
        "label": "Handala Inner Channel (BELECTRIC/Etihad Source)",
        "tier": 1,
        "threat": "CRITICAL",
        "notes": "Private Handala coordination channel. Source of BELECTRIC/Bank al Etihad breach screenshots with Farsi text claiming persistent access.",
    },
}

# Flatten all channels for monitoring
ALL_CHANNELS = []
for tier_channels in WATCHLIST.values():
    ALL_CHANNELS.extend(tier_channels)

# Shared file for pending channels (discovery → monitor communication)
PENDING_FILE = OUTPUT_DIR / "pending_channels.json"

# Live discovery engine state file
DISCOVERY_FILE = OUTPUT_DIR / "discovered_channels.json"

# Heuristic patterns for detecting cyber/hacktivist channel names
HACKTIVIST_KEYWORDS = [
    "hack", "hacker", "cyber", "attack", "ddos", "anon", "anonymous",
    "team", "crew", "squad", "gang", "army", "force", "ghost", "shadow",
    "dark", "black", "storm", "fire", "kill", "breach", "pwn", "root",
    "shell", "exploit", "leak", "resistance", "مقاومة", "هاكر", "هكر",
    "اختراق", "قرصنة", "هجوم", "سيبر", "إلكتروني", "مجاهد", "تيم",
    "فريق", "جيش", "حرب", "نار", "ظل", "سري", "operation", "عملية",
    "palestine", "فلسطين", "iran", "ايران", "islamic", "اسلامي",
    "deface", "defaced", "botnet", "phish", "malware", "ransomware",
    "wiper", "c2", "rat", "trojan", "0day", "zeroday",
    "jihad", "mujahed", "resistance", "aqsa", "intifada",
    "apt", "ioc", "cve", "payload", "backdoor", "stealer",
]

# Known threat actor group name fragments — bonus scoring when found in channel names
KNOWN_GROUP_NAMES = [
    "rippersec", "cyberfattah", "fattah", "fatemiyoun", "fatimion",
    "handala", "killnet", "noname057", "darkstorm", "dragonforce",
    "ghostsec", "sylhet", "lulzsec", "dienet", "keymous", "stucx",
    "anonghost", "azrael", "garuda", "indohax", "altoufan", "313",
    "mrhamza", "cyberav3nger", "eaglecrew", "serverkillers",
    "mysterious_team", "mysteriousteam", "holyteam", "usersecc",
    "zpentest", "peoplescyber", "turkhack", "1915team",
    "moroccan", "arabian_ghost", "golden_falcon", "isnaad",
    "cyb3r_drag0n", "cyberdrag0n", "swordjustice",
    "gaza_children", "islamic_hacker", "nation_of_savior",
]

# ==============================================================================
# KEYWORD DETECTION - MULTI-LANGUAGE
# ==============================================================================

# HIGH PRIORITY - Immediate alert
KEYWORDS_CRITICAL = [

    # ══════════════════════════════════════════
    # JORDAN — GENERAL IDENTIFIERS
    # ══════════════════════════════════════════
    "الاردن", "الأردن", "اردن", "أردن",
    "jordan", "jordanian", "اردني", "أردني", "الأردنية", "الاردنية",
    "عمان", "amman",
    ".jo", ".gov.jo", ".edu.jo", ".mil.jo", ".net.jo", ".com.jo", ".org.jo",
    "مواقع اردنية", "jordanian sites", "jordanian infrastructure",
    "zarqa", "الزرقاء", "irbid", "اربد", "aqaba", "العقبة",
    "mafraq", "المفرق", "karak", "الكرك", "jerash", "جرش",

    # ══════════════════════════════════════════
    # JORDAN MILITARY / SECURITY
    # ══════════════════════════════════════════
    "الجيش الاردني", "القوات المسلحة الاردنية",
    "jordanian army", "jordanian military", "jordan armed forces",
    "muwaffaq salti", "الموفق السلطي", "king hussein air college",
    "مديرية الأمن العام", "public security directorate", "psd.gov.jo",
    "الدرك", "gendarmerie jordan", "jordan gendarmerie",
    "مكافحة الإرهاب", "counter terrorism jordan",
    "استخبارات اردن", "gid jordan", "general intelligence directorate",
    "border guard jordan", "حرس الحدود",

    # ══════════════════════════════════════════
    # JORDAN TELECOM / ISP
    # ══════════════════════════════════════════
    "zain jordan", "زين الأردن", "zain.jo",
    "orange jordan", "اورنج الأردن", "orange.jo",
    "umniah", "امنية", "umniah.com",
    "jordan telecom", "jordan.net.jo",
    "batelco jordan", "نبض", "viva jordan",
    "تنظيم الاتصالات", "trc.gov.jo",
    "tcs.jo", "tcs communications jordan",
    "jet jordan", "jet.jo", "jordan express telecom",
    "go telecom jordan", "go.jo",
    "cablenet.jo", "index.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — CENTRAL BANK
    # ══════════════════════════════════════════
    "central bank of jordan", "البنك المركزي الأردني", "البنك المركزي الاردني",
    "cbj.gov.jo", "مصرف مركزي الأردن",

    # ══════════════════════════════════════════
    # JORDAN BANKING — ARAB BANK (ABB)
    # ══════════════════════════════════════════
    "arab bank", "البنك العربي", "arabbank",
    "arab bank plc", "arabbank.com", "arabbank.jo",
    "بنك عربي", "البنك العربي المحدود",

    # ══════════════════════════════════════════
    # JORDAN BANKING — BANK OF JORDAN (BOJ)
    # ══════════════════════════════════════════
    "bank of jordan", "بنك الأردن", "بنك الاردن",
    "bankofJordan", "bankofjordan.com", "boj.jo",
    "bank-of-jordan",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN AHLI BANK (JAB)
    # ══════════════════════════════════════════
    "jordan ahli bank", "البنك الأهلي الأردني", "البنك الاهلي الاردني",
    "ahli bank", "البنك الأهلي",
    "jordanahlibank.com", "ahli.com", "jab.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — CAIRO AMMAN BANK (CAB)
    # ══════════════════════════════════════════
    "cairo amman bank", "بنك القاهرة عمان", "بنك القاهرة-عمان",
    "cairoammanbank", "cab.jo", "cairoammanbank.com",
    "كيرو عمان بنك",

    # ══════════════════════════════════════════
    # JORDAN BANKING — BANK AL ETIHAD (BAE)
    # ══════════════════════════════════════════
    "bank al etihad", "بنك الاتحاد", "بنك الإتحاد",
    "bankaletihad", "bankaletihad.com", "etihad bank jordan",
    "الاتحاد للاستثمار",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN KUWAIT BANK (JKB)
    # ══════════════════════════════════════════
    "jordan kuwait bank", "بنك الكويت الأردني", "بنك الكويت الاردني",
    "jkbonline.com", "jkbank.com", "jkb.jo",
    "jordan kuwait banking",

    # ══════════════════════════════════════════
    # JORDAN BANKING — HOUSING BANK (HBTF)
    # ══════════════════════════════════════════
    "housing bank", "بنك الإسكان", "بنك الاسكان",
    "housing bank for trade and finance", "hbtf",
    "hbtf.com", "housingbank.jo", "iskan bank",
    "بنك الإسكان للتجارة والتمويل",

    # ══════════════════════════════════════════
    # JORDAN BANKING — CAPITAL BANK (CBJ)
    # ══════════════════════════════════════════
    "capital bank", "كابيتال بنك", "capital bank of jordan",
    "capitalbank.jo", "capitalbank.com.jo",
    "بنك رأس المال",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN ISLAMIC BANK (JIB)
    # ══════════════════════════════════════════
    "jordan islamic bank", "البنك الإسلامي الأردني", "البنك الاسلامي الاردني",
    "jordanislamicbank.com", "jib.jo",
    "islamic bank jordan", "بنك إسلامي اردن",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN COMMERCIAL BANK (JCB)
    # ══════════════════════════════════════════
    "jordan commercial bank", "البنك التجاري الأردني", "البنك التجاري الاردني",
    "jcb", "jcbank.com.jo", "jordancommercialbank.com",
    "البنك التجاري",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN NATIONAL BANK (JNB / AL WATANI)
    # ══════════════════════════════════════════
    "jordan national bank", "البنك الوطني الأردني", "البنك الوطني الاردني",
    "al watani bank", "البنك الوطني",
    "jnb.com.jo", "jordannationalbank.com",

    # ══════════════════════════════════════════
    # JORDAN BANKING — ARAB JORDAN INVESTMENT BANK (AJIB)
    # ══════════════════════════════════════════
    "arab jordan investment bank", "البنك العربي الأردني للاستثمار",
    "ajib", "ajib.com.jo", "ajib.jo",
    "jordan investment bank", "بنك الاستثمار الأردني العربي",

    # ══════════════════════════════════════════
    # JORDAN BANKING — SOCIETE GENERALE (SGBJ)
    # ══════════════════════════════════════════
    "societe generale jordan", "سوسيتيه جنرال الأردن",
    "sgbj", "sgbj.com.jo", "societegenerale jordan",
    "بنك سوسيتيه جنرال الأردن",

    # ══════════════════════════════════════════
    # JORDAN BANKING — INVEST BANK
    # ══════════════════════════════════════════
    "invest bank", "بنك الاستثمار الأردني", "investbank",
    "investbank.jo", "invest-bank.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — ISLAMIC INTERNATIONAL ARAB BANK (IIAB)
    # ══════════════════════════════════════════
    "islamic international arab bank", "البنك العربي الإسلامي الدولي",
    "iiab", "iiab.com.jo",
    "بنك عربي اسلامي دولي",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JORDAN POST BANK / POSTAL SAVINGS
    # ══════════════════════════════════════════
    "jordan post bank", "بنك البريد الأردني",
    "postal savings jordan", "jordanpost.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — ABC BANK JORDAN
    # ══════════════════════════════════════════
    "abc bank jordan", "بنك أي بي سي الأردن",
    "arab banking corporation jordan",
    "abcjo.com",

    # ══════════════════════════════════════════
    # JORDAN BANKING — STANDARD CHARTERED JORDAN
    # ══════════════════════════════════════════
    "standard chartered jordan", "ستاندرد تشارترد الأردن",
    "standardchartered.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — CITIBANK JORDAN
    # ══════════════════════════════════════════
    "citibank jordan", "سيتي بنك الأردن",

    # ══════════════════════════════════════════
    # JORDAN BANKING — NATIONAL BANK OF KUWAIT JORDAN (NBK)
    # ══════════════════════════════════════════
    "national bank of kuwait jordan", "البنك الوطني الكويتي الأردن",
    "nbk jordan", "nbk.com.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — CREDIT AGRICOLE JORDAN
    # ══════════════════════════════════════════
    "credit agricole jordan", "كريدي أغريكول الأردن",
    "creditagricole.jo",

    # ══════════════════════════════════════════
    # JORDAN BANKING — JOPACC (PAYMENT INFRASTRUCTURE)
    # ══════════════════════════════════════════
    "jopacc", "jo-pacc", "jordan payments and clearing company",
    "شركة نظم المدفوعات الأردنية والتسوية",
    "jordan clearing", "efawateercom", "إيفواتيرکم",
    "cliq", "cliq.jo", "jordan payment gateway",
    "instant payment jordan", "real time payment jordan",

    # ══════════════════════════════════════════
    # JORDAN — FINANCIAL MARKET / EXCHANGE
    # ══════════════════════════════════════════
    "amman stock exchange", "بورصة عمان", "ase.com.jo",
    "jordan securities commission", "هيئة الأوراق المالية",
    "jsc.gov.jo", "jordan depository center",

    # ══════════════════════════════════════════
    # JORDAN — INSURANCE (key targets)
    # ══════════════════════════════════════════
    "jordan insurance", "التأمين الأردنية",
    "arab orient insurance", "التأمين العربي الشرقي",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — PRIME MINISTRY
    # ══════════════════════════════════════════
    "رئاسة الوزراء", "رئيس الوزراء", "مجلس الوزراء",
    "prime minister", "prime ministry", "cabinet jordan",
    "pm.gov.jo", "jordan government", "الحكومة الأردنية",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — ROYAL COURT
    # ══════════════════════════════════════════
    "الديوان الملكي", "royal court jordan", "rhc.jo",
    "royal hashemite court", "king abdullah", "الملك عبدالله",
    "crown prince", "ولي العهد",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — PARLIAMENT
    # ══════════════════════════════════════════
    "مجلس النواب", "مجلس الأعيان", "البرلمان الأردني",
    "jordanian parliament", "house of representatives jordan",
    "senate jordan", "parliament.jo",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF INTERIOR
    # ══════════════════════════════════════════
    "وزارة الداخلية", "وزير الداخلية",
    "ministry of interior jordan", "moi jordan", "moi.gov.jo",
    "دائرة الجوازات", "passport department jordan", "civil status",
    "الأحوال المدنية",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF FOREIGN AFFAIRS
    # ══════════════════════════════════════════
    "وزارة الخارجية", "وزير الخارجية",
    "ministry of foreign affairs jordan", "mfa jordan", "mfa.gov.jo",
    "اليونيفيل الأردن",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF DEFENSE
    # ══════════════════════════════════════════
    "وزارة الدفاع", "وزير الدفاع",
    "ministry of defense jordan", "mod jordan",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF FINANCE
    # ══════════════════════════════════════════
    "وزارة المالية", "وزير المالية",
    "ministry of finance jordan", "mof jordan", "mof.gov.jo",
    "ضريبة الدخل", "ضريبة المبيعات", "income tax", "sales tax",
    "دائرة ضريبة الدخل والمبيعات", "income and sales tax department",
    "istd.gov.jo", "jordan treasury",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF HEALTH
    # ══════════════════════════════════════════
    "وزارة الصحة", "وزير الصحة",
    "ministry of health jordan", "moh jordan", "moh.gov.jo",
    "jordan food and drug administration", "jfda", "jfda.jo",
    "royal medical services", "الخدمات الطبية الملكية",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF EDUCATION
    # ══════════════════════════════════════════
    "وزارة التربية والتعليم", "وزارة التربية", "وزير التربية",
    "ministry of education jordan", "moe jordan", "moe.gov.jo",
    "tawjihi", "توجيهي",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF DIGITAL ECONOMY
    # ══════════════════════════════════════════
    "وزارة الاقتصاد الرقمي", "وزارة الاتصالات وتكنولوجيا المعلومات",
    "ministry of digital economy", "moict jordan", "moict.gov.jo",
    "وزير الاتصالات",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF ENERGY
    # ══════════════════════════════════════════
    "وزارة الطاقة والثروة المعدنية", "وزارة الطاقة",
    "ministry of energy jordan", "memr jordan", "memr.gov.jo",
    "الكهرباء الأردنية",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — MINISTRY OF JUSTICE
    # ══════════════════════════════════════════
    "وزارة العدل", "ministry of justice jordan", "moj.gov.jo",
    "محاكم اردن", "jordan courts",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — OTHER MINISTRIES
    # ══════════════════════════════════════════
    "وزارة السياحة والآثار", "ministry of tourism jordan", "tourism.jo",
    "وزارة الزراعة", "ministry of agriculture jordan", "moa.gov.jo",
    "وزارة الأشغال العامة والإسكان", "ministry of public works",
    "وزارة الاقتصاد الوطني", "ministry of national economy", "mop.gov.jo",
    "وزارة الصناعة والتجارة", "ministry of industry and trade", "mit.gov.jo",
    "وزارة الشؤون الاجتماعية", "ministry of social development",
    "وزارة العمل", "ministry of labour jordan", "mol.gov.jo",
    "وزارة الأوقاف", "ministry of awqaf jordan", "awqaf.gov.jo",
    "وزارة الشباب", "ministry of youth jordan",
    "وزارة البيئة", "ministry of environment jordan",
    "وزارة الاتصالات", "وزارة التخطيط",

    # ══════════════════════════════════════════
    # JORDAN GOVERNMENT — KEY DEPARTMENTS / AGENCIES
    # ══════════════════════════════════════════
    "الجمارك الأردنية", "الجمارك الاردنية",
    "jordan customs", "customs.gov.jo",
    "دائرة الأراضي والمساحة",
    "department of lands and survey", "dls.gov.jo",
    "دائرة الإحصاءات العامة",
    "department of statistics jordan", "dos.gov.jo",
    "هيئة الاستثمار", "jordan investment commission", "jic.gov.jo",
    "محكمة التمييز", "court of cassation jordan",
    "ديوان المحاسبة", "audit bureau jordan",
    "هيئة مكافحة الفساد", "jacc jordan", "jacc.gov.jo",
    "سلطة منطقة العقبة", "aseza", "aqabazone.com",

    # ══════════════════════════════════════════
    # JORDAN — ENERGY / UTILITIES
    # ══════════════════════════════════════════
    "national electric power company", "nepco", "nepco.com.jo",
    "الشركة الأردنية لنقل الكهرباء",
    "irbid electricity", "كهرباء إربد",
    "jordan electric power company", "jepco",
    "edd.com.jo", "jepco.com.jo",
    "petra electric", "كهرباء البتراء",
    "water authority jordan", "سلطة المياه",
    "miyahuna", "مياهنا", "miyahuna.jo",
    "yarmouk water", "شركة اليرموك للمياه",
    "aqaba water", "مياه العقبة",
    "jordan petroleum refinery", "مصفاة البترول الأردنية", "jpr",
    "jordan oil shale", "تشيل اويل",
    "national gas company jordan", "نابكو",

    # ══════════════════════════════════════════
    # JORDAN — UNIVERSITIES / EDUCATION
    # ══════════════════════════════════════════
    "university of jordan", "الجامعة الأردنية", "ju.edu.jo",
    "jordan university of science", "just.edu.jo",
    "yarmouk university", "جامعة اليرموك", "yu.edu.jo",
    "mutah university", "جامعة مؤتة", "mutah.edu.jo",
    "hashemite university", "الجامعة الهاشمية", "hu.edu.jo",
    "german jordanian university", "gju.edu.jo",
    "philadelphia university jordan", "philadelphia.edu.jo",
    "applied science university", "asu.edu.jo",

    # ══════════════════════════════════════════
    # JORDAN — MEDIA / NATIONAL AGENCIES
    # ══════════════════════════════════════════
    "jordan news agency", "petra news", "petra.gov.jo",
    "وكالة الأنباء الأردنية", "وكالة بترا",
    "jordan tv", "التلفزيون الأردني", "jrtv.jo",
    "jordan radio", "إذاعة الأردن",
    "al ghad newspaper", "الغد", "alghad.com",
    "al arab al yawm", "العرب اليوم",

    # ══════════════════════════════════════════
    # ATTACK CLAIMS
    # ══════════════════════════════════════════
    "تم اختراق", "تم اختراق الموقع", "تم الاختراق",
    "hacked", "breached", "defaced", "pwned", "owned",
    "تسريب", "تسريب بيانات", "leak", "data leak", "data breach",
    "dump", "database dump", "db dump",
    "رانسوم", "ransomware", "فدية",
    "wiper", "مسح البيانات", "مسح", "تدمير", "destroy",
    "اختراق ناجح", "successful hack",
    "تم السيطرة", "full access", "root access",
]

# MEDIUM PRIORITY - Log and review
KEYWORDS_MEDIUM = [
    # Operational keywords
    "target list", "قائمة الاهداف", "اهداف",
    "vulnerability", "ثغرة", "ثغرات",
    "exploit", "استغلال",
    "CVE-", "0day", "zero-day",
    "ddos", "دي دي او اس",
    "botnet",
    "web shell", "شل",
    "reverse shell",
    "phishing", "تصيد",
    # Cyberweapon / tool references
    "mirai", "killnet", "godzilla shell",
    "cobalt strike", "metasploit",
    "sqlmap", "nikto", "nuclei",
    "anonymous sudan", "anonymous palestine",
    "غارات المقاومة", "cyber army",
    "operation #jordan", "أوبيريشن اردن",
    "tango down jordan", "هجوم اردن",
    # Leak / data infra commonly used
    "anonfiles", "pastebin jordan", "ghostbin",
    "mega.nz jordan", "telegram dump",
    # Regional targets (Gulf + allies)
    "bahrain", "البحرين",
    "qatar", "قطر",
    "kuwait", "الكويت",
    "saudi", "السعودية",
    "uae", "الامارات",
    # Military
    "قاعدة عسكرية", "military base",
    "centcom", "5th fleet",
    "al udeid", "ali al salem", "al dhafra",
    "muwaffaq salti air base", "h4 air base",
    "king hussein bin talal airport",
    # Specific Jordan-based US/NATO assets
    "usaid jordan", "us embassy amman", "السفارة الأمريكية عمان",
    "jtf-levant", "operation inherent resolve jordan",
    # Resistance axis
    "khamenei", "خامنئي", "الشهيد القائد",
    "soleimani", "سليماني",
    "انتقام", "revenge", "retaliation",
    "true promise", "الوعد الصادق",
    "operation", "عملية",
    # Sanctions / pressure keywords used by threat actors
    "boycott jordan", "مقاطعة الأردن",
    "arab normalization", "تطبيع أردن",
]

# ── Load keyword overrides from admin panel (keywords.json) ──────────────────
_KW_OVERRIDE = OUTPUT_DIR / "keywords.json"
if _KW_OVERRIDE.exists():
    try:
        _kw_data = json.loads(_KW_OVERRIDE.read_text(encoding="utf-8"))
        if _kw_data.get("critical"):
            KEYWORDS_CRITICAL = list(_kw_data["critical"])
        if _kw_data.get("medium"):
            KEYWORDS_MEDIUM = list(_kw_data["medium"])
        print(f"[KEYWORDS] Loaded from keywords.json: {len(KEYWORDS_CRITICAL)} critical, {len(KEYWORDS_MEDIUM)} medium")
    except Exception as _e:
        print(f"[KEYWORDS] Failed to load keywords.json: {_e} — using hardcoded defaults")
# ─────────────────────────────────────────────────────────────────────────────

# ── Backfill queue (admin panel writes here, monitor processes it) ────────────
BACKFILL_QUEUE_FILE = OUTPUT_DIR / "backfill_queue.json"
# ─────────────────────────────────────────────────────────────────────────────

# ── Critical Subtype Signal Sets ─────────────────────────────────────────────
# Used to classify CRITICAL messages as CYBER or NATIONAL SECURITY subtype.
# These are SUBSETS of KEYWORDS_CRITICAL checked against keyword_hits.

CYBER_CRITICAL_SIGNALS = {
    # Attack types
    "ddos", "d-dos", "defacement", "defaced", "data leak", "data breach", "databreach",
    "ransomware", "ransom", "malware", "trojan", "botnet", "exploit", "sql injection",
    "sqlmap", "webshell", "shell", "backdoor", "rootkit", "c2",
    "brute force", "credential", "hacked", "hacking", "hack", "pwned", "owned",
    "breach", "breached", "leak", "dump", "wiper", "destroy",
    "root access", "full access",
    # Arabic cyber terms
    "اختراق", "تسريب", "بيانات", "قرصنة", "هاكر", "فيروس", "هجوم",
    "دي دوس", "برامج خبيثة", "رانسوم", "فدية", "مسح",
    # Jordan domain targets (domain targeting = cyber)
    ".jo", ".gov.jo", ".com.jo", ".edu.jo", ".org.jo",
    # DDoS tools / indicators
    "check-host", "dienet", "connection timed out", "connection refused",
    "layer7", "layer4", "http flood",
    # Critical infrastructure (cyber attacks on infra = cyber)
    "bank", "بنك", "مصرف", "arab bank", "البنك العربي", "cairo amman",
    "القاهرة عمان", "housing bank", "بنك الاسكان", "jordan bank",
    "البنك الاردني", "financial", "مالي",
    "telecom", "اتصالات", "nepco", "jepco", "miyahuna", "مياهنا",
    "water authority", "electric power", "كهرباء",
}

NATIONAL_CRITICAL_SIGNALS = {
    # Iranian/IRGC
    "irgc", "iranian", "khamenei", "خامنئي", "حرس الثوري", "فاطميون",
    "soleimani", "سليماني", "quds force", "الحرس الثوري",
    # Resistance axis groups
    "حزب الله", "hezbollah", "حماس", "hamas", "قسام", "qassam",
    "جهاد اسلامي", "حوثي", "houthi", "انصار الله", "مقاومة",
    # Geopolitical / conflict zones (these disambiguate اختراق as military)
    "gaza", "غزة", "palestine", "فلسطين", "فلسطيني", "palestinian",
    "lebanon", "لبنان", "syria", "سوريا", "iraq", "العراق", "yemen", "اليمن",
    "west bank", "الضفة", "الأقصى", "al aqsa", "occupied", "محتل", "احتلال",
    "resistance", "المقاومة", "axis", "محور",
    # Jordan military / security services
    "عسكري", "military", "troops", "army", "القوات المسلحة",
    "الجيش الاردني", "jordan armed forces", "القوات الجوية", "air force",
    "us base", "nato", "ain al asad", "العديد", "المفرق",
    ".mil.jo",  # military domain = national security
    "استخبارات", "intelligence", "gendarmerie", "الدرك",
    "border guard", "حرس الحدود", "مكافحة الإرهاب", "counter terrorism",
    "الأمن العام", "security directorate", "muwaffaq", "الموفق",
    # War / conflict / military operations
    "حرب", "warfare", "warzone", "at war", "of war", "airstrike", "air strike",
    "missile", "صاروخ", "تصعيد", "escalation",
    "عملية عسكرية", "military operation",
    # Aerial / ground military terms (disambiguates اختراق جوي = aerial penetration)
    "جوي", "aerial", "airspace", "اجتياح", "incursion", "invasion", "غزو",
    "bombardment", "قصف", "shelling", "شهيد", "martyr", "شهداء",
    "casualties", "killed", "قتلى", "جرحى", "wounded",
}

# Service/sale advertisements — hacking services being sold, not actual attacks
SERVICE_AD_SIGNALS = {
    "service", "services", "for sale", "for hire", "hire", "buy", "sell", "selling",
    "pricing", "price", "order", "contact us", "dm for", "dm me",
    "blackhat", "black hat", "professional hacking", "hacking service", "blackhat service",
    "we hack", "hack for", "hacker for",
    "we offer", "we provide", "available now", "24/7",
    "guaranteed results", "confidential", "affordable", "discount",
    "package", "combo", "premium", "vip",
    "خدمات", "خدمة", "للبيع", "للإيجار", "اشتري", "نبيع",
    "اسعار", "سعر", "اطلب", "تواصل معنا", "راسلنا",
    "نقدم", "نوفر", "متاح الآن", "خدمات احترافية",
    "خدمات هک", "سرویس", "فروش", "قیمت", "سفارش",
    "تماس بگیرید", "ارائه می‌دهیم",
}

JORDAN_REFS = {
    "jordan", "jordanian", "amman",
    "الاردن", "الأردن", "أردن", "اردن", "اردني", "أردني", "الأردني", "الاردني",
    "عمان", "عمّان", "اردن", "اُردن",
    ".jo", ".gov.jo", ".com.jo", ".edu.jo", ".org.jo", ".mil.jo",
}

# ─────────────────────────────────────────────────────────────────────────────

# IOC PATTERNS - Extract indicators of compromise
IOC_PATTERNS = {
    "ipv4": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "domain": re.compile(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:jo|gov|mil|edu|com|net|org|ir|iq|lb|sy)\b'),
    "url": re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'),
    "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    "cve": re.compile(r'CVE-\d{4}-\d{4,7}'),
    "hash_md5": re.compile(r'\b[a-fA-F0-9]{32}\b'),
    "hash_sha256": re.compile(r'\b[a-fA-F0-9]{64}\b'),
}

# ==============================================================================
# CORE MONITORING ENGINE
# ==============================================================================

class TelegramMonitor:
    def __init__(self):
        self.client = TelegramClient("jordan_cyber_intel", int(API_ID), API_HASH)
        self.alert_log   = OUTPUT_DIR / "alerts.jsonl"
        self.ioc_log     = OUTPUT_DIR / "iocs.jsonl"
        self.message_log = OUTPUT_DIR / "messages.jsonl"
        self.timing_log  = OUTPUT_DIR / "timing_analysis.jsonl"
        self.cursor_file = OUTPUT_DIR / "last_seen.json"
        self.stats       = defaultdict(int)
        self.monitored_ids       = set()   # channel IDs we're listening to (dynamic)
        self.monitored_usernames = set()   # usernames already processed
        self.discovered_channels = {}      # username -> discovery metadata
        self._load_discovered()

    def _load_cursor(self):
        """Load the last-seen cursor (shutdown timestamp) from disk."""
        if not self.cursor_file.exists():
            return None
        try:
            return json.loads(self.cursor_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cursor(self):
        """Persist the current timestamp as the cursor so next startup can fill the gap."""
        try:
            self.cursor_file.write_text(
                json.dumps({"last_run_stopped": datetime.now(timezone.utc).isoformat()},
                           ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"[CURSOR] Failed to save cursor: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # LIVE DISCOVERY ENGINE
    # ──────────────────────────────────────────────────────────────────────────

    def _load_discovered(self):
        """Load previously discovered channels from disk."""
        if DISCOVERY_FILE.exists():
            try:
                self.discovered_channels = json.loads(
                    DISCOVERY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.discovered_channels = {}

    def _save_discovered(self):
        """Persist discovered channels to disk."""
        try:
            DISCOVERY_FILE.write_text(
                json.dumps(self.discovered_channels, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            log.warning(f"[DISCOVERY] Save error: {e}")

    def _score_text_for_relevance(self, text):
        """
        Score text for Jordan/hacktivist relevance.
        Returns (score 0-100, list of matching keywords).
        """
        if not text:
            return 0, []
        text_lower = text.lower()
        critical_hits = [kw for kw in KEYWORDS_CRITICAL if kw.lower() in text_lower]
        medium_hits   = [kw for kw in KEYWORDS_MEDIUM   if kw.lower() in text_lower]
        hack_hits     = [kw for kw in HACKTIVIST_KEYWORDS if kw in text_lower]
        # Bonus: known threat actor group names in text
        group_hits    = [g for g in KNOWN_GROUP_NAMES if g in text_lower]
        score = (len(critical_hits) * 25 + len(medium_hits) * 8
                 + len(hack_hits) * 5 + len(group_hits) * 30)
        return min(score, 100), critical_hits + medium_hits

    def _looks_like_hacktivist_channel(self, username, title=""):
        """Quick heuristic: does this username/title look like a hacktivist channel?"""
        combined = (username + " " + title).lower()
        return (any(kw in combined for kw in HACKTIVIST_KEYWORDS)
                or any(g in combined for g in KNOWN_GROUP_NAMES))

    async def _check_and_add_channel(self, username, reason, score):
        """
        Evaluate a discovered username.
        If score >= 40 → auto-queue for monitoring.
        Always log to discovered_channels.json for admin review.
        """
        if not username or len(username) < 4:
            return
        uname_lower = username.lower()

        # Skip already monitored
        if uname_lower in self.monitored_usernames:
            return

        existing = self.discovered_channels.get(uname_lower)
        if existing:
            # Update score if we found a higher one
            if score > existing.get("score", 0):
                existing["score"] = score
                existing["reason"] = reason
                existing["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save_discovered()
            return

        # Attempt to fetch channel metadata for richer vetting context
        metadata = {}
        try:
            entity = await self.client.get_entity(username)
            metadata = {
                "about": getattr(entity, "about", "") or "",
                "participants_count": getattr(entity, "participants_count", 0) or 0,
                "scam": bool(getattr(entity, "scam", False)),
                "title": getattr(entity, "title", "") or "",
            }
        except Exception:
            pass

        entry = {
            "username": username,
            "score": score,
            "reason": reason,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_review",
            "auto_added": score >= 40,
            "metadata": metadata,
        }
        self.discovered_channels[uname_lower] = entry
        log.info(f"[DISCOVERY] New channel: @{username} (score={score}, via {reason})"
                 + (f" — {metadata.get('participants_count',0):,} subs" if metadata else ""))
        self.stats["discovered"] += 1
        self._save_discovered()

        # Auto-queue if high relevance
        if score >= 40:
            await self._queue_for_monitoring(username)

    async def _queue_for_monitoring(self, username):
        """Add a channel to pending_channels.json for the auto-join task to pick up."""
        try:
            data = {}
            if PENDING_FILE.exists():
                try:
                    data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            pending    = data.get("pending", [])
            processed  = data.get("processed", [])
            if username not in pending and username not in processed:
                pending.append(username)
                data["pending"]    = pending
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                PENDING_FILE.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                log.info(f"[DISCOVERY] Auto-queued @{username} for monitoring")
        except Exception as e:
            log.warning(f"[DISCOVERY] Queue error for @{username}: {e}")

    async def _scan_message_for_channels(self, message, text):
        """
        Real-time scan of an incoming message for new channel references:
        1. Forwarded-from channel (including private channels by ID)
        2. @mentions in text
        3. t.me/ public links in text
        4. t.me/+ and t.me/joinchat/ invite links (for private groups)
        """
        try:
            # 1. Forwarded from another channel
            if message.forward:
                fwd = message.forward
                fwd_chat = getattr(fwd, 'chat', None)
                if fwd_chat:
                    fwd_username = getattr(fwd_chat, 'username', None) or ''
                    fwd_title    = getattr(fwd_chat, 'title',    '') or ''
                    fwd_id       = getattr(fwd_chat, 'id', None)

                    if fwd_username and fwd_username.lower() not in self.monitored_usernames:
                        score, hits = self._score_text_for_relevance(text + " " + fwd_title)
                        if score > 0 or self._looks_like_hacktivist_channel(fwd_username, fwd_title):
                            await self._check_and_add_channel(
                                fwd_username,
                                f"forwarded_from:{fwd_title or fwd_username}",
                                max(score, 20))
                    elif not fwd_username and fwd_id:
                        # Private channel with no username — track by numeric ID
                        abs_id = abs(fwd_id)
                        if abs_id > 1_000_000_000_000:
                            abs_id = abs_id - 1_000_000_000_000
                        if abs_id not in self.monitored_ids and abs_id not in PRIVATE_CHANNELS:
                            score, hits = self._score_text_for_relevance(text + " " + fwd_title)
                            if score > 0 or self._looks_like_hacktivist_channel("", fwd_title):
                                self._store_private_channel_lead(
                                    abs_id, fwd_title,
                                    f"forwarded_from_private:{fwd_title}",
                                    max(score, 25))

            # 2. @mentions in text
            mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,})', text)
            for mention in mentions:
                if mention.lower() not in self.monitored_usernames:
                    score, hits = self._score_text_for_relevance(text)
                    if score > 0 or self._looks_like_hacktivist_channel(mention):
                        await self._check_and_add_channel(
                            mention, "mentioned_in_message", max(score, 15))

            # 3. t.me/ public links
            tme_links = re.findall(r't\.me/([a-zA-Z][a-zA-Z0-9_]{4,})', text)
            for link_user in tme_links:
                if link_user.lower() not in self.monitored_usernames:
                    score, hits = self._score_text_for_relevance(text)
                    if score > 0 or self._looks_like_hacktivist_channel(link_user):
                        await self._check_and_add_channel(
                            link_user, "tme_link_in_message", max(score, 15))

            # 4. Invite links — t.me/+HASH and t.me/joinchat/HASH (private group access)
            invite_hashes = re.findall(r't\.me/\+([A-Za-z0-9_-]{10,})', text)
            invite_hashes += re.findall(r't\.me/joinchat/([A-Za-z0-9_-]{10,})', text)
            for inv_hash in invite_hashes:
                score, hits = self._score_text_for_relevance(text)
                self._store_invite_link(inv_hash, text, max(score, 20))

        except Exception as e:
            log.debug(f"[DISCOVERY] Scan error: {e}")

    def _store_invite_link(self, invite_hash, context_text, score):
        """Store a discovered invite link for later auto-join attempts."""
        try:
            invite_file = OUTPUT_DIR / "discovered_invite_links.json"
            data = {}
            if invite_file.exists():
                try:
                    data = json.loads(invite_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            links = data.get("links", {})
            if invite_hash in links:
                # Already known — update score if higher
                if score > links[invite_hash].get("score", 0):
                    links[invite_hash]["score"] = score
                    links[invite_hash]["updated_at"] = datetime.now(timezone.utc).isoformat()
                return
            links[invite_hash] = {
                "hash": invite_hash,
                "score": score,
                "context": context_text[:300],
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",       # pending | joined | failed | irrelevant
                "join_attempts": 0,
                "channel_id": None,        # Filled after successful join
                "channel_title": None,
            }
            data["links"] = links
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            invite_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info(f"[DISCOVERY] New invite link: t.me/+{invite_hash[:20]}... (score={score})")
        except Exception as e:
            log.debug(f"[DISCOVERY] Invite link store error: {e}")

    def _store_private_channel_lead(self, channel_id, title, reason, score):
        """Store a private channel discovered via forward-chain for later join attempts."""
        try:
            leads_file = OUTPUT_DIR / "private_channel_leads.json"
            data = {}
            if leads_file.exists():
                try:
                    data = json.loads(leads_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            leads = data.get("leads", {})
            str_id = str(channel_id)
            if str_id in leads:
                if score > leads[str_id].get("score", 0):
                    leads[str_id]["score"] = score
                    leads[str_id]["sightings"] = leads[str_id].get("sightings", 0) + 1
                    leads[str_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                return
            leads[str_id] = {
                "channel_id": channel_id,
                "title": title,
                "reason": reason,
                "score": score,
                "sightings": 1,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",    # pending | joined | failed
            }
            data["leads"] = leads
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            leads_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info(f"[DISCOVERY] Private channel lead: ID {channel_id} ({title}) score={score}")
        except Exception as e:
            log.debug(f"[DISCOVERY] Private lead store error: {e}")

    async def _periodic_search(self):
        """
        Background task: every 45 minutes search Telegram for new hacktivist channels.
        Uses contacts.SearchRequest which searches channel names/usernames.
        """
        # Stagger start so it doesn't fire immediately on boot
        await asyncio.sleep(120)
        base_terms = [
            # Arabic terms
            "اختراق الاردن", "هاكرز الاردن", "هجوم سيبراني", "تسريب بيانات",
            "اختراق عربي", "الجيش الإلكتروني", "مقاومة إلكترونية",
            "هاكرز إيران", "سيبر إسلامي", "فاطميون سيبر",
            "تسريب اردن", "هجوم اردن", "هاكر عربي",
            "مقاومة سيبرانية", "جيش سيبراني", "عملية سيبرانية",
            # English terms — general
            "hack jordan", "jordan cyber", "cyber attack arab",
            "anonymous palestine", "anonymous sudan", "cyber resistance",
            "hackers team", "dark storm", "killnet", "islamic hackers",
            "iran cyber", "cyber army islam", "operation jordan",
            "hacktivist palestine", "hacktivist jordan", "hacktivist arab",
            "ddos jordan", "deface jordan", "leak jordan",
            "hack middle east", "cyber attack middle east",
            "pro palestine hackers", "islamic cyber army",
            # Known group names — direct search
            "rippersec", "ripper sec", "megamedusa",
            "cyber fattah", "cyberfattah", "fattah cyber",
            "dragonforce", "threatsec", "rootkit", "ghostsec",
            "sylhet gang", "team insane", "moroccan cyber",
            "handala hack", "handala cyber",
            "dark storm team", "darkstormteam",
            "team azrael", "angel of death hack",
            "cyber av3ngers", "cyberavengers",
            "stucx team", "stucxnet",
            "keymous team", "keymous hack",
            "indohaxsec", "garuda hacktivist",
            "lulzsec black", "lulzsec muslim",
            "altoufan team", "golden falcon hack",
            "mysterious team bangladesh", "eagle cyber crew",
            "z-pentest", "zpentest", "server killers",
            "people's cyber army", "holy league hacktivist",
            "1915 team", "turk hack team",
            "nation of saviors", "cyber isnaad",
            "gaza children hackers", "islamic hacker army",
            "dienet ddos", "anonghost",
            "fatemiyoun cyber", "313 team hack",
        ]
        while True:
            # Load AI-discovered search terms dynamically
            search_terms = list(base_terms)
            terms_file = OUTPUT_DIR / "discovery_search_terms.json"
            channel_leads = []
            if terms_file.exists():
                try:
                    tdata = json.loads(terms_file.read_text(encoding="utf-8"))
                    ai_terms = [t["term"] for t in tdata.get("terms", [])
                                if int(t.get("confidence", 0)) >= 65]
                    search_terms = list(dict.fromkeys(base_terms + ai_terms))
                    channel_leads = [c["username"] for c in tdata.get("channel_leads", [])
                                     if c.get("username") and int(c.get("confidence", 0)) >= 75]
                except Exception as e:
                    log.debug(f"[DISCOVERY] Could not load discovery_search_terms.json: {e}")

            log.info(f"[DISCOVERY] Periodic search starting "
                     f"({len(search_terms)} terms, {len(channel_leads)} direct leads)...")
            found_count = 0

            # Direct resolution of high-confidence channel leads from AI
            for lead_uname in channel_leads:
                try:
                    if lead_uname.lower() not in self.monitored_usernames:
                        await self._check_and_add_channel(
                            lead_uname, "ai_direct_lead", 70)
                        found_count += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    log.debug(f"[DISCOVERY] Direct lead error for @{lead_uname}: {e}")

            for term in search_terms:
                try:
                    from telethon.tl.functions.contacts import SearchRequest
                    result = await self.client(SearchRequest(q=term, limit=15))
                    for chat in getattr(result, 'chats', []):
                        username = getattr(chat, 'username', None) or ''
                        title    = getattr(chat, 'title', '')    or ''
                        if not username:
                            continue
                        score, hits = self._score_text_for_relevance(title + " " + term)
                        if score > 0 or self._looks_like_hacktivist_channel(username, title):
                            await self._check_and_add_channel(
                                username,
                                f"periodic_search:{term}",
                                max(score, 20))
                            found_count += 1
                    await asyncio.sleep(3)  # Rate-limit between searches
                except Exception as e:
                    log.debug(f"[DISCOVERY] Search error for '{term}': {e}")
            log.info(f"[DISCOVERY] Periodic search done — {found_count} new candidates found")
            await asyncio.sleep(2700)  # Run every 45 minutes

    # ──────────────────────────────────────────────────────────────────────────

    def _to_irst(self, utc_dt):
        """Convert UTC datetime to Iran Standard Time for timing analysis"""
        return utc_dt + IRST_OFFSET

    def _extract_iocs(self, text):
        """Extract all indicators of compromise from message text"""
        iocs = {}
        for ioc_type, pattern in IOC_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                iocs[ioc_type] = list(set(matches))
        return iocs

    @staticmethod
    def _normalize_arabic(s):
        """Strip Arabic diacritics and normalize alef/ta-marbuta variants for fuzzy matching"""
        import unicodedata
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        return s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه')

    @staticmethod
    def _detect_language(text):
        """Detect primary script: 'fa' Farsi, 'ar' Arabic, 'en' English, 'mixed'"""
        FARSI_SPECIFIC = set('گچپژکی')  # chars present in Farsi but NOT standard Arabic
        farsi_count  = sum(1 for c in text if c in FARSI_SPECIFIC)
        arabic_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        latin_count  = sum(1 for c in text if c.isascii() and c.isalpha())
        if farsi_count >= 3:
            return 'fa'
        if arabic_count > latin_count * 2:
            return 'ar'
        if latin_count > arabic_count:
            return 'en'
        return 'mixed'

    def _check_keywords(self, text):
        """Check message against keyword lists, return (priority, hits, critical_subtype)."""
        lang = self._detect_language(text)
        # Map Jordan flag emoji to 'jordan'
        text = text.replace('\U0001F1EF\U0001F1F4', ' jordan ')
        # Normalize Arabic diacritics for fuzzy matching
        text_norm  = self._normalize_arabic(text).lower()
        text_lower = text.lower()

        critical_hits = [kw for kw in KEYWORDS_CRITICAL
                         if kw.lower() in text_lower or self._normalize_arabic(kw).lower() in text_norm]
        medium_hits   = [kw for kw in KEYWORDS_MEDIUM
                         if kw.lower() in text_lower or self._normalize_arabic(kw).lower() in text_norm]

        priority = "LOW"
        if critical_hits:
            # Farsi spam reduction: single-hit Farsi messages → MEDIUM (unless 2+ hits)
            if lang == 'fa' and len(critical_hits) < 2:
                priority = "MEDIUM"
            else:
                priority = "CRITICAL"
        elif medium_hits:
            priority = "MEDIUM"

        # Compute critical_subtype for CRITICAL messages
        critical_subtype = None
        if priority == "CRITICAL":
            hits_lower   = [kw.lower() for kw in critical_hits]
            cyber_set    = {s.lower() for s in CYBER_CRITICAL_SIGNALS}
            national_set = {s.lower() for s in NATIONAL_CRITICAL_SIGNALS}
            # Substring match: signal keyword appears inside the hit phrase (or exact match)
            is_cyber    = any(sig in hit for hit in hits_lower for sig in cyber_set)
            is_national = any(sig in hit for hit in hits_lower for sig in national_set)
            # Demote service/sale ads unless Jordan is mentioned
            if is_cyber and not is_national:
                svc_count = sum(1 for sig in SERVICE_AD_SIGNALS if sig in text_lower)
                if svc_count >= 2 and not any(ref in text_lower for ref in JORDAN_REFS):
                    is_cyber = False  # demote to GENERAL

            if is_cyber and is_national:
                critical_subtype = "BOTH"
            elif is_cyber:
                critical_subtype = "CYBER"
            elif is_national:
                critical_subtype = "NATIONAL"
            else:
                critical_subtype = "GENERAL"

        return priority, critical_hits + medium_hits, critical_subtype

    def _write_jsonl(self, filepath, data):
        """Append a JSON line to file AND insert to SQLite."""
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
        # Also insert into SQLite messages table
        if _SQLITE_OK and filepath == self.message_log and data.get("channel_username"):
            try:
                _db.insert_message(data)
            except Exception:
                pass

    async def _process_message(self, event):
        """Process incoming message from monitored channel"""
        try:
            message = event.message
            if not message:
                return

            # Extract text from body, or from media caption / URL preview
            text = message.text or ""
            caption_source = False
            if not text and message.media:
                caption = getattr(message.media, "caption", None)
                if caption:
                    text = caption
                    caption_source = True
                elif hasattr(message.media, "webpage") and message.media.webpage:
                    wp = message.media.webpage
                    text = " ".join(filter(None, [
                        getattr(wp, "title", "") or "",
                        getattr(wp, "description", "") or "",
                    ]))
                    caption_source = True
            if not text:
                return
            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_title = getattr(chat, 'title', getattr(chat, 'username', 'unknown'))
            chat_username = getattr(chat, 'username', None) or ''

            # Debug: log every incoming event so we can see what's arriving
            log.info(f"[EVENT] @{chat_username or '(no-username)'} | {chat_title[:40]} | {text[:60].replace(chr(10),' ')}")

            # Live discovery: scan ALL incoming messages for new channel mentions/forwards
            # even those from channels we don't monitor (that's how we find new ones)
            asyncio.create_task(self._scan_message_for_channels(message, text))

            # Only process messages from channels we're explicitly monitoring
            # (filters out personal DMs, unrelated groups, etc.)
            if chat_username.lower() not in self.monitored_usernames:
                log.info(f"[EVENT-SKIP] @{chat_username} not in watchlist ({len(self.monitored_usernames)} entries)")
                return
            sender_name = getattr(sender, 'first_name', '') if sender else 'unknown'
            sender_id = getattr(sender, 'id', 'unknown') if sender else 'unknown'

            utc_time = message.date.replace(tzinfo=timezone.utc)
            irst_time = self._to_irst(utc_time)

            # Check keywords — returns (priority, hits, critical_subtype)
            priority, keyword_hits, critical_subtype = self._check_keywords(text)
            lang = self._detect_language(text)

            # Extract IOCs
            iocs = self._extract_iocs(text)

            # If Farsi with IOCs present, upgrade back to CRITICAL even with 1 keyword hit
            if lang == 'fa' and priority == "MEDIUM" and iocs and keyword_hits:
                priority = "CRITICAL"
                hits_lower   = [kw.lower() for kw in keyword_hits]
                cyber_set    = {s.lower() for s in CYBER_CRITICAL_SIGNALS}
                national_set = {s.lower() for s in NATIONAL_CRITICAL_SIGNALS}
                is_cyber    = any(sig in hit for hit in hits_lower for sig in cyber_set)
                is_national = any(sig in hit for hit in hits_lower for sig in national_set)
                if is_cyber and is_national:   critical_subtype = "BOTH"
                elif is_cyber:                 critical_subtype = "CYBER"
                elif is_national:              critical_subtype = "NATIONAL"
                else:                          critical_subtype = "GENERAL"

            # Base record
            record = {
                "timestamp_utc": utc_time.isoformat(),
                "timestamp_irst": irst_time.strftime("%Y-%m-%d %H:%M:%S IRST"),
                "irst_hour": irst_time.hour,
                "irst_weekday": irst_time.strftime("%A"),
                "channel": chat_title,
                "channel_username": chat_username,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "message_id": message.id,
                "text_preview": text,
                "priority": priority,
                "keyword_hits": keyword_hits,
                "iocs": iocs,
                "has_media": message.media is not None,
                "media_type": type(message.media).__name__ if message.media else None,
                "language": lang,
                "critical_subtype": critical_subtype,
            }

            # Always log messages
            self._write_jsonl(self.message_log, record)

            # Log timing data for pattern analysis
            timing_record = {
                "timestamp_utc": utc_time.isoformat(),
                "irst_hour": irst_time.hour,
                "irst_weekday": irst_time.strftime("%A"),
                "channel": chat_title,
                "sender_id": sender_id,
            }
            self._write_jsonl(self.timing_log, timing_record)

            # Download media for CRITICAL and MEDIUM messages
            if message.media and priority in ("CRITICAL", "MEDIUM"):
                try:
                    media_dir = OUTPUT_DIR / "media" / f"{chat_username}_{message.id}"
                    media_dir.mkdir(parents=True, exist_ok=True)
                    dl_path = await message.download_media(file=str(media_dir))
                    if dl_path:
                        record["media_path"] = str(Path(dl_path).relative_to(OUTPUT_DIR))
                        log.info(f"  Media saved: {record['media_path']}")
                except Exception as _me:
                    log.warning(f"  Media download failed: {_me}")

            # Handle based on priority
            if priority == "CRITICAL":
                self.stats["critical"] += 1
                self._write_jsonl(self.alert_log, record)
                log.critical(
                    f"{'='*60}\n"
                    f"CRITICAL ALERT - JORDAN TARGETING DETECTED\n"
                    f"Channel: {chat_title} (@{chat_username})\n"
                    f"Time: {utc_time.isoformat()} UTC / {irst_time.strftime('%H:%M')} IRST\n"
                    f"Keywords: {keyword_hits}\n"
                    f"IOCs: {json.dumps(iocs, ensure_ascii=False) if iocs else 'none'}\n"
                    f"Text: {text[:300]}\n"
                    f"{'='*60}"
                )

            elif priority == "MEDIUM":
                self.stats["medium"] += 1
                self._write_jsonl(self.alert_log, record)
                log.warning(
                    f"MEDIUM: [{chat_title}] Keywords: {keyword_hits} | "
                    f"IRST: {irst_time.strftime('%H:%M %A')}"
                )

            # Log IOCs separately for easy extraction
            if iocs:
                self.stats["iocs"] += 1
                ioc_record = {
                    "timestamp_utc": utc_time.isoformat(),
                    "channel": chat_title,
                    "iocs": iocs,
                    "context": text[:200],
                }
                self._write_jsonl(self.ioc_log, ioc_record)
                log.info(f"IOCs extracted from {chat_title}: {json.dumps(iocs, ensure_ascii=False)}")

            self.stats["total"] += 1

        except Exception as e:
            log.error(f"Error processing message: {e}")

    async def _join_channels(self):
        """Attempt to join/monitor all channels in the watchlist"""
        joined = []
        failed = []

        # Pre-populate usernames from the full watchlist IMMEDIATELY so that
        # _process_message() never drops a message just because get_entity()
        # failed (e.g. during a Telegram FloodWait period).
        for channel in ALL_CHANNELS:
            if channel and not channel.endswith("_bot"):
                self.monitored_usernames.add(channel.lower())
        log.info(f"Pre-populated {len(self.monitored_usernames)} watchlist usernames")

        # ── CRITICAL: load all dialogs first ────────────────────────────────
        # Telethon only delivers NewMessage events for channels the account
        # is subscribed to.  get_dialogs() bulk-loads all subscribed groups
        # into entity cache without per-username rate limits.
        log.info("Loading all dialogs to populate entity cache…")
        dialog_by_username = {}
        try:
            for folder in (0, 1):  # 0=main, 1=archived
                try:
                    dialogs = await self.client.get_dialogs(limit=None, folder=folder)
                    for d in dialogs:
                        entity = d.entity
                        un = getattr(entity, 'username', None)
                        if un:
                            dialog_by_username[un.lower()] = entity
                            self.monitored_ids.add(entity.id)
                except Exception as fe:
                    log.warning(f"get_dialogs(folder={folder}) error: {fe}")
            log.info(f"Loaded {len(dialog_by_username)} subscribed channels from dialogs")
        except Exception as e:
            log.warning(f"get_dialogs() failed: {e}")

        # ── Load session entity cache for channels not yet in dialogs ────────
        # The .session SQLite file caches every entity ever resolved, including
        # their access_hash.  We can join channels using cached hashes without
        # making any new ResolveUsernameRequest (which is FloodWaited).
        session_entities = {}  # username.lower() → (id, access_hash)
        try:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect("jordan_cyber_intel.session")
            for row in conn.execute("SELECT id, hash, username FROM entities WHERE username IS NOT NULL"):
                eid, ehash, eun = row
                if eun:
                    session_entities[eun.lower()] = (eid, ehash)
            conn.close()
            log.info(f"Session cache has {len(session_entities)} username entities")
        except Exception as e:
            log.warning(f"Could not read session cache: {e}")

        for channel in ALL_CHANNELS:
            if not channel or channel.endswith("_bot"):
                continue
            clow = channel.lower()

            # Already subscribed — events will flow automatically
            if clow in dialog_by_username:
                entity = dialog_by_username[clow]
                joined.append(channel)
                log.info(f"Monitoring (subscribed): {channel} (ID: {entity.id})")
                continue

            # Not subscribed but we have a cached entity ID → try joining by ID
            # Session stores IDs as -100XXXX; PeerChannel needs the positive channel ID.
            if clow in session_entities:
                eid, ehash = session_entities[clow]
                # Convert -100XXXX → raw channel ID (positive)
                raw_id = abs(eid)
                if raw_id > 1_000_000_000_000:
                    raw_id = raw_id - 1_000_000_000_000
                try:
                    entity = await self.client.get_entity(PeerChannel(raw_id))
                    await self.client(JoinChannelRequest(entity))
                    joined.append(channel)
                    self.monitored_ids.add(entity.id)
                    dialog_by_username[clow] = entity
                    log.info(f"Monitoring (joined via cache): {channel} (ID: {raw_id})")
                    continue
                except Exception as e:
                    log.warning(f"Join via cache failed for {channel}: {e}")

            # Last resort: get_entity by username — may be FloodWaited
            try:
                entity = await self.client.get_entity(channel)
                await self.client(JoinChannelRequest(entity))
                joined.append(channel)
                self.monitored_ids.add(entity.id)
                log.info(f"Monitoring (joined): {channel} (ID: {entity.id})")
            except Exception as e:
                failed.append((channel, str(e)))
                log.warning(f"Cannot access {channel}: {e}")

        # ── Join private channels by numeric ID ──────────────────────────
        for ch_id, ch_info in PRIVATE_CHANNELS.items():
            label = ch_info.get("label", f"private_{ch_id}")
            try:
                entity = await self.client.get_entity(PeerChannel(ch_id))
                self.monitored_ids.add(entity.id)
                ch_uname = getattr(entity, "username", None) or f"c_{ch_id}"
                self.monitored_usernames.add(ch_uname.lower())
                joined.append(f"{ch_uname} ({label})")
                log.info(f"Monitoring (private): {label} (ID: {ch_id}, username: {ch_uname})")
            except Exception as e:
                failed.append((f"ID:{ch_id} ({label})", str(e)))
                log.warning(f"Cannot access private channel {ch_id} ({label}): {e}")

        log.info(f"\nMonitoring {len(joined)} channels, {len(failed)} failed")
        if failed:
            log.info("Failed channels (may be banned/private/renamed):")
            for ch, err in failed:
                log.info(f"  - {ch}: {err}")

        return joined

    # Default backfill floor: at least 1000 msgs AND at least back to Feb 1 2026
    _BACKFILL_MIN_MSGS = 1000
    _BACKFILL_MIN_DATE = datetime(2026, 2, 1, tzinfo=timezone.utc)

    async def _backfill_single(self, channel, min_msgs=None, min_date=None):
        """
        Backfill a single channel.
        Keeps fetching until BOTH conditions are satisfied:
          - At least min_msgs messages fetched
          - Reached back to min_date
        Whichever takes longer — we keep going until both are done.
        """
        min_msgs = min_msgs or self._BACKFILL_MIN_MSGS
        min_date = min_date or self._BACKFILL_MIN_DATE
        log.info(f"  Backfill @{channel}: min {min_msgs} msgs, min date {min_date.strftime('%Y-%m-%d')}...")
        count = 0
        try:
            chat = await self.client.get_entity(channel)
            chat_title    = getattr(chat, 'title',    getattr(chat, 'username', channel))
            chat_username = getattr(chat, 'username', channel)

            # limit=None → fetch unlimited; we break manually when both conditions met
            async for message in self.client.iter_messages(channel, limit=None):
                if not message or not message.text:
                    continue
                text = message.text
                utc_time  = message.date.replace(tzinfo=timezone.utc)

                # Stop only when BOTH conditions are satisfied
                if count >= min_msgs and utc_time <= min_date:
                    break

                irst_time = self._to_irst(utc_time)
                priority, keyword_hits, critical_subtype = self._check_keywords(text)
                lang = self._detect_language(text)
                iocs = self._extract_iocs(text)

                record = {
                    "timestamp_utc":  utc_time.isoformat(),
                    "timestamp_irst": irst_time.strftime("%Y-%m-%d %H:%M:%S IRST"),
                    "irst_hour":      irst_time.hour,
                    "irst_weekday":   irst_time.strftime("%A"),
                    "channel":        chat_title,
                    "channel_username": chat_username,
                    "sender_name":    "unknown",
                    "sender_id":      getattr(message, 'sender_id', 'unknown'),
                    "message_id":     message.id,
                    "text_preview":   text,
                    "priority":       priority,
                    "keyword_hits":   keyword_hits,
                    "iocs":           iocs,
                    "has_media":      message.media is not None,
                    "media_type":     type(message.media).__name__ if message.media else None,
                    "language":       lang,
                    "critical_subtype": critical_subtype,
                    "backfill":       True,
                }
                # Download media for CRITICAL/MEDIUM backfills
                if message.media and priority in ("CRITICAL", "MEDIUM"):
                    try:
                        media_dir = OUTPUT_DIR / "media" / f"{chat_username}_{message.id}"
                        media_dir.mkdir(parents=True, exist_ok=True)
                        dl_path = await message.download_media(file=str(media_dir))
                        if dl_path:
                            record["media_path"] = str(Path(dl_path).relative_to(OUTPUT_DIR))
                    except Exception:
                        pass
                self._write_jsonl(self.message_log, record)
                if priority in ("CRITICAL", "MEDIUM"):
                    self._write_jsonl(self.alert_log, record)
                    self.stats[priority.lower()] += 1
                if iocs:
                    self._write_jsonl(self.ioc_log, {"timestamp_utc": utc_time.isoformat(),
                                                      "channel": chat_title, "iocs": iocs,
                                                      "context": text[:200]})
                    self.stats["iocs"] += 1
                self.stats["total"] += 1
                count += 1

                # Scan backfilled messages for invite links + channel refs
                asyncio.create_task(self._scan_message_for_channels(message, text))

        except Exception as e:
            log.error(f"  Backfill error @{channel}: {e}")
        log.info(f"  Backfill @{channel}: {count} messages saved")

    async def _auto_join_pending(self):
        """Every 5 minutes, check pending_channels.json for new channels to join."""
        while True:
            await asyncio.sleep(300)
            if not PENDING_FILE.exists():
                continue
            try:
                with open(PENDING_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                pending = [ch for ch in data.get("pending", [])
                           if ch.lower() not in self.monitored_usernames]
                if not pending:
                    continue
                log.info(f"AUTO-JOIN: {len(pending)} pending channels to process")
                newly_joined, still_pending, permanently_failed = [], [], []
                # Error substrings that mean the channel will NEVER exist — discard immediately
                _PERM_FAIL = ("no user has", "nobody is using this username",
                              "username is unacceptable", "no peer id found")
                for ch in pending:
                    try:
                        entity = await self.client.get_entity(ch)
                        self.monitored_ids.add(entity.id)
                        self.monitored_usernames.add(ch.lower())
                        log.info(f"  AUTO-JOINED: @{ch} (ID: {entity.id})")
                        await self._backfill_single(ch)
                        newly_joined.append(ch)
                    except Exception as e:
                        err_lower = str(e).lower()
                        if any(kw in err_lower for kw in _PERM_FAIL):
                            log.warning(f"  PERMANENT FAIL @{ch} — discarding: {e}")
                            permanently_failed.append(ch)
                        else:
                            log.warning(f"  Cannot join @{ch} (will retry): {e}")
                            still_pending.append(ch)

                data["pending"]    = still_pending
                data["processed"]  = list(set(data.get("processed", []) + newly_joined))
                data["failed"]     = list(set(data.get("failed", []) + permanently_failed))
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                with open(PENDING_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                if newly_joined:
                    log.info(f"AUTO-JOIN complete: +{len(newly_joined)} channels, "
                             f"now monitoring {len(self.monitored_ids)} total")
                if permanently_failed:
                    log.info(f"AUTO-JOIN discarded {len(permanently_failed)} non-existent channels")
            except Exception as e:
                log.error(f"Auto-join error: {e}")

    async def _auto_join_invite_links(self):
        """Every 10 minutes, try to join discovered invite links."""
        await asyncio.sleep(180)  # Stagger: 3 min after boot
        invite_file = OUTPUT_DIR / "discovered_invite_links.json"
        _MAX_ATTEMPTS = 3
        while True:
            try:
                if not invite_file.exists():
                    await asyncio.sleep(600)
                    continue
                data = json.loads(invite_file.read_text(encoding="utf-8"))
                links = data.get("links", {})
                pending = {h: info for h, info in links.items()
                           if info.get("status") == "pending"
                           and info.get("join_attempts", 0) < _MAX_ATTEMPTS}
                if not pending:
                    await asyncio.sleep(600)
                    continue

                log.info(f"[INVITE-JOIN] Processing {len(pending)} pending invite links...")
                joined, failed = 0, 0
                for inv_hash, info in list(pending.items())[:10]:  # Max 10 per cycle
                    try:
                        info["join_attempts"] = info.get("join_attempts", 0) + 1
                        # First check what the invite leads to
                        check = await self.client(CheckChatInviteRequest(hash=inv_hash))
                        title = getattr(check, 'title', '') or ''
                        about = getattr(check, 'about', '') or ''
                        participants = getattr(check, 'participants_count', 0) or 0

                        # Score the invite to see if it's relevant
                        score, hits = self._score_text_for_relevance(
                            title + " " + about + " " + info.get("context", ""))
                        is_hacktivist = self._looks_like_hacktivist_channel("", title + " " + about)

                        if score > 0 or is_hacktivist or info.get("score", 0) >= 20:
                            # Relevant — join it
                            result = await self.client(ImportChatInviteRequest(hash=inv_hash))
                            chat = result.chats[0] if result.chats else None
                            if chat:
                                ch_id = chat.id
                                ch_uname = getattr(chat, 'username', None) or f"c_{ch_id}"
                                self.monitored_ids.add(ch_id)
                                self.monitored_usernames.add(ch_uname.lower())
                                info["status"] = "joined"
                                info["channel_id"] = ch_id
                                info["channel_title"] = title or getattr(chat, 'title', '')
                                info["joined_at"] = datetime.now(timezone.utc).isoformat()
                                joined += 1
                                log.info(f"[INVITE-JOIN] JOINED via invite: {title or ch_uname} "
                                         f"(ID: {ch_id}, {participants} members)")
                                # Backfill messages from the newly joined channel
                                await self._backfill_single(ch_uname)
                            else:
                                info["status"] = "failed"
                                info["error"] = "No chat in result"
                        else:
                            info["status"] = "irrelevant"
                            info["reason"] = f"Low relevance score={score}"
                            log.debug(f"[INVITE-JOIN] Skipped irrelevant invite: {title}")

                    except Exception as e:
                        err_str = str(e).lower()
                        if "expired" in err_str or "revoked" in err_str:
                            info["status"] = "failed"
                            info["error"] = "Invite expired/revoked"
                        elif "already" in err_str and ("participant" in err_str or "member" in err_str):
                            # Already in this chat — mark as joined
                            info["status"] = "joined"
                            info["note"] = "Already a member"
                            log.info(f"[INVITE-JOIN] Already member of invite {inv_hash[:15]}...")
                        elif "flood" in err_str:
                            log.warning(f"[INVITE-JOIN] FloodWait — pausing invite joins")
                            break  # Stop processing this cycle
                        else:
                            failed += 1
                            if info.get("join_attempts", 0) >= _MAX_ATTEMPTS:
                                info["status"] = "failed"
                                info["error"] = str(e)
                            log.debug(f"[INVITE-JOIN] Error for {inv_hash[:15]}: {e}")
                        await asyncio.sleep(5)
                    await asyncio.sleep(8)  # Conservative rate limit between joins

                # Save updated state
                data["links"] = links
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                invite_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                if joined:
                    log.info(f"[INVITE-JOIN] Cycle complete: {joined} joined, {failed} failed")
            except Exception as e:
                log.error(f"[INVITE-JOIN] Error: {e}")
            await asyncio.sleep(600)  # Every 10 minutes

    async def _auto_join_private_leads(self):
        """Every 15 minutes, try to join private channels discovered via forward-chain."""
        await asyncio.sleep(240)  # Stagger: 4 min after boot
        leads_file = OUTPUT_DIR / "private_channel_leads.json"
        while True:
            try:
                if not leads_file.exists():
                    await asyncio.sleep(900)
                    continue
                data = json.loads(leads_file.read_text(encoding="utf-8"))
                leads = data.get("leads", {})
                pending = {cid: info for cid, info in leads.items()
                           if info.get("status") == "pending"
                           and info.get("sightings", 0) >= 2}  # Need 2+ sightings for confidence
                if not pending:
                    await asyncio.sleep(900)
                    continue

                log.info(f"[PRIVATE-JOIN] Processing {len(pending)} private channel leads...")
                for str_id, info in list(pending.items())[:5]:  # Max 5 per cycle
                    ch_id = int(str_id)
                    if ch_id in self.monitored_ids:
                        info["status"] = "joined"
                        continue
                    try:
                        entity = await self.client.get_entity(PeerChannel(ch_id))
                        self.monitored_ids.add(entity.id)
                        ch_uname = getattr(entity, "username", None) or f"c_{ch_id}"
                        self.monitored_usernames.add(ch_uname.lower())
                        info["status"] = "joined"
                        info["joined_at"] = datetime.now(timezone.utc).isoformat()
                        info["username"] = ch_uname
                        log.info(f"[PRIVATE-JOIN] Joined private channel: {info.get('title','')} "
                                 f"(ID: {ch_id}, username: {ch_uname})")
                        await self._backfill_single(ch_uname)
                    except Exception as e:
                        err_str = str(e).lower()
                        if "channel_private" in err_str or "not a member" in err_str:
                            # Can't access — need invite link
                            info["status"] = "needs_invite"
                            info["error"] = "Not a member — need invite link"
                            log.info(f"[PRIVATE-JOIN] {info.get('title','')} (ID: {ch_id}) — "
                                     f"needs invite link (private, not a member)")
                        else:
                            log.debug(f"[PRIVATE-JOIN] Error for ID {ch_id}: {e}")
                    await asyncio.sleep(5)

                data["leads"] = leads
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                leads_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                log.error(f"[PRIVATE-JOIN] Error: {e}")
            await asyncio.sleep(900)  # Every 15 minutes

    async def _backfill_existing_invite_links(self):
        """One-time scan: extract invite links from ALL existing messages in the DB."""
        await asyncio.sleep(30)  # Short delay on boot
        invite_file = OUTPUT_DIR / "discovered_invite_links.json"
        # Check if we've already done the backfill scan
        already_done = False
        if invite_file.exists():
            try:
                data = json.loads(invite_file.read_text(encoding="utf-8"))
                if data.get("backfill_complete"):
                    already_done = True
            except Exception:
                pass
        if already_done:
            log.info("[INVITE-BACKFILL] Already completed — skipping")
            return

        log.info("[INVITE-BACKFILL] Scanning all DB messages for invite links...")
        count = 0
        try:
            if _SQLITE_OK:
                from app.database import query as db_query
                rows = db_query(
                    "SELECT text_preview, full_text FROM messages "
                    "WHERE text_preview LIKE '%t.me/+%' OR text_preview LIKE '%t.me/joinchat%' "
                    "OR full_text LIKE '%t.me/+%' OR full_text LIKE '%t.me/joinchat%'")
                for row in rows:
                    text = (row.get("full_text") or row.get("text_preview") or "")
                    invite_hashes = re.findall(r't\.me/\+([A-Za-z0-9_-]{10,})', text)
                    invite_hashes += re.findall(r't\.me/joinchat/([A-Za-z0-9_-]{10,})', text)
                    for inv_hash in invite_hashes:
                        score, _ = self._score_text_for_relevance(text)
                        self._store_invite_link(inv_hash, text, max(score, 15))
                        count += 1
            else:
                # Fallback: scan JSONL
                msg_file = OUTPUT_DIR / "messages.jsonl"
                if msg_file.exists():
                    with open(msg_file, encoding="utf-8") as f:
                        for line in f:
                            if "t.me/+" not in line and "t.me/joinchat" not in line:
                                continue
                            try:
                                m = json.loads(line.strip())
                                text = m.get("text_preview", "") or ""
                                invite_hashes = re.findall(r't\.me/\+([A-Za-z0-9_-]{10,})', text)
                                invite_hashes += re.findall(r't\.me/joinchat/([A-Za-z0-9_-]{10,})', text)
                                for inv_hash in invite_hashes:
                                    score, _ = self._score_text_for_relevance(text)
                                    self._store_invite_link(inv_hash, text, max(score, 15))
                                    count += 1
                            except Exception:
                                pass

            # Mark backfill as done
            data = {}
            if invite_file.exists():
                try:
                    data = json.loads(invite_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            data["backfill_complete"] = True
            data["backfill_at"] = datetime.now(timezone.utc).isoformat()
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            invite_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info(f"[INVITE-BACKFILL] Complete — found {count} invite links in existing messages")
        except Exception as e:
            log.error(f"[INVITE-BACKFILL] Error: {e}")

    def _compact_messages(self):
        """Deduplicate messages — uses SQLite for dedup, also compacts JSONL."""
        try:
            if _SQLITE_OK:
                result = _db.compact_messages()
                log.info(f"[COMPACT] SQLite: {result['remaining']} unique ({result['deleted']} dupes removed)")
            # Also compact JSONL file for backward compat
            lines = self.message_log.read_text(encoding="utf-8").splitlines()
            seen, msgs = {}, []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    key = f"{m.get('channel_username','')}_{m.get('message_id','')}"
                    if key not in seen:
                        seen[key] = True
                        msgs.append(m)
                except Exception:
                    pass
            msgs.sort(key=lambda x: x.get("timestamp_utc", ""))
            self.message_log.write_text(
                "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n",
                encoding="utf-8"
            )
            log.info(f"[COMPACT] JSONL: {len(msgs)} unique messages")
        except Exception as e:
            log.warning(f"[COMPACT] Error during compaction: {e}")

    async def _process_backfill_queue(self):
        """Check backfill_queue.json every 60s and process any pending requests."""
        while True:
            await asyncio.sleep(60)
            if not BACKFILL_QUEUE_FILE.exists():
                continue
            try:
                queue = json.loads(BACKFILL_QUEUE_FILE.read_text(encoding="utf-8"))
                pending = queue.get("pending", [])
                if not pending:
                    continue
                done = []
                for req in pending:
                    ch    = req.get("channel", "")
                    req_min_msgs = int(req.get("limit", 0)) or None
                    since_str = req.get("since", "")
                    req_min_date = None
                    if since_str:
                        try:
                            req_min_date = datetime.fromisoformat(since_str)
                        except Exception:
                            pass
                    log.info(f"[BF-QUEUE] Processing: @{ch} "
                             f"min_msgs={req_min_msgs or 'default'}, "
                             f"min_date={req_min_date or 'default'}")
                    # Auto-join if not already monitoring
                    if ch.lower() not in self.monitored_usernames:
                        try:
                            entity = await self.client.get_entity(ch)
                            self.monitored_ids.add(entity.id)
                            self.monitored_usernames.add(ch.lower())
                            log.info(f"[BF-QUEUE] Joined @{ch}")
                        except Exception as e:
                            log.warning(f"[BF-QUEUE] Cannot join @{ch}: {e}")
                            done.append({"channel": ch, "status": "failed", "error": str(e)})
                            continue
                    await self._backfill_single(ch, min_msgs=req_min_msgs,
                                                min_date=req_min_date)
                    self._compact_messages()
                    done.append({"channel": ch, "status": "done"})
                queue["pending"]   = []
                queue["completed"] = queue.get("completed", []) + done
                queue["updated_at"] = datetime.now(timezone.utc).isoformat()
                BACKFILL_QUEUE_FILE.write_text(
                    json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
                log.info(f"[BF-QUEUE] Processed {len(done)} requests")
            except Exception as e:
                log.error(f"[BF-QUEUE] Error: {e}")

    async def _print_stats(self):
        """Periodically print monitoring statistics and save cursor"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            log.info(
                f"STATS | Total: {self.stats['total']} | "
                f"Critical: {self.stats['critical']} | "
                f"Medium: {self.stats['medium']} | "
                f"IOCs: {self.stats['iocs']}"
            )
            self._save_cursor()  # Keep cursor fresh so gap is minimal if we crash

    async def backfill(self, limit=500, since_date=None):
        """Fetch historical messages from all accessible channels.
        Uses the standard backfill logic: at least 1000 msgs AND back to Feb 1 2026.
        CLI params override: limit → min_msgs, since_date → min_date.
        """
        await self.client.start(phone=PHONE)
        log.info("Authenticated successfully")

        active_channels = await self._join_channels()
        if not active_channels:
            log.error("No channels accessible. Update the watchlist.")
            return

        bf_min_msgs = max(limit, self._BACKFILL_MIN_MSGS)
        bf_min_date = since_date or self._BACKFILL_MIN_DATE
        log.info(f"\nBACKFILL STARTING — {len(active_channels)} channels, "
                 f"min {bf_min_msgs} msgs, back to {bf_min_date.strftime('%Y-%m-%d')}")

        for channel in active_channels:
            await self._backfill_single(channel, min_msgs=bf_min_msgs,
                                        min_date=bf_min_date)

        self._compact_messages()
        log.info(f"\nBACKFILL COMPLETE")
        log.info(f"  Total messages: {self.stats['total']}")
        log.info(f"  Critical alerts: {self.stats['critical']}")
        log.info(f"  Medium alerts:   {self.stats['medium']}")
        log.info(f"  IOCs extracted:  {self.stats['iocs']}")
        log.info(f"  Output: {OUTPUT_DIR.absolute()}")

    async def run(self):
        """Main monitoring loop"""
        log.info("="*60)
        log.info("TELEGRAM INTELLIGENCE MONITOR - STARTING")
        log.info(f"Output directory: {OUTPUT_DIR.absolute()}")
        log.info(f"Channels in watchlist: {len(ALL_CHANNELS)}")
        log.info("="*60)

        await self.client.start(phone=PHONE)
        log.info("Authenticated successfully")

        # Join channels and populate self.monitored_ids / self.monitored_usernames
        await self._join_channels()

        if not self.monitored_ids:
            log.error("No channels accessible. Update the watchlist.")
            return

        # ── Auto-resume: fill gap since last shutdown ─────────────────────────
        cursor = self._load_cursor()
        if cursor:
            last_stop_str = cursor.get("last_run_stopped", "")
            if last_stop_str:
                try:
                    last_stop = datetime.fromisoformat(last_stop_str)
                    gap_secs  = (datetime.now(timezone.utc) - last_stop).total_seconds()
                    gap_min   = gap_secs / 60
                    if gap_secs > 300:  # > 5 minutes gap
                        # Gap-fill: use last_stop as min_date, scale min_msgs by gap length
                        gap_min_msgs = max(50, min(1000, int(gap_secs / 3600 * 20)))
                        log.info(f"[RESUME] Gap of {gap_min:.0f} min detected since last run ({last_stop_str[:19]})")
                        log.info(f"[RESUME] Auto-backfilling (min {gap_min_msgs} msgs, back to {last_stop_str[:19]})...")
                        for ch in list(self.monitored_usernames):
                            await self._backfill_single(ch, min_msgs=gap_min_msgs,
                                                        min_date=last_stop)
                        # Compact messages.jsonl after gap-fill to remove duplicates
                        self._compact_messages()
                        log.info("[RESUME] Gap fill complete — resuming live monitoring")
                    else:
                        log.info(f"[RESUME] Short gap ({gap_min:.0f} min), skipping auto-backfill")
                except Exception as e:
                    log.warning(f"[RESUME] Error during auto-resume: {e}")
        else:
            log.info("[RESUME] No cursor found — starting fresh (first run)")
        # Save cursor immediately so a crash still marks last-seen
        self._save_cursor()
        # ─────────────────────────────────────────────────────────────────────

        # Catch-all handler — filter by username (not chat_id) because
        # Telethon channel event.chat_id is negative (-100xxxx) but
        # entity.id stored in monitored_ids is positive — they never match.
        # Filtering by username inside _process_message is correct.
        @self.client.on(events.NewMessage())
        async def handler(event):
            await self._process_message(event)

        log.info("\nLIVE MONITORING ACTIVE - Waiting for messages...")
        log.info(f"Monitoring {len(self.monitored_ids)} channels (auto-expanding via pending file)")
        log.info("Press Ctrl+C to stop\n")

        # Background tasks: stats printer + auto-join pending + backfill queue + discovery
        asyncio.create_task(self._print_stats())
        asyncio.create_task(self._auto_join_pending())
        asyncio.create_task(self._process_backfill_queue())
        asyncio.create_task(self._periodic_search())
        asyncio.create_task(self._auto_join_invite_links())
        asyncio.create_task(self._auto_join_private_leads())
        asyncio.create_task(self._backfill_existing_invite_links())
        log.info("[DISCOVERY] Live discovery engine started — scanning all messages + periodic search")
        log.info("[DISCOVERY] Invite link harvester + private channel tracker active")

        # Keep running — save cursor on any exit
        try:
            await self.client.run_until_disconnected()
        finally:
            self._save_cursor()
            log.info("[CURSOR] Shutdown cursor saved — next start will auto-resume from now")


# ==============================================================================
# ANALYSIS UTILITIES
# ==============================================================================

def analyze_timing(timing_file):
    """
    Analyze message timing to confirm Iranian operator hours.
    Run this after collecting data: python3 telegram_monitor.py --analyze-timing
    """
    hour_counts = defaultdict(int)
    weekday_counts = defaultdict(int)

    with open(timing_file, "r") as f:
        for line in f:
            record = json.loads(line)
            hour_counts[record["irst_hour"]] += 1
            weekday_counts[record["irst_weekday"]] += 1

    print("\n" + "="*60)
    print("TIMING ANALYSIS - IRST (Iran Standard Time UTC+3:30)")
    print("="*60)

    print("\nActivity by hour (IRST):")
    max_count = max(hour_counts.values()) if hour_counts else 1
    for hour in range(24):
        count = hour_counts.get(hour, 0)
        bar = "#" * int(40 * count / max_count) if max_count > 0 else ""
        label = "  <-- SLEEP" if 2 <= hour <= 7 else ""
        label = "  <-- PEAK" if 10 <= hour <= 23 else label
        print(f"  {hour:02d}:00  [{count:4d}] {bar}{label}")

    print("\nActivity by day (IRST):")
    for day in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        count = weekday_counts.get(day, 0)
        bar = "#" * int(40 * count / max_count) if max_count > 0 else ""
        label = "  <-- IRANIAN WEEKEND" if day == "Friday" else ""
        print(f"  {day:12s}  [{count:4d}] {bar}{label}")

    print("\nINTERPRETATION:")
    friday_count = weekday_counts.get("Friday", 0)
    avg_weekday = sum(weekday_counts.get(d, 0) for d in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]) / 6
    if avg_weekday > 0 and friday_count < avg_weekday * 0.6:
        print("  STRONG INDICATOR: Friday activity significantly lower than other days")
        print("  This is consistent with Iranian operators (Friday = Iranian weekend)")

    sleep_hours = sum(hour_counts.get(h, 0) for h in range(2, 8))
    active_hours = sum(hour_counts.get(h, 0) for h in range(10, 24))
    if active_hours > 0 and sleep_hours < active_hours * 0.15:
        print("  STRONG INDICATOR: Activity drops during IRST 02:00-07:00")
        print("  Consistent with operators sleeping on Iranian timezone")


def extract_all_iocs(ioc_file):
    """
    Extract and deduplicate all IOCs for import into your SIEM/firewall.
    Run: python3 telegram_monitor.py --extract-iocs
    """
    all_iocs = defaultdict(set)

    with open(ioc_file, "r") as f:
        for line in f:
            record = json.loads(line)
            for ioc_type, values in record.get("iocs", {}).items():
                all_iocs[ioc_type].update(values)

    print("\n" + "="*60)
    print("EXTRACTED IOCs - Import into SIEM/Firewall")
    print("="*60)

    for ioc_type, values in sorted(all_iocs.items()):
        print(f"\n[{ioc_type.upper()}] ({len(values)} unique)")
        # Write to separate files for easy import
        outfile = OUTPUT_DIR / f"iocs_{ioc_type}.txt"
        with open(outfile, "w") as f:
            for v in sorted(values):
                print(f"  {v}")
                f.write(v + "\n")
        print(f"  --> Saved to {outfile}")


# ==============================================================================
# CHANNEL DISCOVERY - Find new channels
# ==============================================================================

async def discover_channels(client):
    """
    Search Telegram for new Iranian hacktivist channels.
    Channels get banned and recreated constantly - run this daily.
    """
    search_terms = [
        "فاطميون",           # Fatemiyoun
        "فتح سايبري",        # Cyber Fattah
        "المقاومة الاسلامية سايبر",  # Cyber Islamic Resistance
        "هاكرز اسلامي",      # Islamic hackers
        "FaD TeaM",
        "cyber fattah",
        "islamic hacker army",
        "cyber resistance iran",
        "اختراق الاردن",      # hack jordan
        "هاكرز ايران",       # hackers iran
        "sharp333",
        "313 team",
    ]

    discovered = set()
    for term in search_terms:
        try:
            results = await client.get_dialogs()
            # Also try searching
            log.info(f"Searching: {term}")
            # Note: Telegram's search API has limitations
            # For better results, use tgscan.io or telegago externally
        except Exception as e:
            log.warning(f"Search error for '{term}': {e}")

    return discovered


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--analyze-timing":
            timing_file = OUTPUT_DIR / "timing_analysis.jsonl"
            if timing_file.exists():
                analyze_timing(timing_file)
            else:
                print(f"No timing data found at {timing_file}. Run monitor first.")
        elif sys.argv[1] == "--extract-iocs":
            ioc_file = OUTPUT_DIR / "iocs.jsonl"
            if ioc_file.exists():
                extract_all_iocs(ioc_file)
            else:
                print(f"No IOC data found at {ioc_file}. Run monitor first.")
        elif sys.argv[1] == "--backfill":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 500
            since_date = None
            if len(sys.argv) > 3:
                from datetime import datetime
                since_date = datetime.strptime(sys.argv[3], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            monitor = TelegramMonitor()
            asyncio.run(monitor.backfill(limit=limit, since_date=since_date))
        elif sys.argv[1] in ("--live", "--daemon"):
            monitor = TelegramMonitor()
            asyncio.run(monitor.run())
        else:
            print("Usage:")
            print("  python3 telegram_monitor.py                    # Start live monitoring")
            print("  python3 telegram_monitor.py --live             # Same (daemon-friendly alias)")
            print("  python3 telegram_monitor.py --backfill [N]     # Fetch last N msgs per channel (default 500)")
            print("  python3 telegram_monitor.py --analyze-timing   # Analyze operator timing")
            print("  python3 telegram_monitor.py --extract-iocs     # Extract IOCs for SIEM")
    else:
        monitor = TelegramMonitor()
        asyncio.run(monitor.run())
