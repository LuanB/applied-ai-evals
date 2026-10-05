"""Synthetic import-shipment bundles with known labels.

Each bundle is one consignment: commercial invoice, packing list, bill of lading, and
1–3 of certificate of origin / phytosanitary certificate / fumigation certificate.
Every page is rendered as a noisy "scan" (rotation, blur, speckle, JPEG) and every
field value is recorded, so classification AND extraction have an exact answer key.

All companies, people and numbers are invented. Two things make it harder than a
title-matching exercise, on purpose and in the way real bundles are hard:
  * a third of pages have no printed document title (letterhead + table only);
  * pages cross-reference each other ("Invoice No." on a packing list, "Fumigation
    Cert" on a B/L), so a keyword rule that fires on the first hit picks wrong.

Run: python generate_trade_docs.py  (seeded; writes data/synthetic/ + labels.json)
"""

from __future__ import annotations

import io
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "synthetic"
FONTS = Path("/System/Library/Fonts/Supplemental")
W, H = 1240, 1754  # A4 @150dpi

CLASSES = ["commercial_invoice", "packing_list", "bill_of_lading",
           "certificate_of_origin", "phytosanitary_certificate", "fumigation_certificate"]

SELLERS = ["Golden Valley Exports Co. Ltd", "Pacific Rim Timber Pte Ltd", "Anatolia Dried Fruits A.S.",
           "Mekong Agri Trading JSC", "Cascade Orchards LLC", "Hanseatic Furniture GmbH",
           "Sierra Citrus Cooperativa", "Lanka Spice Mills (Pvt) Ltd", "Nordic Pine Sawmills AB"]
BUYERS = ["Southern Cross Imports Pty Ltd", "Wattle & Co Wholesale Pty Ltd", "Harbourside Fresh Pty Ltd",
          "Kookaburra Home Furnishings Pty Ltd", "Bluegum Food Distributors Pty Ltd",
          "Riverina Trading Pty Ltd"]
GOODS = [  # description, HS code, botanical name or None, origin
    ("Fresh oranges, navel", "0805.10", "Citrus sinensis", "Spain"),
    ("Sawn timber, pine, kiln dried", "4407.11", "Pinus sylvestris", "Sweden"),
    ("Walnuts, in shell", "0802.31", "Juglans regia", "United States"),
    ("Dried apricots", "0813.10", "Prunus armeniaca", "Turkey"),
    ("Wooden dining chairs", "9403.60", None, "Germany"),
    ("Black pepper, whole", "0904.11", "Piper nigrum", "Sri Lanka"),
    ("Cashew kernels", "0801.32", "Anacardium occidentale", "Vietnam"),
]
PORTS_LOAD = {"Spain": "Valencia", "Sweden": "Gothenburg", "United States": "Oakland",
              "Turkey": "Izmir", "Germany": "Hamburg", "Sri Lanka": "Colombo", "Vietnam": "Ho Chi Minh City"}
PORTS_AU = ["Melbourne", "Sydney", "Brisbane", "Fremantle", "Adelaide"]
VESSELS = ["MSC ARIANNA", "MAERSK KOWLOON", "CMA CGM TAGE", "ONE HARMONY", "EVER GIVEN II", "COSCO LIBRA"]
INCOTERMS = ["FOB", "CIF", "CFR", "EXW", "DAP"]
FUMIGANTS = [("Methyl bromide", "48 g/m3", 24), ("Sulfuryl fluoride", "1500 g-h/m3", 24),
             ("Phosphine", "2 g/m3", 120)]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


@dataclass
class Page:
    id: str
    label: str
    fields: dict
    titled: bool
    lines: list[tuple] = field(default_factory=list)  # (x, y, text, font_name, size)


def container(r: random.Random) -> str:
    return r.choice(["MSKU", "TGHU", "CMAU", "MSCU", "OOLU"]) + f"{r.randint(1000000, 9999999)}"


def d(r: random.Random) -> str:
    return f"{r.randint(1, 28):02d}/{r.randint(7, 9):02d}/2026"


def bundle(r: random.Random, n: int) -> list[Page]:
    seller, buyer = r.choice(SELLERS), r.choice(BUYERS)
    desc, hs, botanical, origin = r.choice(GOODS)
    pkgs = r.randint(200, 1800)
    net = round(pkgs * r.uniform(8, 22), 1)
    gross = round(net * r.uniform(1.04, 1.12), 1)
    cont = container(r)
    inv_no = f"INV-{r.randint(10000, 99999)}"
    pl_no = f"PL-{r.randint(10000, 99999)}"
    bl_no = f"{r.choice(['MEDU', 'MAEU', 'CMDU', 'ONEY'])}{r.randint(10000000, 99999999)}"
    unit = round(r.uniform(1.5, 40), 2)
    total = f"{pkgs * unit:,.2f}"
    currency = r.choice(["USD", "EUR", "AUD"])
    vessel, voyage = r.choice(VESSELS), f"{r.randint(100, 999)}{r.choice('NSEW')}"
    pol, pod = PORTS_LOAD[origin], r.choice(PORTS_AU)
    inv_date = d(r)
    b = f"B{n:02d}"
    pages: list[Page] = []

    def title(p: Page, text: str, y: int = 150):
        if p.titled:
            p.lines.append((W // 2 - len(text) * 13, y, text, "Arial Bold.ttf", 44))

    def letterhead(p: Page, who: str):
        p.lines.append((80, 60, who.upper(), "Arial Bold.ttf", 26))
        p.lines.append((80, 95, f"{r.randint(1, 400)} Industrial Rd, {origin}", "Arial.ttf", 18))

    def kv(p: Page, y: int, k: str, v: str, x: int = 80):
        p.lines.append((x, y, f"{k}:", "Arial Bold.ttf", 20))
        p.lines.append((x + 300, y, v, "Courier New.ttf", 22))

    # commercial invoice -------------------------------------------------
    p = Page(f"{b}-01", "commercial_invoice", {
        "invoice_number": inv_no, "invoice_date": inv_date, "seller": seller, "buyer": buyer,
        "currency": currency, "total_amount": total, "incoterm": r.choice(INCOTERMS), "hs_code": hs},
        titled=r.random() > 0.33)
    letterhead(p, seller)
    title(p, r.choice(["COMMERCIAL INVOICE", "INVOICE", "EXPORT INVOICE"]))
    y = 260
    for k, v in [("Invoice No.", inv_no), ("Date", inv_date), ("Sold to", buyer),
                 ("Packing List No.", pl_no), ("Terms of delivery", p.fields["incoterm"]),
                 ("Currency", currency)]:
        kv(p, y, k, v); y += 48
    y += 30
    p.lines.append((80, y, "Description            HS Code    Qty     Unit price   Amount", "Courier New.ttf", 22)); y += 40
    p.lines.append((80, y, f"{desc[:22]:<22} {hs:<10} {pkgs:<7} {unit:<12} {total}", "Courier New.ttf", 22)); y += 80
    kv(p, y, "TOTAL " + currency, total); y += 60
    p.lines.append((80, y, f"Country of origin: {origin}", "Arial.ttf", 20))
    pages.append(p)

    # packing list -------------------------------------------------------
    p = Page(f"{b}-02", "packing_list", {
        "packing_list_number": pl_no, "invoice_number": inv_no, "total_packages": str(pkgs),
        "gross_weight_kg": f"{gross}", "net_weight_kg": f"{net}", "container_number": cont},
        titled=r.random() > 0.33)
    letterhead(p, seller)
    title(p, r.choice(["PACKING LIST", "PACKING SPECIFICATION", "WEIGHT & PACKING NOTE"]))
    y = 260
    for k, v in [("Ref No.", pl_no), ("Invoice No.", inv_no), ("Consignee", buyer),
                 ("Container", cont), ("Marks", f"{buyer.split()[0].upper()}/{pod.upper()}")]:
        kv(p, y, k, v); y += 48
    y += 30
    p.lines.append((80, y, "Pkgs   Description              Net kg      Gross kg", "Courier New.ttf", 22)); y += 40
    p.lines.append((80, y, f"{pkgs:<6} {desc[:24]:<24} {net:<11} {gross}", "Courier New.ttf", 22)); y += 80
    kv(p, y, "Total packages", str(pkgs)); y += 48
    kv(p, y, "Total gross weight (kg)", str(gross)); y += 48
    kv(p, y, "Total net weight (kg)", str(net))
    pages.append(p)

    # bill of lading -----------------------------------------------------
    p = Page(f"{b}-03", "bill_of_lading", {
        "bl_number": bl_no, "shipper": seller, "consignee": buyer, "vessel": vessel, "voyage": voyage,
        "port_of_loading": pol, "port_of_discharge": pod, "container_number": cont},
        titled=r.random() > 0.33)
    p.lines.append((80, 60, r.choice(["MEDITERRANEAN LINES", "OCEANIC CONTAINER LINE", "TRANS-PACIFIC CARRIERS"]),
                    "Arial Black.ttf", 30))
    title(p, r.choice(["BILL OF LADING", "OCEAN BILL OF LADING", "SEA WAYBILL"]))
    y = 260
    for k, v in [("B/L No.", bl_no), ("Shipper", seller), ("Consignee", buyer), ("Notify party", "Same as consignee"),
                 ("Vessel / Voyage", f"{vessel} / {voyage}"), ("Port of loading", pol),
                 ("Port of discharge", pod), ("Container / Seal", f"{cont} / SL{r.randint(100000, 999999)}")]:
        kv(p, y, k, v); y += 48
    y += 30
    p.lines.append((80, y, f"{pkgs} PACKAGES SAID TO CONTAIN {desc.upper()}", "Courier New.ttf", 22)); y += 40
    p.lines.append((80, y, f"GROSS WEIGHT {gross} KGS   INVOICE {inv_no}", "Courier New.ttf", 22)); y += 40
    if r.random() > 0.5:
        p.lines.append((80, y, "FUMIGATION CERTIFICATE AND PHYTOSANITARY CERTIFICATE ATTACHED", "Courier New.ttf", 22))
    pages.append(p)

    # certificates ------------------------------------------------------
    extras = ["certificate_of_origin"]
    if botanical:
        extras += ["phytosanitary_certificate"]
    if "timber" in desc.lower() or "chairs" in desc.lower() or r.random() > 0.6:
        extras += ["fumigation_certificate"]
    r.shuffle(extras)
    extras = extras[: r.randint(1, len(extras))]
    for i, kind in enumerate(extras, start=4):
        cert = f"{r.choice(['AU', 'EX', 'PC', 'CO', 'FC'])}{r.randint(100000, 999999)}"
        if kind == "certificate_of_origin":
            p = Page(f"{b}-{i:02d}", kind, {"certificate_number": cert, "exporter": seller, "consignee": buyer,
                                            "country_of_origin": origin, "hs_code": hs}, titled=r.random() > 0.33)
            p.lines.append((80, 60, f"CHAMBER OF COMMERCE — {origin.upper()}", "Arial Bold.ttf", 26))
            title(p, r.choice(["CERTIFICATE OF ORIGIN", "ORIGIN DECLARATION"]))
            y = 260
            for k, v in [("Certificate No.", cert), ("Exporter", seller), ("Consignee", buyer),
                         ("Means of transport", f"{vessel} from {pol}"), ("HS heading", hs),
                         ("Goods", desc), ("Country of origin", origin)]:
                kv(p, y, k, v); y += 48
            p.lines.append((80, y + 40, f"We certify the goods described in invoice {inv_no} originate in {origin}.",
                            "Times New Roman.ttf", 22))
        elif kind == "phytosanitary_certificate":
            p = Page(f"{b}-{i:02d}", kind, {"certificate_number": cert, "exporter": seller, "consignee": buyer,
                                            "botanical_name": botanical, "place_of_origin": origin},
                     titled=r.random() > 0.33)
            p.lines.append((80, 60, f"NATIONAL PLANT PROTECTION ORGANIZATION OF {origin.upper()}", "Arial Bold.ttf", 24))
            title(p, "PHYTOSANITARY CERTIFICATE")
            y = 260
            for k, v in [("No.", cert), ("Name of exporter", seller), ("Declared consignee", buyer),
                         ("Botanical name of plants", botanical), ("Place of origin", origin),
                         ("Declared means of conveyance", vessel), ("Point of entry", pod)]:
                kv(p, y, k, v); y += 48
            p.lines.append((80, y + 40, "The plants or plant products described herein have been inspected and are",
                            "Times New Roman.ttf", 22))
            p.lines.append((80, y + 75, "considered free from quarantine pests of the importing contracting party.",
                            "Times New Roman.ttf", 22))
        else:
            fum, dose, hours = r.choice(FUMIGANTS)
            fdate = d(r)
            p = Page(f"{b}-{i:02d}", kind, {"certificate_number": cert, "fumigant": fum, "dosage": dose,
                                            "exposure_hours": str(hours), "date_of_fumigation": fdate,
                                            "container_number": cont}, titled=r.random() > 0.33)
            p.lines.append((80, 60, r.choice(["PESTGUARD FUMIGATION SERVICES", "SAFEHOLD QUARANTINE TREATMENTS"]),
                            "Arial Bold.ttf", 26))
            title(p, r.choice(["FUMIGATION CERTIFICATE", "CERTIFICATE OF TREATMENT"]))
            y = 260
            for k, v in [("Certificate No.", cert), ("Fumigant", fum), ("Dosage rate", dose),
                         ("Exposure period (hrs)", str(hours)), ("Date of fumigation", fdate),
                         ("Container No.", cont), ("Commodity", desc), ("Consignment link", f"B/L {bl_no}")]:
                kv(p, y, k, v); y += 48
        pages.append(p)
    return pages


def render(p: Page, r: random.Random) -> bytes:
    img = Image.new("L", (W, H), 250)
    dr = ImageDraw.Draw(img)
    for x, y, text, fname, size in p.lines:
        dr.text((x, y), text, fill=r.randint(10, 50), font=font(fname, size))
    dr.rectangle((60, 240, W - 60, 240 + 2), fill=120)
    img = img.rotate(r.uniform(-2.0, 2.0), fillcolor=235, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(r.uniform(0.3, 1.1)))
    px = img.load()
    for _ in range(4000):  # speckle
        px[r.randrange(W), r.randrange(H)] = r.randint(0, 255)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=r.randint(45, 70))
    return buf.getvalue()


def main(n_bundles: int = 20, seed: int = 7, split: str = "test") -> None:
    """test = the scored set (seed 7). train = a disjoint set (seed 8) used ONLY to fit
    the classical baseline, so it is never scored on pages it was fitted to."""
    r = random.Random(seed)
    out = OUT if split == "test" else OUT.parent / "synthetic_train"
    out.mkdir(parents=True, exist_ok=True)
    labels = []
    for n in range(n_bundles):
        for p in bundle(r, n):
            (out / f"{p.id}.jpg").write_bytes(render(p, r))
            labels.append({"id": p.id, "label": p.label, "titled": p.titled, "fields": p.fields})
    name = "trade_labels.json" if split == "test" else "trade_train_labels.json"
    (HERE / "data" / name).write_text(json.dumps(labels, indent=1))
    by = {c: sum(l["label"] == c for l in labels) for c in CLASSES}
    print(f"{len(labels)} pages, untitled {sum(not l['titled'] for l in labels)}: {by}")


if __name__ == "__main__":
    main()
    main(n_bundles=10, seed=8, split="train")
