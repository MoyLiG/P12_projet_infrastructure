"""
Génère le support de soutenance P12 (.pptx) via python-pptx.

Design : structure "sandwich" — slides sombres (titre, résultats, conclusion),
slides claires (contenu). Accent emerald (sport/énergie), violet secondaire.
Motif récurrent : pastille numérotée + cards à barre latérale gauche.

Usage : python docs/soutenance/build_pptx.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

OUT = Path(__file__).resolve().parent / "Le_Gall_Morgan_Option_B_1_support_062026.pptx"

# ----- Palette ---------------------------------------------------------
DARK      = RGBColor(0x0E, 0x14, 0x1B)   # charcoal (fond sombre)
DARK2     = RGBColor(0x16, 0x20, 0x2B)   # surface sombre
LIGHT     = RGBColor(0xF4, 0xF6, 0xF5)   # off-white (fond clair)
CARD      = RGBColor(0xFF, 0xFF, 0xFF)   # carte sur fond clair
EMERALD   = RGBColor(0x10, 0xB9, 0x81)   # accent principal
EMERALD_L = RGBColor(0x34, 0xD3, 0x99)   # accent clair
VIOLET    = RGBColor(0x7C, 0x6F, 0xF0)   # secondaire
INK       = RGBColor(0x1A, 0x22, 0x2E)   # texte sombre
MUTED     = RGBColor(0x5B, 0x6B, 0x7A)   # texte muté
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHTTXT  = RGBColor(0xE7, 0xEC, 0xEA)   # texte clair sur sombre
DIM       = RGBColor(0x8A, 0x99, 0xA6)   # muté clair sur sombre

F_TITLE = "Trebuchet MS"
F_BODY  = "Calibri"

EMU_W, EMU_H = Inches(13.333), Inches(7.5)


def solid(shape, color, line=None, line_w=None):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w or 1)
    shape.shadow.inherit = False
    return shape


def rect(slide, x, y, w, h, color, line=None, line_w=None, rounded=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    return solid(shp, color, line, line_w)


def textbox(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            space_after=6, line_spacing=1.0):
    """runs: list of paragraphs ; chaque para = list de (text, size, color, bold, font, italic)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        if line_spacing:
            p.line_spacing = line_spacing
        for (text, size, color, bold, font, italic) in para:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.color.rgb = color
            r.font.bold = bold
            r.font.name = font
            r.font.italic = italic
    return tb


def R(text, size, color, bold=False, font=F_BODY, italic=False):
    return (text, size, color, bold, font, italic)


def pill(slide, x, y, label, fill=EMERALD, txt=WHITE, w=None):
    w = w or (0.18 * len(label) + 0.4)
    p = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.42))
    solid(p, fill)
    tf = p.text_frame
    tf.margin_top = 0; tf.margin_bottom = 0
    para = tf.paragraphs[0]; para.alignment = PP_ALIGN.CENTER
    run = para.add_run(); run.text = label
    run.font.size = Pt(11); run.font.bold = True; run.font.color.rgb = txt
    run.font.name = F_BODY
    return w


def footer(slide, n, dark=False):
    c = DIM if dark else MUTED
    textbox(slide, 0.6, 7.04, 8, 0.3,
            [[R("Sport Data Solution — POC Avantages Sportifs", 9, c, False)]])
    textbox(slide, 11.5, 7.04, 1.2, 0.3,
            [[R(f"{n:02d} / 15", 9, c, False)]], align=PP_ALIGN.RIGHT)


def title_block(slide, kicker, title):
    """Bandeau de titre standard pour slides de contenu (fond clair)."""
    # pastille accent + kicker
    rect(slide, 0.6, 0.5, 0.22, 0.22, EMERALD)
    textbox(slide, 0.95, 0.44, 8, 0.35, [[R(kicker.upper(), 12, EMERALD, True)]])
    textbox(slide, 0.58, 0.78, 12, 0.9, [[R(title, 30, INK, True, F_TITLE)]])


# =====================================================================
prs = Presentation()
prs.slide_width = EMU_W
prs.slide_height = EMU_H
BLANK = prs.slide_layouts[6]


def new_slide(bg):
    s = prs.slides.add_slide(BLANK)
    rect(s, -0.1, -0.1, 13.5, 7.7, bg)
    return s


# ---- Slide 1 : Titre --------------------------------------------------
s = new_slide(DARK)
# bloc accent décoratif
rect(s, 0, 0, 0.28, 7.5, EMERALD)
rect(s, 10.7, 5.2, 2.4, 2.4, DARK2)
rect(s, 11.0, 5.5, 1.8, 1.8, EMERALD)
pill(s, 0.9, 1.5, "OPENCLASSROOMS · DATA ENGINEER · OPTION B", fill=DARK2, txt=EMERALD_L, w=6.2)
textbox(s, 0.85, 2.3, 11.5, 2.2,
        [[R("POC Avantages Sportifs", 52, WHITE, True, F_TITLE)]])
textbox(s, 0.9, 4.25, 11, 0.7,
        [[R("Pipeline ETL bout-en-bout — Sport Data Solution", 22, EMERALD_L, False, F_BODY)]])
textbox(s, 0.9, 5.7, 11, 1.2,
        [[R("Morgan Le Gall", 16, LIGHTTXT, True)],
         [R("Juin 2026  ·  Faisabilité · Qualité des données · Impact financier", 13, DIM, False)]],
        space_after=4)

# ---- Slide 2 : Contexte & mission ------------------------------------
s = new_slide(LIGHT)
title_block(s, "Contexte", "La mission confiée par Juliette")
textbox(s, 0.6, 1.75, 12.1, 0.7,
        [[R("Encourager la pratique sportive des 161 salariés via deux avantages — "
            "et mesurer leur coût avant d'industrialiser.", 15, MUTED, False)]],
        line_spacing=1.15)
# 2 grandes cartes avantages
def adv_card(x, tag, tagcol, title, body):
    rect(s, x, 2.7, 5.85, 3.4, CARD)
    rect(s, x, 2.7, 0.12, 3.4, tagcol)
    pill(s, x + 0.45, 3.05, tag, fill=tagcol, w=1.7)
    textbox(s, x + 0.45, 3.75, 5.1, 0.9, [[R(title, 20, INK, True, F_TITLE)]])
    textbox(s, x + 0.45, 4.5, 5.1, 1.4, [[R(body, 14, MUTED, False)]], line_spacing=1.2)

adv_card(0.6, "PRIME", EMERALD,
         "+5 % du salaire annuel brut",
         "Pour les salariés venant au bureau en mode actif : marche, course, "
         "vélo, trottinette. Vérifié par la distance domicile-travail.")
adv_card(6.85, "BIEN-ÊTRE", VIOLET,
         "5 jours offerts / an",
         "Pour les salariés réalisant au moins 15 activités physiques sur "
         "l'année, attestées par le flux de données sportives.")
footer(s, 2)

# ---- Slide 3 : Objectifs du POC --------------------------------------
s = new_slide(LIGHT)
title_block(s, "Objectifs", "Ce que le POC doit prouver")
objs = [
    ("01", "Faisabilité technique", "Un pipeline qui tourne de bout en bout, "
     "automatisé et reproductible."),
    ("02", "Données à collecter", "Identifier et structurer les données nécessaires "
     "— dont des données RH sensibles."),
    ("03", "Impact financier", "Chiffrer le coût des avantages, et pouvoir le "
     "recalculer si un paramètre change."),
]
for i, (num, t, b) in enumerate(objs):
    x = 0.6 + i * 4.05
    rect(s, x, 2.5, 3.75, 3.6, CARD)
    rect(s, x, 2.5, 3.75, 0.12, EMERALD)
    textbox(s, x + 0.35, 2.85, 2, 1, [[R(num, 40, EMERALD, True, F_TITLE)]])
    textbox(s, x + 0.35, 4.0, 3.1, 0.8, [[R(t, 18, INK, True, F_TITLE)]])
    textbox(s, x + 0.35, 4.8, 3.1, 1.2, [[R(b, 13.5, MUTED, False)]], line_spacing=1.2)
footer(s, 3)

# ---- Slide 4 : Architecture ------------------------------------------
s = new_slide(LIGHT)
title_block(s, "Architecture", "Un flux orchestré, trois couches de données")

def box(x, y, w, h, title, sub, fill=CARD, tcol=INK, scol=MUTED, bar=EMERALD):
    rect(s, x, y, w, h, fill)
    rect(s, x, y, w, 0.09, bar)
    textbox(s, x + 0.18, y + 0.22, w - 0.36, 0.5, [[R(title, 13.5, tcol, True, F_TITLE)]])
    if sub:
        textbox(s, x + 0.18, y + 0.74, w - 0.36, h - 0.8, [[R(sub, 10.5, scol, False)]], line_spacing=1.1)

def arrow(x, y, w=0.5):
    a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(0.3))
    solid(a, EMERALD)

# Sources (col 1)
textbox(s, 0.6, 1.95, 3, 0.3, [[R("SOURCES", 11, VIOLET, True)]])
box(0.6, 2.3, 3.0, 0.95, "Fichiers RH", "161 salariés · PII", bar=VIOLET)
box(0.6, 3.45, 3.0, 0.95, "Pratiques sportives", "déclaratif", bar=VIOLET)
box(0.6, 4.6, 3.0, 0.95, "Générateur Strava-like", "3948 activités / 12 mois", bar=VIOLET)
arrow(3.75, 3.55)

# PostgreSQL (col 2)
textbox(s, 4.4, 1.95, 4, 0.3, [[R("POSTGRESQL", 11, EMERALD, True)]])
box(4.4, 2.3, 4.0, 3.25, "Base sécurisée",
    "raw  →  staging  →  marts\n\n+ audit (monitoring)\n+ cache (Google Maps)", bar=EMERALD)
arrow(8.55, 3.55)

# Traitements + sorties (col 3)
textbox(s, 9.25, 1.95, 4, 0.3, [[R("VALIDATION & SORTIES", 11, EMERALD, True)]])
box(9.25, 2.3, 3.45, 0.95, "Validation géo + qualité", "Google Maps · Great Expectations")
box(9.25, 3.45, 3.45, 0.95, "Calcul des avantages", "prime · jours bien-être")
box(9.25, 4.6, 1.62, 0.95, "Slack", "messages", bar=VIOLET)
box(11.1, 4.6, 1.6, 0.95, "PowerBI", "KPIs", bar=VIOLET)

# bandeau orchestrateur
rect(s, 0.6, 5.85, 12.1, 0.7, DARK)
textbox(s, 0.85, 6.0, 12, 0.45,
        [[R("KESTRA  ", 14, EMERALD_L, True, F_TITLE),
          R("orchestre le tout — trigger mensuel, replay, monitoring, alertes mail", 13, LIGHTTXT, False)]],
        anchor=MSO_ANCHOR.MIDDLE)
footer(s, 4)

# ---- Slide 5 : Stack & justifications --------------------------------
s = new_slide(LIGHT)
title_block(s, "Choix techniques", "La bonne brique pour chaque besoin")
rows = [
    ("Orchestration", "Kestra", "Replay de l'historique (demandé), monitoring, trigger cron"),
    ("Base de données", "PostgreSQL 16", "Rôles, RLS, audit — adapté aux données RH sensibles"),
    ("Traitement", "Python + pandas", "Extraction, génération, calculs métier"),
    ("Qualité", "Great Expectations", "Tests déclaratifs, bloquants si échec"),
    ("Géocodage", "Google Maps API", "Distance réelle domicile-travail (+ cache)"),
    ("Notifications", "Slack Webhook", "Messages automatiques, démo crédible"),
    ("Restitution", "PowerBI", "KPIs, paramètre de taux dynamique"),
    ("Conteneurs", "Docker Compose", "Stack reproductible en une commande"),
]
y0 = 1.95
rect(s, 0.6, y0, 12.1, 0.5, DARK)
for j, head in enumerate(["BRIQUE", "OUTIL", "POURQUOI CE CHOIX"]):
    xs = [0.8, 3.5, 6.6][j]
    textbox(s, xs, y0 + 0.06, 6, 0.4, [[R(head, 11, EMERALD_L, True)]], anchor=MSO_ANCHOR.MIDDLE)
for i, (a, b, c) in enumerate(rows):
    y = y0 + 0.5 + i * 0.56
    if i % 2 == 0:
        rect(s, 0.6, y, 12.1, 0.56, CARD)
    textbox(s, 0.8, y + 0.08, 2.6, 0.45, [[R(a, 12.5, INK, True)]], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, 3.5, y + 0.08, 3.0, 0.45, [[R(b, 12.5, EMERALD, True)]], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, 6.6, y + 0.08, 6.0, 0.45, [[R(c, 12, MUTED, False)]], anchor=MSO_ANCHOR.MIDDLE)
footer(s, 5)

# ---- Slide 6 : Pipeline étape par étape ------------------------------
s = new_slide(LIGHT)
title_block(s, "Pipeline", "Sept étapes, de la source à la restitution")
steps = [
    ("1", "Extract RH", "fichiers → base"),
    ("2", "Extract sport", "pratiques déclarées"),
    ("3", "Générer", "activités 12 mois"),
    ("4", "Valider géo", "Google Maps"),
    ("5", "Qualité", "Great Expectations"),
    ("6", "Calculer", "prime + bien-être"),
    ("7", "Notifier", "Slack"),
]
# 2 rangées de pastilles
positions = [(0.6 + i*3.05, 2.4) for i in range(4)] + [(0.6 + i*3.05, 4.55) for i in range(3)]
for i, (num, t, b) in enumerate(steps):
    x, y = positions[i]
    circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(0.75), Inches(0.75))
    solid(circ, EMERALD if i % 2 == 0 else VIOLET)
    tf = circ.text_frame; tf.margin_top = 0; tf.margin_bottom = 0
    pr = tf.paragraphs[0]; pr.alignment = PP_ALIGN.CENTER
    rn = pr.add_run(); rn.text = num; rn.font.size = Pt(26); rn.font.bold = True
    rn.font.color.rgb = WHITE; rn.font.name = F_TITLE
    textbox(s, x + 0.9, y + 0.02, 1.9, 0.5, [[R(t, 15, INK, True, F_TITLE)]])
    textbox(s, x + 0.9, y + 0.45, 1.9, 0.5, [[R(b, 11, MUTED, False)]])
# note bas
rect(s, 0.6, 6.0, 12.1, 0.6, DARK)
textbox(s, 0.85, 6.12, 12, 0.4,
        [[R("Échec d'une étape  →  ", 12.5, EMERALD_L, True),
          R("le pipeline s'arrête et envoie une alerte. On ne calcule jamais sur des données douteuses.", 12.5, LIGHTTXT, False)]],
        anchor=MSO_ANCHOR.MIDDLE)
footer(s, 6)

# ---- Slide 7 : Qualité des données -----------------------------------
s = new_slide(LIGHT)
title_block(s, "Qualité", "Trois lignes de défense")
defs = [
    ("Contraintes SQL", "À l'entrée en base : distance ≥ 0, dates valides, "
     "moyen de transport dans une liste fermée. Rejet immédiat.", EMERALD),
    ("Great Expectations", "Règles métier déclaratives, bloquantes. A détecté "
     "un vrai bug : des activités datées dans le futur.", EMERALD_L),
    ("Validation géographique", "Déclaration « marche » mais domicile à 50 km ? "
     "Google Maps calcule la distance réelle → anomalie remontée.", VIOLET),
]
for i, (t, b, col) in enumerate(defs):
    y = 2.0 + i * 1.5
    rect(s, 0.6, y, 12.1, 1.32, CARD)
    rect(s, 0.6, y, 0.12, 1.32, col)
    circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.95), Inches(y + 0.36), Inches(0.6), Inches(0.6))
    solid(circ, col)
    tf = circ.text_frame; tf.margin_top=0; tf.margin_bottom=0
    pr = tf.paragraphs[0]; pr.alignment = PP_ALIGN.CENTER
    rn = pr.add_run(); rn.text = str(i+1); rn.font.size=Pt(22); rn.font.bold=True; rn.font.color.rgb=WHITE; rn.font.name=F_TITLE
    textbox(s, 1.85, y + 0.22, 10.6, 0.5, [[R(t, 18, INK, True, F_TITLE)]])
    textbox(s, 1.85, y + 0.72, 10.6, 0.55, [[R(b, 13.5, MUTED, False)]], line_spacing=1.15)
footer(s, 7)

# ---- Slide 8 : Sécurité & RGPD ---------------------------------------
s = new_slide(LIGHT)
title_block(s, "Sécurité & RGPD", "Des données RH, donc cloisonnées")
points = [
    "3 rôles PostgreSQL : l'analyste ne voit jamais les noms ni les salaires en clair",
    "Pseudonymisation : hash salé des identités, salaires en tranches",
    "Row Level Security + triggers d'audit (traçabilité RGPD)",
    "Aucun secret dans le code — variables d'environnement, .gitignore strict",
]
rect(s, 0.6, 2.0, 7.6, 4.1, CARD)
textbox(s, 0.95, 2.3, 7, 0.4, [[R("MESURES EN PLACE", 12, EMERALD, True)]])
runs = []
for p in points:
    runs.append([R(p, 14, INK, False)])
textbox(s, 0.95, 2.85, 6.9, 3.0, runs, space_after=12, line_spacing=1.1)
# badge audit sécurité
rect(s, 8.45, 2.0, 4.25, 4.1, DARK)
textbox(s, 8.8, 2.35, 3.6, 0.4, [[R("AUDIT DE SÉCURITÉ", 12, EMERALD_L, True)]])
textbox(s, 8.8, 2.95, 3.6, 1.2, [[R("8 / 9", 54, EMERALD, True, F_TITLE)]])
textbox(s, 8.8, 4.15, 3.6, 0.6, [[R("vulnérabilités corrigées", 14, LIGHTTXT, False)]])
textbox(s, 8.8, 4.9, 3.6, 1.1,
        [[R("Bandit : 0 faille critique", 12.5, DIM, False)],
         [R("Socket Docker retiré", 12.5, DIM, False)],
         [R("Dépendances à jour", 12.5, DIM, False)]], space_after=5)
footer(s, 8)

# ---- Slide 9 : Cycle de vie des données personnelles (PII) -----------
s = new_slide(LIGHT)
title_block(s, "Données personnelles", "Le cycle de vie d'une donnée RH")
textbox(s, 0.6, 1.75, 12.1, 0.6,
        [[R("La même donnée, trois niveaux d'exposition selon la couche — "
            "et selon le rôle qui la lit.", 15, MUTED, False)]], line_spacing=1.15)

def pii_card(x, tag, tagcol, layer_desc, example):
    w = 3.7
    rect(s, x, 2.55, w, 2.7, CARD)
    rect(s, x, 2.55, w, 0.1, tagcol)
    pill(s, x + 0.3, 2.85, tag, fill=tagcol, w=1.5)
    textbox(s, x + 0.3, 3.5, w - 0.6, 1.1, [[R(layer_desc, 12.5, MUTED, False)]],
            line_spacing=1.18)
    # encart "exemple" en monospace, pour rendre la transformation concrète
    rect(s, x + 0.3, 4.62, w - 0.6, 0.5, LIGHT)
    textbox(s, x + 0.45, 4.7, w - 0.9, 0.4, [[R(example, 10.5, INK, False, "Consolas")]],
            anchor=MSO_ANCHOR.MIDDLE)

pii_card(0.6, "RAW", VIOLET,
         "Reflet brut du fichier RH. Nom, salaire et adresse en clair. "
         "Lisible par le seul pipeline d'ingestion.",
         "Le Gall · 42 000 € · Lattes")
arrow(4.3, 3.7)
pii_card(4.8, "STAGING", EMERALD,
         "Typé et hashé. Les PII en clair restent, mais cloisonnées par "
         "Row Level Security.",
         "Le Gall + hash a3f9c2…")
arrow(8.5, 3.7)
pii_card(9.0, "MARTS", EMERALD_L,
         "Sortie analytique. Zéro PII : hash pseudonyme et tranche de salaire. "
         "Tout ce que voit PowerBI.",
         "a3f9c2… · BU Tech · 40-50 k€")

# bandeau bas : qui voit quoi (les 3 rôles PostgreSQL)
rect(s, 0.6, 5.55, 12.1, 1.0, DARK)
textbox(s, 0.85, 5.68, 4, 0.3, [[R("QUI VOIT QUOI", 11, EMERALD_L, True)]])
textbox(s, 0.85, 6.02, 12.0, 0.45,
        [[R("etl_writer ", 12.5, EMERALD_L, True, "Consolas"),
          R("écrit et lit les PII   ·   ", 12.5, LIGHTTXT, False),
          R("analyst_reader / powerbi_reader ", 12.5, EMERALD_L, True, "Consolas"),
          R("lisent marts uniquement — jamais de PII", 12.5, LIGHTTXT, False)]],
        anchor=MSO_ANCHOR.MIDDLE)
footer(s, 9)

# ---- Slide 10 : Monitoring -------------------------------------------
s = new_slide(LIGHT)
title_block(s, "Monitoring", "Chaque exécution est tracée")
# panneau "run vert"
rect(s, 0.6, 2.0, 5.7, 4.1, DARK)
textbox(s, 0.95, 2.3, 5, 0.4, [[R("DERNIER RUN KESTRA", 12, EMERALD_L, True)]])
textbox(s, 0.95, 2.85, 5, 1.0, [[R("SUCCESS", 40, EMERALD, True, F_TITLE)]])
textbox(s, 0.95, 3.95, 5, 0.5, [[R("7 / 7 tâches  ·  ~20 secondes", 15, LIGHTTXT, False)]])
textbox(s, 0.95, 4.7, 5, 1.2,
        [[R("Volumétrie et durée tracées par étape", 12.5, DIM, False)],
         [R("Alerte mail automatique si échec", 12.5, DIM, False)],
         [R("Interface temps réel + replay", 12.5, DIM, False)]], space_after=6)
# mini-table audit.run_log
rect(s, 6.55, 2.0, 6.15, 4.1, CARD)
textbox(s, 6.85, 2.25, 5.5, 0.4, [[R("audit.run_log (extrait)", 12.5, INK, True)]])
logrows = [
    ("extract_rh", "161", "OK"),
    ("generate_activities", "3948", "OK"),
    ("validate_geo", "161", "OK"),
    ("validate_quality", "3948", "OK"),
    ("compute_advantages", "68", "OK"),
    ("post_slack", "5", "OK"),
]
ly = 2.75
textbox(s, 6.85, ly, 3.2, 0.3, [[R("ÉTAPE", 10, MUTED, True)]])
textbox(s, 10.2, ly, 1.3, 0.3, [[R("LIGNES", 10, MUTED, True)]])
textbox(s, 11.7, ly, 0.9, 0.3, [[R("STATUT", 10, MUTED, True)]])
for i, (st, n, ok) in enumerate(logrows):
    y = ly + 0.4 + i * 0.48
    if i % 2 == 0:
        rect(s, 6.7, y - 0.04, 5.85, 0.46, LIGHT)
    textbox(s, 6.85, y, 3.3, 0.4, [[R(st, 12, INK, False, "Consolas")]], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, 10.2, y, 1.3, 0.4, [[R(n, 12, MUTED, False)]], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, 11.7, y, 0.9, 0.4, [[R(ok, 12, EMERALD, True)]], anchor=MSO_ANCHOR.MIDDLE)
footer(s, 10)

# ---- Slide 11 : Résultats (dark, KPI) --------------------------------
s = new_slide(DARK)
rect(s, 0, 0, 0.28, 7.5, EMERALD)
textbox(s, 0.85, 0.55, 8, 0.4, [[R("RÉSULTATS — IMPACT FINANCIER", 13, EMERALD_L, True)]])
textbox(s, 0.82, 0.95, 11.5, 0.9, [[R("Ce que coûtent les avantages", 30, WHITE, True, F_TITLE)]])

def kpi(x, y, w, number, label, col=EMERALD):
    rect(s, x, y, w, 1.85, DARK2)
    rect(s, x, y, w, 0.09, col)
    textbox(s, x + 0.3, y + 0.32, w - 0.5, 1.0, [[R(number, 38, col, True, F_TITLE)]])
    textbox(s, x + 0.3, y + 1.25, w - 0.5, 0.5, [[R(label, 13, LIGHTTXT, False)]])

kpi(0.85, 2.1, 3.75, "172 482 €", "coût annuel de la prime", EMERALD)
kpi(4.8, 2.1, 3.75, "68 / 161", "salariés éligibles à la prime", EMERALD_L)
kpi(8.75, 2.1, 3.7, "0", "déclaration suspecte", EMERALD_L)
kpi(0.85, 4.15, 3.75, "44", "éligibles aux jours bien-être", VIOLET)
kpi(4.8, 4.15, 3.75, "220", "jours bien-être accordés", VIOLET)
kpi(8.75, 4.15, 3.7, "3 948", "activités sportives analysées", VIOLET)
textbox(s, 0.85, 6.25, 11.5, 0.5,
        [[R("Tous ces chiffres se recalculent en un clic si le taux de prime change.", 13, DIM, False, F_BODY, True)]])
footer(s, 11, dark=True)

# ---- Slide 12 : Démo live --------------------------------------------
s = new_slide(LIGHT)
title_block(s, "Démonstration", "Deux scénarios en direct")
def demo(x, tag, title, steps, col):
    rect(s, x, 2.1, 5.85, 4.0, CARD)
    rect(s, x, 2.1, 5.85, 0.12, col)
    pill(s, x + 0.4, 2.45, tag, fill=col, w=1.5)
    textbox(s, x + 0.4, 3.15, 5.1, 0.7, [[R(title, 19, INK, True, F_TITLE)]])
    runs = [[R(stp, 14, MUTED, False)] for stp in steps]
    textbox(s, x + 0.4, 3.95, 5.1, 2.0, runs, space_after=12, line_spacing=1.15)
demo(0.6, "SCÉNARIO A", "Changer le taux de prime",
     ["1. Passer le taux de 5 % à 7 % dans Kestra",
      "2. Relancer le pipeline",
      "3. Le coût total évolue dans PowerBI"], EMERALD)
demo(6.85, "SCÉNARIO B", "Insérer une activité live",
     ["1. Ajouter une nouvelle course",
      "2. Le message arrive dans Slack",
      "3. L'activité apparaît dans le reporting"], VIOLET)
footer(s, 12)

# ---- Slide 13 : Scalabilité ------------------------------------------
s = new_slide(LIGHT)
title_block(s, "Robustesse & scalabilité", "Pensé pour passer en production")
left = [
    ("Reproductible", "Stack conteneurisée, démarrage en une commande"),
    ("Idempotent", "Rejouable sans créer de doublons (Slack, calculs)"),
    ("Replay", "Recalcul de l'historique si une source change"),
]
right = [
    ("API Strava réelle", "Remplacer le générateur par les vraies données"),
    ("CI/CD", "Tests et audit sécurité automatisés à chaque commit"),
    ("Secret manager", "Rotation des secrets en production"),
]
textbox(s, 0.6, 2.0, 5, 0.4, [[R("DÉJÀ EN PLACE", 12, EMERALD, True)]])
textbox(s, 7.0, 2.0, 5, 0.4, [[R("PROCHAINES ÉTAPES", 12, VIOLET, True)]])
for i, (t, b) in enumerate(left):
    y = 2.5 + i * 1.2
    rect(s, 0.6, y, 5.9, 1.05, CARD); rect(s, 0.6, y, 0.1, 1.05, EMERALD)
    textbox(s, 0.95, y + 0.18, 5.3, 0.5, [[R(t, 16, INK, True, F_TITLE)]])
    textbox(s, 0.95, y + 0.62, 5.3, 0.4, [[R(b, 12.5, MUTED, False)]])
for i, (t, b) in enumerate(right):
    y = 2.5 + i * 1.2
    rect(s, 6.8, y, 5.9, 1.05, CARD); rect(s, 6.8, y, 0.1, 1.05, VIOLET)
    textbox(s, 7.15, y + 0.18, 5.3, 0.5, [[R(t, 16, INK, True, F_TITLE)]])
    textbox(s, 7.15, y + 0.62, 5.3, 0.4, [[R(b, 12.5, MUTED, False)]])
footer(s, 13)

# ---- Slide 14 : Conclusion (dark) ------------------------------------
s = new_slide(DARK)
rect(s, 0, 0, 0.28, 7.5, EMERALD)
pill(s, 0.85, 1.2, "CONCLUSION", fill=DARK2, txt=EMERALD_L, w=2.2)
textbox(s, 0.82, 1.95, 11.5, 1.6,
        [[R("Le POC valide les trois objectifs.", 34, WHITE, True, F_TITLE)]])
checks = [
    "Faisable : pipeline complet, vert, en ~20 secondes",
    "Données maîtrisées : sensibles, cloisonnées, tracées",
    "Coût chiffré et pilotable : 172 482 € / an, recalculable à la demande",
]
runs = [[R("✓  ", 16, EMERALD, True), R(c, 16, LIGHTTXT, False)] for c in checks]
textbox(s, 0.9, 3.7, 11, 2.0, runs, space_after=14, line_spacing=1.1)
rect(s, 0.85, 6.0, 11.85, 0.7, EMERALD)
textbox(s, 1.1, 6.13, 11.4, 0.45,
        [[R("Recommandation : industrialiser, en commençant par l'intégration Strava.", 14, DARK, True)]],
        anchor=MSO_ANCHOR.MIDDLE)
footer(s, 14, dark=True)

# ---- Slide 15 : Merci / questions ------------------------------------
s = new_slide(DARK)
rect(s, 10.7, 0, 2.6, 7.5, DARK2)
rect(s, 11.0, 2.5, 2.0, 2.0, EMERALD)
textbox(s, 0.85, 2.7, 9.5, 1.2, [[R("Merci.", 50, WHITE, True, F_TITLE)]])
textbox(s, 0.9, 3.95, 9, 0.7, [[R("Place à la discussion et à la démonstration.", 18, EMERALD_L, False)]])
textbox(s, 0.9, 5.2, 9, 0.5, [[R("Morgan Le Gall — POC Avantages Sportifs — Sport Data Solution", 13, DIM, False)]])
footer(s, 15, dark=True)

n_slides = len(prs.slides._sldIdLst)
prs.save(str(OUT))
print(f"OK — {n_slides} slides écrites : {OUT}")
