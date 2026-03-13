"""
Generate a genericized IOC Intelligence Report PDF matching the original styling.
All specific company names, bank names, and environment-specific findings removed.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.lib.pagesizes import letter
import os

# Colors matching the original dark/military style
DARK_BG = HexColor("#1a1a2e")
HEADER_BG = HexColor("#16213e")
ACCENT = HexColor("#0f3460")
CRITICAL_RED = HexColor("#c0392b")
HIGH_ORANGE = HexColor("#e67e22")
MEDIUM_YELLOW = HexColor("#f39c12")
TABLE_HEADER_BG = HexColor("#1a1a2e")
TABLE_ALT_ROW = HexColor("#f0f0f5")
TABLE_BORDER = HexColor("#2c3e50")
LIGHT_GRAY = HexColor("#ecf0f1")
TEXT_DARK = HexColor("#2c3e50")
SECTION_BG = HexColor("#1a1a2e")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "ScanWave_Generic_IOC_Intelligence_Report.pdf")

def build_report():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    W = doc.width

    # Custom styles
    s_header_bar = ParagraphStyle(
        "HeaderBar", parent=styles["Normal"],
        fontSize=7, textColor=HexColor("#666666"), alignment=TA_CENTER,
        spaceAfter=2,
    )
    s_title = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=26, textColor=DARK_BG, alignment=TA_CENTER,
        spaceAfter=6, spaceBefore=40, fontName="Helvetica-Bold",
    )
    s_subtitle = ParagraphStyle(
        "SubTitle", parent=styles["Normal"],
        fontSize=14, textColor=ACCENT, alignment=TA_CENTER,
        spaceAfter=4, fontName="Helvetica",
    )
    s_cover_detail = ParagraphStyle(
        "CoverDetail", parent=styles["Normal"],
        fontSize=10, textColor=HexColor("#555555"), alignment=TA_CENTER,
        spaceAfter=2,
    )
    s_confidential = ParagraphStyle(
        "Confidential", parent=styles["Normal"],
        fontSize=11, textColor=CRITICAL_RED, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceBefore=20, spaceAfter=4,
    )
    s_section = ParagraphStyle(
        "SectionHead", parent=styles["Heading1"],
        fontSize=14, textColor=white, fontName="Helvetica-Bold",
        spaceBefore=18, spaceAfter=8, backColor=DARK_BG,
        borderPadding=(6, 8, 6, 8), leading=20,
    )
    s_subsection = ParagraphStyle(
        "SubSection", parent=styles["Heading2"],
        fontSize=11, textColor=ACCENT, fontName="Helvetica-Bold",
        spaceBefore=12, spaceAfter=6, borderWidth=0,
        borderColor=ACCENT, borderPadding=(0,0,2,0),
    )
    s_body = ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=9, textColor=TEXT_DARK, alignment=TA_JUSTIFY,
        spaceAfter=6, leading=13, fontName="Helvetica",
    )
    s_body_bold = ParagraphStyle(
        "BodyBold", parent=s_body, fontName="Helvetica-Bold",
    )
    s_bullet = ParagraphStyle(
        "BulletItem", parent=s_body,
        leftIndent=18, bulletIndent=6, spaceBefore=2, spaceAfter=2,
    )
    s_finding_box = ParagraphStyle(
        "FindingBox", parent=s_body,
        backColor=HexColor("#fdf2e9"), borderColor=HIGH_ORANGE,
        borderWidth=1, borderPadding=(8,8,8,8),
        spaceBefore=8, spaceAfter=8, fontName="Helvetica-Bold",
        fontSize=9,
    )
    s_small = ParagraphStyle(
        "SmallText", parent=styles["Normal"],
        fontSize=7, textColor=HexColor("#999999"),
    )

    def make_table(headers, rows, col_widths=None):
        data = [headers] + rows
        if col_widths is None:
            col_widths = [W / len(headers)] * len(headers)
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))
        t.setStyle(TableStyle(style_cmds))
        return t

    def sev_color(text):
        t = text.upper()
        if "CRITICAL" in t:
            return f'<font color="#c0392b"><b>{text}</b></font>'
        elif "HIGH" in t:
            return f'<font color="#e67e22"><b>{text}</b></font>'
        elif "MEDIUM" in t:
            return f'<font color="#f39c12"><b>{text}</b></font>'
        elif "CONFIRMED" in t:
            return f'<font color="#c0392b"><b>{text}</b></font>'
        return text

    story = []

    # ── HEADER BAR (every page will have this via the template, but add to cover) ──
    story.append(Paragraph(
        "ScanWave  |  IOC Intelligence Report  |  March 2026", s_header_bar
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc")))
    story.append(Spacer(1, 8))
    story.append(Paragraph("CONFIDENTIAL", s_confidential))

    # ── COVER PAGE ──
    story.append(Spacer(1, 60))
    story.append(Paragraph("ScanWave", ParagraphStyle(
        "Brand", parent=s_title, fontSize=16, textColor=ACCENT, spaceAfter=2, spaceBefore=0,
    )))
    story.append(Paragraph("IOC INTELLIGENCE REPORT", s_title))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Threat Intelligence Report — Financial &amp; Energy Sector Targeting", s_subtitle
    ))
    story.append(Paragraph("March 2026", s_cover_detail))
    story.append(Spacer(1, 30))
    story.append(Paragraph("CONFIDENTIAL", s_confidential))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Prepared by ScanWave Security Operations Center", s_cover_detail
    ))
    story.append(Paragraph(
        "platform.scanwave.io  ·  soc@scanwave.io", s_cover_detail
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("1. EXECUTIVE SUMMARY", s_section))
    story.append(Paragraph(
        "A threat actor with suspected Iranian-nexus affiliations has claimed successful compromise of a "
        "major financial institution operating in the Middle East region. The threat communique, published "
        "in Farsi, details a multi-stage intrusion that leveraged a compromised third-party management "
        "system deployed within the target country to gain persistent backdoor access to the organization's "
        "core server infrastructure.",
        s_body
    ))
    story.append(Paragraph(
        "The actor claims persistent access to the target's technical infrastructure, asserting that "
        "defensive measures undertaken by the security team — including port blocking and access "
        "restriction — were ineffective. Evidence provided as proof-of-compromise includes live server "
        "monitoring dashboards and an industrial energy SCADA/ICS panel showing grid-disconnected "
        "inverters in a national economic zone.",
        s_body
    ))
    story.append(Paragraph(
        "The initial access vector is attributed to a third-party contractor responsible for deploying a "
        "management system in the target country, which inadvertently introduced multiple backdoor access "
        "points to the organization's core servers. This represents a classic supply chain compromise with "
        "significant implications for both the financial services and energy sectors.",
        s_body
    ))
    story.append(Paragraph(
        "Threat intelligence correlation suggests possible links to the Handala Hack Team (suspected "
        "MOIS-linked), a suspected Iranian state-sponsored group conducting Operation HamsaUpdate — a "
        "destructive wiper campaign targeting energy and financial sectors across the Middle East region. "
        "A regional energy provider was previously breached by Handala (listed as \"BLEnergy\" on 2024-07-23), "
        "establishing a pattern of repeated targeting.",
        s_body
    ))
    story.append(Paragraph(
        "INVESTIGATION FINDING: A comprehensive investigation was conducted across the targeted "
        "organization's environment. No evidence of compromise via the claimed SCADA/solar attack vector "
        "was found on currently connected SOC scope. However, active external reconnaissance against "
        "the organization's web assets, SIP brute-force attacks against branch VoIP infrastructure, and a "
        "complete telemetry blind spot on the alleged attack surface (solar/SCADA systems) were identified.",
        s_finding_box
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 2. SUSPECTED THREAT ACTOR PROFILE
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("2. SUSPECTED THREAT ACTOR PROFILE", s_section))
    ta_table = make_table(
        ["Attribute", "Detail"],
        [
            ["Designation", "Handala Hack Team (a.k.a. Handala, Hanzala)"],
            ["Tracked As", "UNK-IR-SECTOR-0307 / Handala Hack Team"],
            ["State Affiliation", "Iran — Ministry of Intelligence and Security (MOIS)"],
            ["Assessed Origin", "Iran (Farsi-language communique)"],
            ["Motivation", "Geopolitical / Hacktivism / Destructive (wiper deployment)"],
            ["Sophistication", "Moderate-to-High (supply chain exploitation, wiper malware, SCADA access)"],
            ["Target Profile", "Middle Eastern financial institutions, energy/solar infrastructure, regional targets"],
            ["Active Operations", "Operation HamsaUpdate (wiper campaign), RedAlert fake app, energy provider breach"],
            ["Language", "Farsi (Persian) — operational communique"],
            ["Leak Sites", "handala-hack.to (clearnet, DDoS-Guard) / .onion Tor site (NGINX)"],
            ["Total Known Victims", "137 (as of 2026-03-07) | Last victim posted: 2026-03-07"],
            ["Status", "ACTIVE — Claims ongoing access"],
        ],
        col_widths=[1.6*inch, W - 1.6*inch]
    )
    story.append(ta_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "The threat actor's communique was authored entirely in Farsi, which combined with the targeting "
        "pattern (Middle Eastern financial infrastructure) and the parallel SCADA/ICS compromise is consistent "
        "with suspected Iranian-nexus cyber operations. The targeting of solar energy infrastructure in a "
        "national economic zone aligns with known Iranian interest in disrupting regional critical infrastructure.",
        s_body
    ))

    # 2.1 Recent Victims
    story.append(Paragraph("2.1 Handala Recent Victims (March 2026 Campaign)", s_subsection))
    story.append(Paragraph(
        "The following victims were posted by Handala in the same campaign wave:",
        s_body
    ))
    victims_table = make_table(
        ["Victim Sector", "Date", "Industry", "Relevance"],
        [
            ["Regional Energy Provider (as \"BLEnergy\")", "2024-07-23", "Energy / Solar", "PRIOR breach of same target"],
            ["Energy Company — Middle East", "2026-03-02", "Energy", "Same campaign wave"],
            ["Oil & Gas Corporation — Gulf Region", "2026-03-03", "Energy / Oil & Gas", "Same campaign wave"],
            ["National Oil Corporation — Gulf Region", "2026-03-03", "Energy / Oil & Gas", "Same campaign wave"],
            ["Government Research Institute", "2026-03-04", "Government / Think Tank", "Same campaign wave"],
            ["Regional Insurance Provider", "2026-03-05", "Financial / Insurance", "Same campaign wave"],
            ["Healthcare Organization", "2026-02-25", "Healthcare", "Same campaign wave"],
        ],
        col_widths=[2.2*inch, 0.9*inch, 1.3*inch, W - 4.4*inch]
    )
    story.append(victims_table)

    # 2.2 Online Presence
    story.append(Paragraph("2.2 Handala Online Presence", s_subsection))
    presence_table = make_table(
        ["Platform", "Identifier", "Status"],
        [
            ["Twitter/X", "@Handala_news", "Active"],
            ["Forum", "BreachForums", "Active account"],
            ["Forum", "Ramp / Exploit", "Active accounts"],
            ["Comms", "Tox / ProtonMail", "Secure communication channels"],
        ],
        col_widths=[1.4*inch, 2.2*inch, W - 3.6*inch]
    )
    story.append(presence_table)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 3. ATTACK NARRATIVE & TIMELINE
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("3. ATTACK NARRATIVE &amp; TIMELINE", s_section))
    phases = [
        ("Phase 1 — Initial Access (Supply Chain Compromise):",
         "The threat actor exploited a management system deployed by a third-party contractor operating within "
         "the target country. This system contained inherent vulnerabilities that created multiple unintended "
         "backdoor access points to the targeted organization's core server infrastructure. Handala's known TTPs "
         "include spear-phishing with fake F5 BIG-IP update notifications and RedAlert app updates, delivering "
         ".NET loaders (F5UPDATER.exe)."),
        ("Phase 2 — Persistence &amp; Lateral Movement:",
         "Upon gaining initial access, the actor established persistent footholds across multiple segments of "
         "the organization's technical infrastructure. The communique explicitly states that the security team's "
         "efforts to block ports and restrict access were unsuccessful in dislodging the adversary. Handala's "
         "Operation HamsaUpdate deploys second-stage loaders (Handala.exe) and uses AutoIt-based shellcode injection."),
        ("Phase 3 — Active Surveillance &amp; Exfiltration:",
         "Handala's known exfiltration methods include AWS S3, and Storj decentralized storage."),
        ("Phase 4 — Parallel Infrastructure Attack (SCADA/ICS):",
         "Evidence from the posted materials indicates compromise of a solar energy monitoring system in a "
         "national economic zone. All five solar inverters (INV/1 through INV/5) were observed in an OFF state "
         "with \"Grid Loss\" status, suggesting deliberate grid disconnection or manipulation of the solar energy "
         "control systems. The affected energy provider operates multiple solar plants in the region (~100 MW total)."),
        ("Phase 5 — Wiper Deployment (Assessed):",
         "Based on Handala's known TTPs from Operation HamsaUpdate, destructive wiper payloads (Hatef.exe for "
         "Windows, update.sh/Hamsa for Linux) may have been staged or deployed. These wipers perform disk structure "
         "wipe (T1561.002) and use BYOVD privilege escalation via vulnerable drivers (ListOpenedFileDrv_32.sys)."),
    ]
    for title, text in phases:
        story.append(Paragraph(f"<b>{title}</b> {text}", s_body))
    story.append(Paragraph(
        "Observed Timestamp: 2024-01-28 08:47:09 UTC (from energy provider dashboard). Environmental data "
        "anomalies (ambient temperature reading of -40°C) suggest possible sensor manipulation or system "
        "compromise affecting telemetry integrity.",
        s_body
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 4. RISK ASSESSMENT MATRIX
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("4. RISK ASSESSMENT MATRIX", s_section))
    risk_table = make_table(
        ["Category", "Rating", "Justification"],
        [
            ["Confidentiality Impact", "HIGH", "Potential access to core financial systems, customer data exposure"],
            ["Integrity Impact", "CRITICAL", "Wiper malware (Hatef.exe) designed to destroy disk structures; server manipulation"],
            ["Availability Impact", "CRITICAL", "Solar grid disconnection confirmed; wiper deployment destroys systems permanently"],
            ["Overall Risk Rating", "CRITICAL", "Active nation-state/hacktivist intrusion with destructive capability into critical infrastructure"],
        ],
        col_widths=[1.5*inch, 0.8*inch, W - 2.3*inch]
    )
    story.append(risk_table)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 5. INDICATORS OF COMPROMISE (IOCs)
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("5. INDICATORS OF COMPROMISE (IOCs)", s_section))
    story.append(Paragraph(
        "The following IOCs have been extracted from the threat actor's communique, associated infrastructure "
        "analysis, and Handala Hack Team threat intelligence. All network indicators are presented in defanged format.",
        s_body
    ))

    # 5.1 Network Indicators
    story.append(Paragraph("5.1 Network Indicators", s_subsection))
    net_table = make_table(
        ["Type", "Indicator", "Context", "Confidence"],
        [
            ["IP (C2)", "31.192.237[.]207", "Handala C2 server (port 2515/HTTPS) — Chelyabinsk, Russia", "CRITICAL"],
            ["IP", "38.180.239[.]161", "Associated threat infrastructure", "HIGH"],
            ["IP", "209.74.87[.]100", "Associated threat infrastructure", "HIGH"],
            ["IP", "157.20.182[.]49", "Associated threat infrastructure", "HIGH"],
            ["IP", "185.236.25[.]11", "Associated threat infrastructure", "HIGH"],
            ["IP", "92.243.65[.]243", "Associated threat infrastructure", "HIGH"],
            ["IP Range", "185.173.35[.]0/24", "Suspected C2 infrastructure", "HIGH"],
            ["IP Range", "91.243.44[.]0/24", "SCADA/ICS callback range", "MEDIUM"],
            ["Port", "TCP/2515", "Handala C2 communication port (HTTPS)", "CRITICAL"],
            ["Port", "TCP/4443", "Non-standard HTTPS backdoor", "HIGH"],
            ["Port", "TCP/8443", "Management interface backdoor", "HIGH"],
            ["Port", "TCP/9090", "Web management console", "MEDIUM"],
        ],
        col_widths=[0.7*inch, 1.6*inch, 2.8*inch, 0.9*inch]
    )
    story.append(net_table)

    # 5.2 Infrastructure & System Indicators
    story.append(Paragraph("5.2 Infrastructure &amp; System Indicators", s_subsection))
    infra_table = make_table(
        ["Type", "Indicator", "Context", "Confidence"],
        [
            ["Platform", "Solar Energy Monitoring System", "Compromised SCADA/ICS panel", "CONFIRMED"],
            ["System", "Solar Inverters INV/1–INV/5", "Grid-disconnected (OFF state)", "CONFIRMED"],
            ["Timestamp", "2024-01-28T08:47:09Z", "Observed compromise timestamp", "CONFIRMED"],
            ["Location", "National Economic Zone", "Solar farm geographic target", "CONFIRMED"],
            ["System", "Core Server Dashboard", "Live server monitoring claimed", "HIGH"],
            ["Vector", "Third-party management system", "Initial access vector (contractor)", "HIGH"],
            ["Prior Breach", "Regional Energy Provider (\"BLEnergy\")", "Handala victim 2024-07-23", "CONFIRMED"],
        ],
        col_widths=[0.8*inch, 1.8*inch, 2.2*inch, 1.0*inch]
    )
    story.append(infra_table)

    # 5.3 Behavioral Indicators
    story.append(Paragraph("5.3 Behavioral Indicators (TTPs)", s_subsection))
    ttp_table = make_table(
        ["Type", "Indicator", "Context", "Confidence"],
        [
            ["TTP", "Contractor supply chain compromise", "Third-party management platform", "HIGH"],
            ["TTP", "Persistent backdoor implantation", "Multiple access points on core servers", "HIGH"],
            ["TTP", "Live server monitoring capture", "Real-time surveillance of target", "CONFIRMED"],
            ["TTP", "Firewall/port restriction bypass", "Evading defensive countermeasures", "HIGH"],
            ["TTP", "SCADA/ICS manipulation", "Solar inverter grid disconnect", "CONFIRMED"],
            ["TTP", "Farsi-language threat communique", "Iranian-nexus attribution indicator", "MEDIUM"],
            ["TTP", "BYOVD privilege escalation", "ListOpenedFileDrv_32.sys vulnerable driver", "HIGH"],
            ["TTP", "Messaging platform C2 exfiltration", "Bot token + chat ID for data theft", "HIGH"],
        ],
        col_widths=[0.6*inch, 2.0*inch, 2.2*inch, 1.0*inch]
    )
    story.append(ttp_table)
    story.append(PageBreak())

    # 5.4 Malicious URLs & Payloads
    story.append(Paragraph("5.4 Malicious URLs &amp; Payloads", s_subsection))
    url_table = make_table(
        ["Type", "Indicator", "Context", "Confidence"],
        [
            ["URL", "hxxps://www[.]shirideitch[.]com/wp-content/uploads/2022/06/RedAlert.apk", "Malicious Android APK (RedAlert trojan)", "HIGH"],
            ["URL", "hxxps://api[.]ra-backup[.]com/analytics/submit.php", "C2 callback / data exfiltration endpoint", "HIGH"],
            ["URL", "hxxps://bit[.]ly/4tWJhQh", "Shortened URL — suspected phishing/malware delivery", "HIGH"],
            ["URL", "hxxps://sjc1[.]vultrobjects[.]com/f5update/update.sh", "Linux wiper (Hamsa) download URL", "CRITICAL"],
            ["URL", "hxxp://38[.]180[.]239[.]161", "Threat infrastructure — HTTP endpoint", "HIGH"],
            ["URL", "hxxps://web27[.]info/0d894cce589ccd44", "Suspected malware staging / phishing", "HIGH"],
            ["URL", "hxxps://web27[.]info/b4cac8a7128d6507", "Suspected malware staging / phishing", "HIGH"],
            ["URL", "hxxps://web27[.]info/772b49c3c513b961", "Suspected malware staging / phishing", "HIGH"],
            ["URL", "hxxps://web27[.]info/b4f44ec4db01887aHOR", "Suspected malware staging / phishing", "HIGH"],
            ["URL", "hxxps://web27[.]info/ec714d155863dcd6", "Suspected malware staging / phishing", "HIGH"],
        ],
        col_widths=[0.5*inch, 3.0*inch, 1.8*inch, 0.8*inch]
    )
    story.append(url_table)

    # 5.5 Malicious Domains
    story.append(Paragraph("5.5 Malicious Domains", s_subsection))
    domain_table = make_table(
        ["Domain", "Context", "Action", "Confidence"],
        [
            ["api[.]ra-backup[.]com", "C2 callback domain — RedAlert fake app analytics endpoint", "BLOCK", "CRITICAL"],
            ["shirideitch[.]com", "Phishing delivery domain — hosts malicious RedAlert APK", "BLOCK", "HIGH"],
            ["sjc1[.]vultrobjects[.]com", "Vultr object storage — hosts Linux wiper payload", "BLOCK", "CRITICAL"],
            ["web27[.]info", "Suspected malware staging / phishing infrastructure", "BLOCK", "HIGH"],
            ["handala[.]to", "Handala clearnet leak site (unavailable since 2025-06-26)", "BLOCK", "HIGH"],
            ["handala-hack[.]to", "Handala clearnet leak site (active, DDoS-Guard hosted)", "BLOCK", "HIGH"],
        ],
        col_widths=[1.6*inch, 2.8*inch, 0.6*inch, 0.8*inch]
    )
    story.append(domain_table)

    # 5.6 Handala C2 Infrastructure
    story.append(Paragraph("5.6 Handala C2 Infrastructure", s_subsection))
    c2_table = make_table(
        ["Type", "Indicator", "Context", "Severity"],
        [
            ["C2 Server", "31.192.237[.]207:2515/HTTPS", "Primary wiper C2 — Chelyabinsk, Russia", "CRITICAL"],
            ["Tor Leak Site", "vmjfieomxhnfjba57sd6jjws2ogvowjgxhhfglsikqvvrnrajbmpxqqd.onion", "Handala Tor leak site (NGINX)", "HIGH"],
        ],
        col_widths=[0.8*inch, 3.0*inch, 1.6*inch, 0.8*inch]
    )
    story.append(c2_table)
    story.append(PageBreak())

    # 5.7 Malware Hashes
    story.append(Paragraph("5.7 Malware Hashes (SHA256)", s_subsection))
    story.append(Paragraph(
        "Windows wiper campaign, Operation HamsaUpdate, and RedAlert fake app malware samples:",
        s_body
    ))
    hash_table = make_table(
        ["SHA256", "Filename / Description", "Type", "Severity"],
        [
            ["96dec6e07229...dcbc8", "update.zip — Phishing delivery archive", "Dropper", "CRITICAL"],
            ["19001dd441e5...c634f0", "Phishing attachment PDF — initial lure", "Lure", "CRITICAL"],
            ["8316065c4536...e4d67", "OpenFileFinder.dll — wiper component", "Wiper DLL", "CRITICAL"],
            ["9e519211947c...b961", "Wiper variant sample", "Wiper", "CRITICAL"],
            ["fe07dca68f28...e30bd2", "F5UPDATER.exe — .NET loader variant 1 (signed)", "Loader", "CRITICAL"],
            ["ca9bf13897af...d0d74a", "F5UPDATER.exe — .NET loader variant 2 (signed)", "Loader", "CRITICAL"],
            ["e28085e8d64b...3af35", "Hatef.exe — Windows wiper malware", "Wiper", "CRITICAL"],
            ["454e6d3782f2...9567", "Handala.exe — Delphi second-stage loader", "Loader", "CRITICAL"],
            ["6f79c0e0e1aa...b840ad", "update.sh — Linux wiper (Hamsa) encrypted", "Wiper", "CRITICAL"],
            ["ad66251d9e87...166e8a", "ZIP archive — loader + Hatef wiper", "Archive", "CRITICAL"],
            ["64c5fd791ee3...5428c", "ZIP archive — loader + Handala loader", "Archive", "CRITICAL"],
            ["336167b8c5cf...b2767", "FlashDevelop — third-stage payload", "Payload", "CRITICAL"],
            ["f58d3a4b2f3f...efbd3", "Naples.pif — renamed AutoIt interpreter", "Evasion", "HIGH"],
            ["aae989743ddd...8acd4", "Obfuscated AutoIt script — shellcode injector", "Injector", "CRITICAL"],
            ["83651b058966...578b72", "RedAlert.apk — malicious Android app", "Mobile Malware", "HIGH"],
            ["7d9fb236607e...e964c9", "Associated malware sample", "Malware", "HIGH"],
        ],
        col_widths=[1.4*inch, 2.4*inch, 0.9*inch, 0.7*inch]
    )
    story.append(hash_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Full SHA256 hashes for EDR/SIEM integration:</b>", s_body))
    full_hashes = [
        "96dec6e07229201a02f538310815c695cf6147c548ff1c6a0def2fe38f3dcbc8",
        "19001dd441e50233d7f0addb4fcd405a70ac3d5e310ff20b331d6f1a29c634f0",
        "8316065c4536384611cbe7b6ba6a5f12f10db09949e66cb608c92ae8b69e4d67",
        "9e519211947c63d9bf6f4a51bc161f5b9ace596c2935a8eedfce4057f747b961",
        "fe07dca68f288a4f6d7cbd34d79bb70bc309635876298d4fde33c25277e30bd2",
        "ca9bf13897af109cb354f2629c10803966eb757ee4b2e468abc04e7681d0d74a",
        "e28085e8d64bb737721b1a1d494f177e571c47aab7c9507dba38253f6183af35",
        "454e6d3782f23455875a5db64e1a8cd8eb743400d8c6dadb1cd8fd2ffc2f9567",
        "6f79c0e0e1aab63c3aba0b781e0e46c95b5798b2d4f7b6ecac474b5c40b840ad",
        "ad66251d9e8792cf4963b0c97f7ab44c8b68101e36b79abc501bee1807166e8a",
        "64c5fd791ee369082273b685f724d5916bd4cad756750a5fe953c4005bb5428c",
        "336167b8c5cfc5cd330502e7aa515cc133656e12cbedb4b41ebbf847347b2767",
        "f58d3a4b2f3f7f10815c24586fae91964eeed830369e7e0701b43895b0cefbd3",
        "aae989743dddc84adef90622c657e45e23386488fa79d7fe7cf0863043b8acd4",
        "83651b0589665b112687f0858bfe2832ca317ba75e700c91ac34025ee6578b72",
        "7d9fb236607e7fe5e0921b06f45d9cb69acbdb923e2877d87a99720b8dc964c9",
    ]
    for idx, h in enumerate(full_hashes, 1):
        story.append(Paragraph(f"<font size=7><b>{idx}.</b> <font face='Courier'>{h}</font></font>", s_small))
    story.append(PageBreak())

    # 5.8 Malicious Filenames
    story.append(Paragraph("5.8 Malicious Filenames (EDR/SIEM Hunting)", s_subsection))
    story.append(Paragraph(
        "The following filenames should be hunted across all endpoints and monitored in EDR solutions:",
        s_body
    ))
    fn_table = make_table(
        ["Filename", "Description", "Severity", "Action"],
        [
            ["F5UPDATER.exe", "Handala loader masquerading as F5 BIG-IP update", "CRITICAL", "HUNT"],
            ["Hatef.exe", "Windows wiper malware", "CRITICAL", "HUNT"],
            ["Handala.exe", "Delphi second-stage loader", "CRITICAL", "HUNT"],
            ["senvarservice-DC.exe", "Data exfiltration component (AWS S3/Storj/Telegram)", "CRITICAL", "HUNT"],
            ["Naples.pif", "Renamed AutoIt interpreter (.pif extension evasion)", "HIGH", "HUNT"],
            ["OpenFileFinder.dll", "Wiper DLL component", "CRITICAL", "HUNT"],
            ["ListOpenedFileDrv_32.sys", "Vulnerable driver used for BYOVD privilege escalation", "CRITICAL", "HUNT"],
            ["Carroll.cmd", "Obfuscated batch script for wiper execution", "HIGH", "HUNT"],
            ["RedAlert.apk", "Fake RedAlert app — Android malware", "HIGH", "HUNT"],
            ["update.sh", "Linux wiper payload script (Hamsa)", "CRITICAL", "HUNT"],
        ],
        col_widths=[1.5*inch, 2.6*inch, 0.8*inch, 0.6*inch]
    )
    story.append(fn_table)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 6. INVESTIGATION — CORRELATED FINDINGS (GENERICIZED)
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("6. INVESTIGATION — CORRELATED FINDINGS", s_section))
    story.append(Paragraph(
        "A comprehensive search was conducted across the targeted organization's environment to correlate "
        "the threat actor's claimed IOCs against actual telemetry. The following sections present the high-level findings.",
        s_body
    ))

    # 6.1
    story.append(Paragraph("6.1 Threat Actor IOC Correlation (Negative)", s_subsection))
    story.append(Paragraph(
        "The following claimed indicators were searched across all available telemetry and returned ZERO results:",
        s_body
    ))
    neg_table = make_table(
        ["Indicator Category", "Context", "Result"],
        [
            ["Threat actor C2 IP addresses", "Known Handala infrastructure IPs", "NO HITS"],
            ["Critical CVEs (PAN-OS, Ivanti)", "CVE-2024-3400, CVE-2024-21887, CVE-2023-46805", "NO HITS"],
            ["Energy provider / SCADA keywords", "Solar management vendor, ICS/OT terms", "NO HITS"],
            ["Suspected C2 IP ranges", "185.173.35.0/24, 91.243.44.0/24", "NO HITS"],
            ["Handala primary C2", "31.192.237.207", "NO HITS"],
            ["Exposed subdomains with vulnerabilities", "External-facing application subdomains", "NO HITS"],
        ],
        col_widths=[2.0*inch, 2.6*inch, 0.8*inch]
    )
    story.append(neg_table)

    # 6.2
    story.append(Paragraph("6.2 WAF — External Attacker IPs Detected", s_subsection))
    story.append(Paragraph(
        "While the threat actor's specific IOCs were not found, external attackers were detected probing "
        "the organization's web assets:",
        s_body
    ))
    waf_table = make_table(
        ["Source IP", "Country", "Attack Type"],
        [
            ["178.79.148.111", "United Kingdom", "Database dump file probe (db.sql)"],
            ["165.154.24.96", "Hong Kong", "Phishing reconnaissance probe"],
            ["194.238.28.128", "Unknown", "Security researcher reconnaissance"],
        ],
        col_widths=[1.3*inch, 1.2*inch, 3.3*inch]
    )
    story.append(waf_table)

    # 6.3
    story.append(Paragraph("6.3 Cloud Storage Reconnaissance Probes", s_subsection))
    story.append(Paragraph(
        "Probes against the organization's cloud storage bucket, all returned AccessDenied:",
        s_body
    ))
    s3_table = make_table(
        ["URI Probed", "Intent", "Result"],
        [
            ["/[bucket-path].7z", "Archive exfiltration attempt", "AccessDenied"],
            ["/[bucket-path]/actuator/prometheus", "Spring Boot actuator endpoint discovery", "AccessDenied"],
            ["/[bucket-path]-api/api/v1/users", "API user enumeration attempt", "AccessDenied"],
        ],
        col_widths=[2.4*inch, 2.4*inch, 1.0*inch]
    )
    story.append(s3_table)

    # 6.4
    story.append(Paragraph("6.4 NGFW — High Severity Threat Events", s_subsection))
    story.append(Paragraph(
        "4 high-severity events detected on the primary next-generation firewall:",
        s_body
    ))
    fw_table = make_table(
        ["Timestamp", "Source (Internal)", "Dest", "Threat", "Action"],
        [
            ["2026-03-04 16:11:32", "Internal branch device", "VoIP Gateway :5060/UDP", "SIP Register Brute Force", "DROP"],
            ["2026-03-04 16:11:36", "Internal branch device", "VoIP Gateway :5060/UDP", "SIP Register Brute Force", "DROP"],
            ["2026-03-04 16:15:38", "Internal branch device", "VoIP Gateway :5060/UDP", "SIP Register Brute Force", "DROP"],
            ["2026-03-04 16:15:41", "Internal branch device", "VoIP Gateway :5060/UDP", "SIP Register Brute Force", "DROP"],
        ],
        col_widths=[1.3*inch, 1.2*inch, 1.4*inch, 1.3*inch, 0.6*inch]
    )
    story.append(fw_table)
    story.append(Paragraph(
        "Source IPs are internal branch network devices targeting a VoIP/SIP gateway. Threat category: brute-force. "
        "Application flags include: used-by-malware, has-known-vulnerability. All attacks were DROPPED by the NGFW.",
        s_body
    ))

    # 6.5 - Genericized
    story.append(Paragraph("6.5 Database Audit Events", s_subsection))
    story.append(Paragraph(
        "Database audit trail entries showing a batch service account performing routine SELECT queries on "
        "internal mapping tables. Running under Administrator context. Assessment: <b>normal batch processing activity</b>.",
        s_body
    ))

    # 6.6 - Genericized
    story.append(Paragraph("6.6 Cloud Console — Access Review", s_subsection))
    story.append(Paragraph(
        "A single legitimate console login was detected from an authorized employee originating from the national "
        "telecom provider's IP range. No failed login attempts or suspicious IAM activity detected.",
        s_body
    ))

    # 6.7
    story.append(Paragraph("6.7 Additional Negative Findings", s_subsection))
    neg2_table = make_table(
        ["Search Term", "Result"],
        [
            ["Backdoor tools (webshell, reverse shell, C2 beacons)", "Not detected"],
            ["Remote access tools (AnyDesk, TeamViewer, ngrok, Cobalt Strike)", "Not found"],
            ["Port scanning signatures", "No evidence"],
            ["Lateral movement (pass-the-hash, mimikatz, credential dumping)", "No indicators"],
            ["Claimed attack location references", "Only website content images"],
            ["Handala malware filenames (F5UPDATER.exe, Hatef.exe, etc.)", "Not detected"],
        ],
        col_widths=[3.6*inch, W - 3.6*inch]
    )
    story.append(neg2_table)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 7. MITRE ATT&CK MAPPING
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("7. MITRE ATT&amp;CK MAPPING", s_section))
    story.append(Paragraph(
        "The following MITRE ATT&amp;CK techniques have been mapped based on observed and claimed threat actor "
        "behavior, Handala Hack Team known TTPs, and investigation-correlated findings:",
        s_body
    ))
    mitre_table = make_table(
        ["Tactic ID", "Tactic", "Technique ID", "Technique", "Observation"],
        [
            ["TA0001", "Initial Access", "T1566.001", "Spear Phishing Attachment", "Phishing emails with F5 update lures, RedAlert APK"],
            ["TA0001", "Initial Access", "T1190", "Exploit Public-Facing App", "Management system exploitation; WAF db.sql probe detected"],
            ["TA0001", "Initial Access", "T1199", "Trusted Relationship", "Compromised third-party contractor/vendor system"],
            ["TA0002", "Execution", "T1059.010", "AutoHotkey & AutoIT", "AutoIt-based shellcode injection (Naples.pif)"],
            ["TA0002", "Execution", "T1059", "Command & Scripting", "Carroll.cmd batch script, update.sh Linux wiper"],
            ["TA0003", "Persistence", "T1505.003", "Web Shell", "Backdoor access points on core servers (claimed)"],
            ["TA0003", "Persistence", "T1098", "Account Manipulation", "Maintaining persistent access post-detection"],
            ["TA0004", "Priv Escalation", "T1068", "Exploitation for Priv Esc", "BYOVD via ListOpenedFileDrv_32.sys"],
            ["TA0005", "Defense Evasion", "T1027", "Obfuscated Files", "Encrypted wiper payloads, obfuscated AutoIt scripts"],
            ["TA0005", "Defense Evasion", "T1497.003", "Time-Based Evasion", "Sleep delays to evade sandbox analysis"],
            ["TA0005", "Defense Evasion", "T1562.004", "Disable/Modify FW", "Circumventing port blocking and access restrictions"],
            ["TA0006", "Credential Access", "T1110", "Brute Force", "SIP Register brute force on VoIP gateway (confirmed)"],
            ["TA0007", "Discovery", "T1046", "Network Service Scan", "Live monitoring and enumeration of servers"],
            ["TA0007", "Discovery", "T1087", "Account Discovery", "/api/v1/users enumeration attempt (confirmed)"],
            ["TA0007", "Discovery", "T1590", "Gather Victim Net Info", "Reconnaissance via icanhazip.com for victim IP"],
            ["TA0009", "Collection", "T1005", "Data from Local Sys", "Capture of server dashboards and SCADA panels"],
            ["TA0010", "Exfiltration", "T1020", "Automated Exfiltration", "Messaging platform C2 + AWS S3 + Storj"],
            ["TA0011", "C2", "T1071", "App Layer Protocol", "HTTPS on port 2515 to C2; messaging bot API"],
            ["TA0040", "Impact", "T1561.002", "Disk Structure Wipe", "Hatef.exe (Windows) and Hamsa/update.sh (Linux)"],
            ["TA0040", "Impact", "T1489", "Service Stop", "Solar inverter grid disconnection"],
        ],
        col_widths=[0.6*inch, 0.8*inch, 0.65*inch, 1.1*inch, 2.65*inch]
    )
    story.append(mitre_table)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 8. DEFENSIVE RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("8. DEFENSIVE RECOMMENDATIONS", s_section))

    story.append(Paragraph("8.1 Immediate Actions (0–24 Hours)", s_subsection))
    imm_actions = [
        "Conduct emergency audit of all third-party management systems deployed across organizational infrastructure, with priority on contractor-deployed platforms.",
        "Implement emergency firewall rules (see Section 9) to block identified IOC IP ranges, Handala C2 (31.192.237.207), and non-standard ports (TCP/2515, TCP/4443, TCP/8443, TCP/9090).",
        "Block all malicious domains: api.ra-backup.com, shirideitch.com, sjc1.vultrobjects.com, web27.info, handala-hack.to.",
        "Deploy EDR hunting rules for Handala malware filenames: F5UPDATER.exe, Hatef.exe, Handala.exe, senvarservice-DC.exe, Naples.pif, OpenFileFinder.dll.",
        "Hunt for all 16 SHA256 malware hashes across all endpoints (see Section 5.7).",
        "Isolate and forensically image any systems associated with the compromised management platform.",
        "Engage National CERT and relevant financial sector ISACs for coordinated response.",
        "Review and rotate all administrative credentials associated with core systems and SCADA/ICS platforms.",
        "Verify solar energy system status — physical/network audit of energy monitoring infrastructure.",
        "Validate whether any exposed subdomains exist and assess their current patch status.",
        "Block external recon IPs: 178.79.148.111 (db.sql probe), 165.154.24.96 (phishing probe).",
        "Monitor outbound connections to known C2 infrastructure from non-standard hosts.",
    ]
    for a in imm_actions:
        story.append(Paragraph(f"•  {a}", s_bullet))

    story.append(Paragraph("8.2 Short-Term Actions (1–7 Days)", s_subsection))
    short_actions = [
        "Conduct comprehensive network traffic analysis for communications to/from identified IP ranges over the past 90 days.",
        "Perform full vulnerability assessment on all solar monitoring and SCADA/ICS systems within the operational zone.",
        "Deploy enhanced monitoring (EDR/NDR) on all core servers with specific detection rules for the TTPs identified in Section 7.",
        "Engage third-party incident response firm to conduct independent forensic analysis of the compromised management system.",
        "Review all contractor access and implement zero-trust network segmentation for third-party managed systems.",
        "Monitor Handala leak sites daily: handala-hack.to and .onion site for data publication (avg 23.8 day delay).",
        "Investigate SIP brute force from internal branch devices targeting VoIP gateway.",
        "Confirm whether externally-reported IPs belong to organizational assets.",
        "Hunt for BYOVD indicators: ListOpenedFileDrv_32.sys vulnerable driver loading across all Windows endpoints.",
    ]
    for a in short_actions:
        story.append(Paragraph(f"•  {a}", s_bullet))

    story.append(Paragraph("8.3 Long-Term Actions (1–3 Months)", s_subsection))
    long_actions = [
        "Implement supply chain security assessment framework for all technology vendors and contractors.",
        "Deploy network micro-segmentation between IT and OT (SCADA/ICS) environments.",
        "Establish continuous threat monitoring for Iranian-nexus threat actors (Handala, CyberAv3ngers) targeting regional financial and energy sectors.",
        "Conduct tabletop exercise simulating supply chain compromise scenario based on this incident.",
        "Review and enhance SCADA/ICS security posture across all critical infrastructure assets.",
        "Implement canary tokens and deception technology on high-value assets to detect persistent access.",
    ]
    for a in long_actions:
        story.append(Paragraph(f"•  {a}", s_bullet))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 9. CONSOLIDATED IOC SUMMARY
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("9. CONSOLIDATED IOC SUMMARY", s_section))

    story.append(Paragraph("<b>Handala C2 &amp; Threat Infrastructure</b>", s_body_bold))
    c2_sum = make_table(
        ["IP / Indicator", "Threat Type", "Source", "Confidence"],
        [
            ["31.192.237[.]207:2515", "Handala primary C2 server (Chelyabinsk, RU)", "Intezer/Splunk", "CRITICAL"],
            ["38.180.239[.]161", "Associated threat infrastructure", "Threat intel", "HIGH"],
            ["209.74.87[.]100", "Associated threat infrastructure", "Threat intel", "HIGH"],
            ["157.20.182[.]49", "Associated threat infrastructure", "Threat intel", "HIGH"],
            ["185.236.25[.]11", "Associated threat infrastructure", "Threat intel", "HIGH"],
            ["92.243.65[.]243", "Associated threat infrastructure", "Threat intel", "HIGH"],
            ["185.173.35[.]0/24", "Suspected C2 infrastructure", "Threat claim", "HIGH"],
            ["91.243.44[.]0/24", "SCADA/ICS callback range", "Threat claim", "MEDIUM"],
            ["TCP/2515, 4443, 8443, 9090", "C2 and backdoor ports", "Threat intel", "HIGH"],
        ],
        col_widths=[1.5*inch, 2.2*inch, 1.0*inch, 0.8*inch]
    )
    story.append(c2_sum)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Malicious Domains &amp; URLs</b>", s_body_bold))
    dom_sum = make_table(
        ["Indicator", "Context", "Confidence"],
        [
            ["api[.]ra-backup[.]com", "C2 callback domain (RedAlert malware)", "CRITICAL"],
            ["shirideitch[.]com", "Malicious APK delivery domain", "HIGH"],
            ["sjc1[.]vultrobjects[.]com", "Linux wiper payload host", "CRITICAL"],
            ["web27[.]info", "Suspected malware staging / phishing infrastructure", "HIGH"],
            ["handala-hack[.]to", "Handala clearnet leak site (active)", "HIGH"],
            ["handala[.]to", "Handala clearnet leak site (down since 2025-06-26)", "HIGH"],
            ["hxxp://38[.]180[.]239[.]161", "Threat infrastructure HTTP endpoint", "HIGH"],
            ["hxxps://bit[.]ly/4tWJhQh", "Shortened URL — suspected malware delivery", "HIGH"],
        ],
        col_widths=[2.2*inch, 2.6*inch, 0.8*inch]
    )
    story.append(dom_sum)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Malware Hashes (16 samples)</b>", s_body_bold))
    story.append(Paragraph("See Section 5.7 for complete hash list with all 16 SHA256 values.", s_body))
    hash_sum = make_table(
        ["SHA256 (truncated)", "Description", "Severity"],
        [
            ["96dec6e07229...dcbc8", "update.zip — Phishing delivery archive", "CRITICAL"],
            ["fe07dca68f28...30bd2", "F5UPDATER.exe — .NET loader (signed)", "CRITICAL"],
            ["e28085e8d64b...3af35", "Hatef.exe — Windows wiper", "CRITICAL"],
            ["454e6d3782f2...9567", "Handala.exe — Delphi loader", "CRITICAL"],
            ["6f79c0e0e1aa...40ad", "update.sh — Linux wiper (Hamsa)", "CRITICAL"],
            ["83651b058966...8b72", "RedAlert.apk — Android malware", "HIGH"],
            ["7d9fb236607e...64c9", "Associated malware sample", "HIGH"],
        ],
        col_widths=[1.6*inch, 2.8*inch, 0.8*inch]
    )
    story.append(hash_sum)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Detected External Threat IPs (WAF)</b>", s_body_bold))
    ext_sum = make_table(
        ["IP", "Threat Type", "Source", "Confidence"],
        [
            ["178.79.148.111", "db.sql database dump probe (UK)", "WAF logs", "HIGH"],
            ["165.154.24.96", "Phishing recon probe (Hong Kong)", "WAF logs", "HIGH"],
            ["194.238.28.128", "Security researcher recon", "WAF logs", "MEDIUM"],
        ],
        col_widths=[1.3*inch, 2.4*inch, 0.8*inch, 0.8*inch]
    )
    story.append(ext_sum)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Detected Internal Anomalies</b>", s_body_bold))
    int_sum = make_table(
        ["Source", "Activity", "Risk Level"],
        [
            ["Internal branch device (A)", "SIP brute force against VoIP gateway (:5060)", "MEDIUM"],
            ["Internal branch device (B)", "SIP brute force against VoIP gateway (:5060)", "MEDIUM"],
        ],
        col_widths=[1.8*inch, 3.0*inch, 0.8*inch]
    )
    story.append(int_sum)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 10. APPENDIX
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("10. APPENDIX", s_section))

    story.append(Paragraph("10.1 Threat Communique Translation (Farsi → English)", s_subsection))
    story.append(Paragraph(
        "\"[Target financial institution], one of the prominent and long-standing commercial institutions of "
        "[target country], has been the target of our successful penetration. Since yesterday, we have taken "
        "control of parts of this institution's technical infrastructure and have begun manipulation and "
        "persistent access operations into their primary servers.\"",
        s_body
    ))
    story.append(Paragraph(
        "\"The initial penetration occurred through a management system deployed in [target country] that "
        "inadvertently created multiple backdoor access points to the institution's core servers. We sincerely "
        "thank the contractor responsible for deploying this system.\"",
        s_body
    ))
    story.append(Paragraph(
        "[Truncated — additional content references solar energy systems in a national economic zone]",
        s_body
    ))

    story.append(Paragraph("10.2 Energy Provider Dashboard Analysis", s_subsection))
    story.append(Paragraph(
        "The compromised solar monitoring dashboard reveals a solar installation with the following observed "
        "parameters at time of compromise: Monthly Energy output of 22.02 MWh, Yearly Energy of 253.48 MWh, "
        "system availability of 133.85% (monthly, anomalous reading), ambient temperature of -40°C (indicative "
        "of sensor manipulation). All five inverters in OFF/Grid Loss state.",
        s_body
    ))

    story.append(Paragraph("10.3 Regional Energy Provider — Operations", s_subsection))
    story.append(Paragraph(
        "The affected energy provider operates multiple solar plants in the region with approximately 100 MW "
        "total capacity. The largest installation comprises approximately 46 MWp across 395,000 panels. A "
        "centralized SCADA control center monitors all plants remotely in real-time. The provider was previously "
        "listed as a Handala victim under the name \"BLEnergy\" on 2024-07-23 (confirmed via ransomware.live). "
        "The average delay between Handala attack execution and public claim posting is approximately 23.8 "
        "days — a public post regarding the March 2026 breach may be imminent.",
        s_body
    ))

    story.append(Paragraph("10.4 Handala Hack Team — Registration Identities", s_subsection))
    story.append(Paragraph(
        "Known registration identities associated with Handala infrastructure: WordPress admin username "
        "\"vie6c\", domain registration name \"Roxie Collins\". These identities are used across Handala's leak "
        "site infrastructure and may appear in future domain registrations or web platform setups.",
        s_body
    ))

    # ── Build with header/footer ──
    def add_header_footer(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor("#666666"))
        canvas.drawCentredString(
            letter[0] / 2, letter[1] - 0.45*inch,
            "ScanWave  |  IOC Intelligence Report  |  March 2026"
        )
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(CRITICAL_RED)
        canvas.drawCentredString(
            letter[0] / 2, letter[1] - 0.58*inch,
            "CONFIDENTIAL"
        )
        # Footer
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(HexColor("#999999"))
        canvas.drawCentredString(
            letter[0] / 2, 0.4*inch,
            f"© 2026 ScanWave Cybersecurity  |  platform.scanwave.io  |  soc@scanwave.io"
        )
        canvas.drawRightString(
            letter[0] - 0.75*inch, 0.4*inch,
            f"Page {doc.page}"
        )
        # Header line
        canvas.setStrokeColor(HexColor("#cccccc"))
        canvas.setLineWidth(0.5)
        canvas.line(0.75*inch, letter[1] - 0.62*inch, letter[0] - 0.75*inch, letter[1] - 0.62*inch)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print(f"Report generated: {OUTPUT_PATH}")

if __name__ == "__main__":
    build_report()
