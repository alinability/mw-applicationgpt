import os
from jinja2 import Environment, FileSystemLoader

# Generiert ein HTML-Kurzprofil
# - static_info: dict mit name, title, skills, languages
# - experiences: HTML-String mit Listeneinträgen
# - template_path: Pfad zum Jinja-Template-Ordner
# - output_dir: Zielverzeichnis für die HTML-Datei
# - job_title: Job-Titel, der an den Dateinamen angehängt wird

def generate_kurzprofil_html(static_info: dict,
                             experiences: str,
                             template_path: str,
                             output_dir: str,
                             job_title: str) -> str:
    """
    Generiert ein HTML-Kurzprofil basierend auf einem Jinja2-Template.
    """
    # 1. Template laden
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template("kurzprofil_template.html")

    # 2. Erfahrungen in HTML-String (evtl. schon als <li>-Liste formatiert)
    experiences_html = experiences  # TODO: ggf. weitere Qualitätskontrolle

    # 3. Template rendern
    rendered_html = template.render(
        name=static_info["name"],
        title=static_info["title"],
        skills=static_info["skills"],
        languages=static_info["languages"],
        experiences_html=experiences_html
    )

    # 4. Dateiname: Name + Jobtitel
    safe_name = static_info["name"].replace(" ", "_") + "_" + str(job_title)
    filename = f"Kurzprofil_{safe_name}.html"

    # 5. Speichern
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print(f"✅ HTML-Kurzprofil gespeichert unter: {output_path}")
    return output_path