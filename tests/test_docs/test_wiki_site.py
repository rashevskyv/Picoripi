"""The wiki builds into a static site whose links and pictures all resolve."""
import re

from scripts import build_wiki_site


def test_the_wiki_site_builds_and_every_local_link_resolves(tmp_path):
    pages = build_wiki_site.build(tmp_path / "site")
    site = tmp_path / "site"
    assert pages == len(list(site.rglob("*.html"))) > 20
    assert (site / "index.html").exists() and (site / "uk" / "index.html").exists()
    broken = []
    for page in site.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text(encoding="utf-8")):
            if not ref.startswith(("http", "#", "mailto")) and not (page.parent / ref.split("#")[0]).exists():
                broken.append(f"{page.relative_to(site)} -> {ref}")
    assert broken == []


def test_the_getting_started_page_is_the_first_page_and_draws_its_diagram(tmp_path):
    build_wiki_site.build(tmp_path / "site")
    html = (tmp_path / "site" / "0_Getting_Started.html").read_text(encoding="utf-8")
    assert '<pre class="mermaid">' in html and 'src="img/getting_started/01_first_start.png"' in html
    index = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert index.index("0_Getting_Started.html") < index.index("1_User_Guide_and_Workflow_Pipeline.html")


def test_the_site_names_its_domain(tmp_path):
    build_wiki_site.build(tmp_path / "site")
    assert (tmp_path / "site" / "CNAME").read_text(encoding="utf-8").strip() == "picoripi.customfw.xyz"
