import os
import re
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from weasyprint import HTML, CSS

def parse_chatgpt_response_to_experiences(html_list: str) -> list[dict[str, str]]:
    """
    Parsed eine HTML-Liste mit <li>…</li>-Einträgen in eine Liste von Dicts:
      - title:       Der Inhalt des ersten <strong>…</strong> (falls vorhanden)
      - duration:    Der Inhalt des ersten <em>…</em> (falls vorhanden)
      - description: Der restliche Text im <li>, ohne HTML-Tags und ohne Titel/Dauer
    """
    experiences: list[dict[str, str]] = []

    # 1) Alle <li>…</li>-Blöcke extrahieren
    items = re.findall(r'<li\b[^>]*>(.*?)</li>', html_list, flags=re.DOTALL | re.IGNORECASE)

    for item in items:
        # 2) Titel aus <strong>…</strong>
        title_match = re.search(r'<strong\b[^>]*>(.*?)</strong>', item, flags=re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # 3) Dauer aus <em>…</em>
        duration_match = re.search(r'<em\b[^>]*>(.*?)</em>', item, flags=re.DOTALL | re.IGNORECASE)
        duration = duration_match.group(1).strip() if duration_match else ""

        # 4) Beschreibung: letzten <p>-Block als Fließtext extrahieren
        paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', item, flags=re.DOTALL | re.IGNORECASE)
        description = ""
        if paragraphs:
            last_paragraph = paragraphs[-1]
            # Entferne Titel, Dauer, Technologien
            last_paragraph = re.sub(r'<[^>]+>', '', last_paragraph).strip()
            if title:
                last_paragraph = last_paragraph.replace(title, "").strip()
            if duration:
                last_paragraph = last_paragraph.replace(duration, "").strip()
            last_paragraph = re.sub(r'^Technologien\s*:\s*', '', last_paragraph, flags=re.IGNORECASE)
            description = last_paragraph

        experiences.append({
            "title": title,
            "duration": duration,
            "description": description
        })

    return experiences

def _parse_end_date(duration: str) -> datetime:
    """
    Erwartet Formate wie 'MM/YYYY' oder 'Month YYYY' und gibt ein datetime-Objekt zurück.
    Bei Fehlern sehr weit in die Vergangenheit sortieren.
    """
    try:
        # z.B. '04/2022'
        return datetime.strptime(duration, "%m/%Y")
    except:
        try:
            # z.B. 'April 2022'
            return datetime.strptime(duration, "%B %Y")
        except:
            return datetime(1900, 1, 1)

def sort_experiences_by_end_date(experiences: list[dict]) -> list[dict]:
    """
    Sortiert die Erfahrungen absteigend nach ihrem Enddatum.
    """
    return sorted(
        experiences,
        key=lambda e: _parse_end_date(e.get("duration", "")),
        reverse=True
    )

def generate_kurzprofil_html(static_info: dict,
                             experiences: str,
                             template_path: str,
                             output_dir: str,
                             job_title: str) -> str:
    """
    Generiert ein HTML-Kurzprofil aus statischen Daten und geparsten Erfahrungen.
    - static_info: dict mit "name","title","skills","languages"
    - experiences: entweder der rohe ChatGPT-String oder bereits eine List[dict]
    """
    # 1. Template laden
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template("kurzprofil_template.html")

    # Schriftgröße im Body etwas verkleinern, einheitlich für alle Texte
    style_block = """
    <style>
      body {
        font-size: 11px;
        line-height: 1.4;
      }
      h1, h2, h3, .section-header, li strong, li em, .profile-description {
        font-size: 11px !important;
      }
    </style>
    """
    # 2. Rendern
    rendered_html = style_block + template.render(
        name=static_info["name"],
        title=static_info["title"],
        skills=static_info["skills"],
        languages=static_info["languages"],
        description=static_info.get("description", ""),
        experiences_html=experiences,
        logo_path=os.path.abspath(os.path.join(template_path, "Logo-BW.png")),
        photo_path=os.path.abspath(os.path.join(template_path, "marcel.jpeg"))
    )

    # 6. Speichern
    safe_name = f"{static_info['name'].replace(' ', '_')}_{job_title}"
    output_html = os.path.join(output_dir, f"Kurzprofil_{safe_name}.html")
    output_pdf = os.path.join(output_dir, f"Kurzprofil_{safe_name}.pdf")

    os.makedirs(output_dir, exist_ok=True)

    # Speichern als HTML (auskommentiert)
    # with open(output_html, "w", encoding="utf-8") as f:
    #     f.write(rendered_html)

    # Konvertieren in PDF mit base_url, damit Bilder (Logo & Foto) korrekt eingebunden werden
    HTML(string=rendered_html, base_url=template_path).write_pdf(
        output_pdf,
        stylesheets=[CSS(string="""
            @page {
                size: A4;
                margin: 1.5cm;
            }
            body {
                font-size: 11px;
                line-height: 1.4;
            }
            h1, h2, h3 {
                page-break-after: avoid;
            }
        """)]
    )

    print(f"✅ HTML-Kurzprofil gespeichert unter: {output_html}")
    print(f"✅ PDF-Kurzprofil gespeichert unter: {output_pdf}")
    return output_pdf