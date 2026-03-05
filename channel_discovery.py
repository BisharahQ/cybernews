#!/usr/bin/env python3
"""
TELEGRAM CHANNEL DISCOVERY ENGINE
===================================
Finds new/current handles for Iranian hacktivist channels that get
banned and recreated constantly. Outputs discovered channels in a
format ready to plug into telegram_monitor.py

Run daily or after each ban wave.

Usage:
  python channel_discovery.py                  # Full discovery scan
  python channel_discovery.py --quick           # Quick scan (active channels only)
  python channel_discovery.py --export          # Export found channels to watchlist file
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    from telethon import TelegramClient, functions, types
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.tl.functions.messages import SearchGlobalRequest, GetHistoryRequest
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
except ImportError:
    print("ERROR: pip install telethon")
    exit(1)

# ==============================================================================
# CONFIG - Same credentials as telegram_monitor.py
# ==============================================================================
API_ID   = os.environ.get("TG_API_ID",   "35545979")
API_HASH = os.environ.get("TG_API_HASH", "41240e3f451065a430692d2e1bc82453")
PHONE    = os.environ.get("TG_PHONE",    "+962791896483")

OUTPUT_DIR     = Path("./telegram_intel")
OUTPUT_DIR.mkdir(exist_ok=True)
DISCOVERY_LOG  = OUTPUT_DIR / "discovered_channels.jsonl"
WATCHLIST_FILE = OUTPUT_DIR / "active_watchlist.json"
PENDING_FILE   = OUTPUT_DIR / "pending_channels.json"  # monitor picks this up

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_DIR / "discovery.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("Discovery")

# ==============================================================================
# SEARCH TERMS - Multi-language keywords to find hacktivist channels
# ==============================================================================
GROUP_SEARCH_TERMS = [
    # TIER 1 - Jordan attackers
    "Fatimion", "فاطميون", "Fatemiyoun", "FaD TeaM", "فاد تيم",
    "313 Team", "فريق 313", "313team",
    "DieNet", "داي نت", "die net",
    "LulzSec", "lulzsec black",
    "Handala", "حندلة", "هندلة", "handal",
    # TIER 2 - Iranian ecosystem
    "Cyber Islamic Resistance", "المقاومة الاسلامية السيبرانية",
    "المقاومة السيبرانية", "Cyber Fattah", "فتح سايبري",
    "fattah cyber", "سايبر فتح",
    "CyberAv3ngers", "Cyber Avengers", "سايبر انتقام",
    "Mr Hamza", "مستر حمزة",
    "RipperSec", "ripper sec",
    "AnonGhost", "انون غوست",
    "Sylhet Gang", "سيلهيت",
    "Keymous", "كيموس",
    "Nation of Saviors", "امة المنقذين",
    # TIER 3 - Allied groups
    "NoName057", "noname057",
    "Moroccan Black Cyber", "الجيش السيبراني المغربي",
    "Cyb3rDrag0nzz", "cyber dragonz",
    "Team Fearless", "فريق بلا خوف",
    "Al Toufan", "Cyber Toufan", "طوفان سايبر",
    "Holy League", "الحلف المقدس",
    "Islamic Hacker Army", "جيش الهاكرز الاسلامي",
    "Sharp333", "شارب333",
    "APT IRAN",
    # Generic hacktivist search terms
    "هاكرز المقاومة",
    "اختراق الاردن",
    "اختراق اسرائيل",
    "عمليات سيبرانية",
    "غرفة العمليات الالكترونية",
    "محور المقاومة السيبرانية",
]

# Keywords to score channel relevance (how likely it targets Jordan/regional infra)
RELEVANCE_KEYWORDS = [
    # Attack language
    "ddos", "defacement", "breach", "hack", "اختراق", "تسريب",
    "wiper", "exploit", "vulnerability", "ثغرة", "leak", "dump",
    # Jordan-specific targets (higher score = more relevant to us)
    "jordan", "الاردن", "الأردن", "اردن", ".jo", ".gov.jo",
    "arab bank", "البنك العربي", "bank of jordan", "بنك الأردن",
    "housing bank", "بنك الإسكان", "jopacc", "cbj", "البنك المركزي",
    "ministry", "وزارة", "الديوان الملكي", "royal court",
    "استهداف الأردن", "الجيش الأردني", "الحكومة الأردنية",
    # Israel / regional (indicates threat actor orientation)
    "israel", "اسرائيل", "zionist", "صهيوني", "الاحتلال",
    "gulf", "خليج", "saudi", "السعودية",
    "free palestine", "فلسطين", "الاقصى", "غزة",
    # Ideology markers
    "resistance", "مقاومة", "islamic", "اسلامي",
    "khamenei", "خامنئي", "soleimani", "سليماني",
    "true promise", "الوعد الصادق", "محور المقاومة",
    # Operation language
    "operation", "عملية", "target", "هدف",
    # Group names (self-referential in about text)
    "313", "fatimion", "فاطميون", "handala", "حندلة",
    "keymous", "كيموس", "dienet", "lulzsec", "ripper",
]

# Known channel IDs (survive username changes)
KNOWN_CHANNEL_IDS = [
    2250158203,   # 313 Team (xX313XxTeam)
    1233310276,   # 313 Team Official
    2214615288,   # 313 Team Leak
    2227640343,   # 313 Team Backup
    1970086460,   # Fatemiyoun (hak994)
    3148465603,   # Fatemiyoun (hak993)
    2468283118,   # Keymous+ (KeymousTeam)
    3325520970,   # DieNet API Information
]


# ==============================================================================
# DISCOVERY ENGINE
# ==============================================================================

class ChannelDiscovery:
    def __init__(self):
        self.client = TelegramClient("jordan_discovery", int(API_ID), API_HASH)
        self.discovered  = {}
        self.checked_ids = set()

    async def _safe(self, coro):
        try:
            return await coro
        except FloodWaitError as e:
            log.warning(f"Rate limited, waiting {e.seconds}s...")
            await asyncio.sleep(e.seconds + 1)
            try:
                return await coro
            except Exception as e2:
                log.warning(f"Retry failed: {e2}")
                return None
        except (ChannelPrivateError, UsernameNotOccupiedError):
            return None
        except Exception as e:
            log.warning(f"API error: {e}")
            return None

    async def _join_seeds(self):
        """Join all known seed channels so we can read their history."""
        log.info("SEED JOIN: attempting to join known channels...")
        joined, failed = 0, 0
        seeds = list(dict.fromkeys(
            ["hak993", "hak994", "xX313XxTeam", "Team313Official",
             "x313xTeamLeak", "x313xTeamBackup", "KeymousTeam",
             "LulzSecBlack", "handal_a", "dienet3",
             "noname05716eng", "noname05716", "RipperSec", "TheRipperSec",
             "AnonGhostOfficialTeam", "sylhetgangsgofficial",
             "KMPteam", "Keymous_V2", "blackopmrhamza",
             "Mhwear98", "Mhwercyber4", "fattahh_ir",
             "Handala_hack", "handala_hack26"]
        ))
        for uname in seeds:
            try:
                entity = await self.client.get_entity(uname)
                try:
                    await self.client(JoinChannelRequest(entity))
                    log.info(f"  Joined: @{uname}")
                except Exception:
                    pass  # already member or join not needed
                self._record(entity, source="seed")
                joined += 1
            except Exception as e:
                log.warning(f"  Cannot access @{uname}: {e}")
                failed += 1
            await asyncio.sleep(1)
        log.info(f"SEED JOIN complete: {joined} joined/accessible, {failed} unreachable")

    def _score(self, title, about, username):
        text = f"{title} {about} {username}".lower()
        score, matches = 0, []
        for kw in RELEVANCE_KEYWORDS:
            if kw.lower() in text:
                score += 1
                matches.append(kw)
        return score, matches

    def _record(self, entity, source="search"):
        username   = getattr(entity, 'username', None)
        title      = getattr(entity, 'title', getattr(entity, 'first_name', 'unknown'))
        channel_id = entity.id
        about      = getattr(entity, 'about', '') or ''

        if channel_id in self.checked_ids:
            return
        self.checked_ids.add(channel_id)

        score, matches = self._score(title, about, username or '')
        info = {
            "id": channel_id,
            "username": username,
            "title": title,
            "about": about[:200] if about else "",
            "score": score,
            "relevance_matches": matches,
            "source": source,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }

        key = username if username else f"id_{channel_id}"
        self.discovered[key] = info

        with open(DISCOVERY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(info, ensure_ascii=False, default=str) + "\n")

        if score >= 2:
            log.info(f"FOUND [{score}★] @{username or channel_id} - {title} | {matches[:3]} | via: {source}")
        else:
            log.debug(f"Low [{score}★] @{username or channel_id} - {title}")

        return info

    # ── Method 1: Global Search ──
    async def search_global(self):
        log.info("METHOD 1: Global Telegram Search")
        for term in GROUP_SEARCH_TERMS:
            log.info(f"  Searching: {term}")
            try:
                result = await self._safe(self.client(SearchGlobalRequest(
                    q=term, filter=types.InputMessagesFilterEmpty(),
                    min_date=None, max_date=None, offset_rate=0,
                    offset_peer=types.InputPeerEmpty(), offset_id=0, limit=20
                )))
                if result and hasattr(result, 'chats'):
                    for chat in result.chats:
                        self._record(chat, source=f"global:{term}")
                await asyncio.sleep(2)
            except Exception as e:
                log.warning(f"Search error '{term}': {e}")
                await asyncio.sleep(3)

    # ── Method 2: Contact Search ──
    async def search_contacts(self):
        log.info("METHOD 2: Contact Search")
        for term in GROUP_SEARCH_TERMS:
            try:
                result = await self._safe(self.client(SearchRequest(q=term, limit=20)))
                if result:
                    for chat in getattr(result, 'chats', []):
                        self._record(chat, source=f"contact:{term}")
                await asyncio.sleep(2)
            except Exception as e:
                log.warning(f"Contact search error '{term}': {e}")
                await asyncio.sleep(3)

    # ── Method 3: Cross-Post Analysis (most reliable) ──
    async def follow_crossposts(self):
        log.info("METHOD 3: Cross-Post Analysis (forwarded messages / mentions)")
        active = []
        for cid in KNOWN_CHANNEL_IDS:
            try:
                active.append(await self.client.get_entity(cid))
            except Exception:
                pass
        for uname in ["hak993","hak994","xX313XxTeam","Team313Official",
                      "x313xTeamLeak","x313xTeamBackup","KeymousTeam",
                      "LulzSecBlack","handal_a","dienet3"]:
            try:
                e = await self.client.get_entity(uname)
                if e.id not in [x.id for x in active]:
                    active.append(e)
            except Exception:
                pass

        for channel in active:
            title = getattr(channel, 'title', str(channel.id))
            log.info(f"  Scanning: {title}")
            try:
                messages = await self.client(GetHistoryRequest(
                    peer=channel, offset_id=0, offset_date=None,
                    add_offset=0, limit=200, max_id=0, min_id=0, hash=0
                ))
                fwd_seen, mention_seen = set(), set()
                for msg in messages.messages:
                    if msg.fwd_from and hasattr(msg.fwd_from, 'from_id') and msg.fwd_from.from_id:
                        fwd_id = getattr(msg.fwd_from.from_id, 'channel_id', None)
                        if fwd_id and fwd_id not in fwd_seen:
                            fwd_seen.add(fwd_id)
                            try:
                                self._record(await self.client.get_entity(fwd_id), f"fwd_from:{title}")
                            except Exception:
                                pass
                    if msg.message:
                        for uname in re.findall(r'@([a-zA-Z][\w\d]{3,30}[a-zA-Z\d])', msg.message):
                            if uname not in mention_seen:
                                mention_seen.add(uname)
                                try:
                                    self._record(await self.client.get_entity(uname), f"mention_in:{title}")
                                except Exception:
                                    pass
                        for uname in re.findall(r't\.me/([a-zA-Z][\w\d]{3,30})', msg.message):
                            if uname not in mention_seen and uname != "joinchat":
                                mention_seen.add(uname)
                                try:
                                    self._record(await self.client.get_entity(uname), f"tme_in:{title}")
                                except Exception:
                                    pass
                        for inv in re.findall(r't\.me/\+([a-zA-Z0-9_-]+)', msg.message):
                            log.info(f"  Invite link in {title}: t.me/+{inv}")
                await asyncio.sleep(1)
            except Exception as e:
                log.warning(f"Error scanning {title}: {e}")

    # ── Method 4: Known ID Resolution ──
    async def resolve_known_ids(self):
        log.info("METHOD 4: Known ID Resolution")
        all_ids = list(KNOWN_CHANNEL_IDS)
        if DISCOVERY_LOG.exists():
            with open(DISCOVERY_LOG, encoding="utf-8") as f:
                for line in f:
                    try:
                        cid = json.loads(line).get("id")
                        if cid and cid not in all_ids:
                            all_ids.append(cid)
                    except Exception:
                        pass
        for cid in all_ids:
            try:
                entity = await self.client.get_entity(cid)
                log.info(f"  ID {cid} -> @{getattr(entity,'username',None)} ({getattr(entity,'title','?')})")
                self._record(entity, "id_resolution")
            except Exception as e:
                log.debug(f"  ID {cid} unreachable: {e}")
            await asyncio.sleep(0.5)

    # ── Method 5: Linked Channels ──
    async def check_linked(self):
        log.info("METHOD 5: Linked/Similar Channels")
        for username, info in list(self.discovered.items()):
            if (info.get("score") or 0) < 2:
                continue
            try:
                entity = await self.client.get_entity(info.get("username") or info.get("id"))
                full   = await self.client(functions.channels.GetFullChannelRequest(entity))
                if hasattr(full, 'full_chat'):
                    fc = full.full_chat
                    if getattr(fc, 'linked_chat_id', None):
                        try:
                            linked = await self.client.get_entity(fc.linked_chat_id)
                            self._record(linked, f"linked_to:{username}")
                        except Exception:
                            pass
                await asyncio.sleep(1)
            except Exception as e:
                log.debug(f"Error checking links for {username}: {e}")

    # ── Report & Export ──
    def generate_report(self):
        sorted_ch = sorted(self.discovered.values(), key=lambda x: x.get("score", 0), reverse=True)
        high = [c for c in sorted_ch if c.get("score", 0) >= 3]
        med  = [c for c in sorted_ch if 1 <= c.get("score", 0) < 3]

        log.info(f"\nTotal discovered: {len(sorted_ch)} | High: {len(high)} | Medium: {len(med)}")
        for ch in high:
            uname = ch.get("username") or f"ID:{ch.get('id')}"
            log.info(f"  [{ch['score']}★] @{uname} - {ch['title']}")
            log.info(f"       Matches: {ch.get('relevance_matches', [])}")

        watchlist_usernames = [c["username"] for c in sorted_ch if c.get("score",0) >= 2 and c.get("username")]
        watchlist = {
            "generated_at":          datetime.now(timezone.utc).isoformat(),
            "channels_by_username":  watchlist_usernames,
            "channels_by_id":        [c["id"] for c in sorted_ch if c.get("score",0) >= 2 and not c.get("username")],
            "all_discovered":        sorted_ch,
        }
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2, default=str)

        log.info(f"\nWatchlist saved: {WATCHLIST_FILE}")
        if watchlist_usernames:
            log.info("\nCOPY-PASTE into telegram_monitor.py WATCHLIST:")
            for u in watchlist_usernames:
                log.info(f'    "{u}",')

        return watchlist

    def _write_pending(self, min_score=3):
        """Push high-relevance discovered channels to PENDING_FILE for the monitor."""
        candidates = [
            c["username"] for c in self.discovered.values()
            if c.get("score", 0) >= min_score and c.get("username")
        ]
        if not candidates:
            return

        # Merge with whatever is already pending
        existing = {}
        if PENDING_FILE.exists():
            try:
                with open(PENDING_FILE, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        already_pending   = set(existing.get("pending",   []))
        already_processed = set(existing.get("processed", []))
        new_channels = [c for c in candidates
                        if c not in already_pending and c not in already_processed]

        if new_channels:
            existing["pending"]    = list(already_pending | set(new_channels))
            existing["processed"]  = list(already_processed)
            existing["updated_at"] = datetime.now(timezone.utc).isoformat()
            with open(PENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            log.info(f"PENDING: added {len(new_channels)} new channels → {PENDING_FILE}")
            for c in new_channels:
                log.info(f"  → @{c}")

    async def run(self, quick=False):
        log.info(f"TELEGRAM CHANNEL DISCOVERY - {'QUICK' if quick else 'FULL'} MODE")
        await self.client.start(phone=PHONE)
        await self._join_seeds()          # join seed channels first so we can read them
        await self.resolve_known_ids()
        await self.follow_crossposts()
        if not quick:
            await self.search_global()
            await self.search_contacts()
            await self.check_linked()
        watchlist = self.generate_report()
        self._write_pending()
        await self.client.disconnect()
        return watchlist

    async def run_daemon(self, interval_hours=8, quick=False):
        """Run discovery scans in a loop, writing new channels to pending_channels.json."""
        log.info(f"DISCOVERY DAEMON - scanning every {interval_hours}h ({'quick' if quick else 'full'} mode)")
        await self.client.start(phone=PHONE)
        await self._join_seeds()          # join seeds once on startup
        while True:
            scan_start = datetime.now(timezone.utc)
            log.info(f"DAEMON SCAN starting at {scan_start.isoformat()}")
            self.discovered.clear()
            self.checked_ids.clear()
            await self.resolve_known_ids()
            await self.follow_crossposts()
            if not quick:
                await self.search_global()
                await self.search_contacts()
                await self.check_linked()
            self.generate_report()
            self._write_pending()
            log.info(f"DAEMON SCAN complete. Next scan in {interval_hours}h")
            await asyncio.sleep(interval_hours * 3600)


# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    import sys
    if "--export" in sys.argv:
        if WATCHLIST_FILE.exists():
            with open(WATCHLIST_FILE) as f:
                wl = json.load(f)
            print("\n# Auto-discovered channels - paste into telegram_monitor.py WATCHLIST")
            for u in wl.get("channels_by_username", []):
                print(f'    "{u}",')
        else:
            print("No watchlist found. Run discovery first.")
    elif "--daemon" in sys.argv:
        # Parse optional --interval N (hours, default 8)
        interval = 8
        if "--interval" in sys.argv:
            idx = sys.argv.index("--interval")
            if idx + 1 < len(sys.argv):
                try:
                    interval = int(sys.argv[idx + 1])
                except ValueError:
                    pass
        asyncio.run(ChannelDiscovery().run_daemon(interval_hours=interval, quick="--quick" in sys.argv))
    else:
        asyncio.run(ChannelDiscovery().run(quick="--quick" in sys.argv))
