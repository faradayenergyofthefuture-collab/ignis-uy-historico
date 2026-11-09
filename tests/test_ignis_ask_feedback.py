"""Regresiones de ASK IGNIS en español y del formulario de contribuciones."""
import ast
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import unittest

import pandas as pd

from ignis_ask import normalizar_pregunta, responder_ignis

ROOT = Path(__file__).resolve().parents[1]


def example_data():
    return pd.DataFrame([
        {"fecha": "2024-01-11", "latitude": -33.4, "longitude": -56.3,
         "instrumento": "MODIS", "frp": 12.5, "fuente": "FIRMS"},
        {"fecha": "2025-02-15", "latitude": -32.5, "longitude": -55.4,
         "instrumento": "VIIRS", "frp": 22.0, "fuente": "FIRMS"},
        {"fecha": "2025-03-05", "latitude": -30.5, "longitude": -56.4,
         "instrumento": "VIIRS", "frp": None, "fuente": "FIRMS"},
    ])


def extract_preparar_aporte():
    path = ROOT / "ignis_feedback.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "preparar_aporte")
    env = {"urlencode": __import__("urllib.parse", fromlist=["urlencode"]).urlencode,
           "ISSUES_URL": "https://github.com/sarapcoffee/ignis-uy-historico/issues"}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), env)
    return env["preparar_aporte"]


class AskIgnisSpanishTests(unittest.TestCase):
    def test_normalizes_accents(self):
        self.assertEqual(normalizar_pregunta("¿Cuántas detecciones?"), "¿cuantas detecciones?")

    def test_no_external_llm(self):
        result = responder_ignis(example_data(), "¿Qué IA utiliza ASK IGNIS?")
        self.assertIn("no utiliza GPT", result["answer"].lower().replace("no utiliza gpt", "no utiliza GPT"))
        self.assertIsNone(result["chart"])

    def test_handles_missing_files_in_spanish(self):
        result = responder_ignis(pd.DataFrame(), "¿Cuántos registros hay?")
        self.assertIn("Todavía no hay registros", result["answer"])
        self.assertEqual(result["sources"], [])

    def test_modis_viirs_comparison(self):
        result = responder_ignis(example_data(), "Compará las observaciones MODIS y VIIRS.")
        self.assertEqual(result["chart"]["Observaciones"].sum(), 3)
        self.assertEqual(set(result["chart"]["Instrumento"]), {"MODIS", "VIIRS"})
        self.assertIn("no están armonizados", result["answer"])

    def test_historical_yearly(self):
        result = responder_ignis(example_data(), "Mostrá el histórico por año.")
        self.assertEqual(result["chart"]["Año"].tolist(), [2024, 2025])
        self.assertIn("Serie anual", result["answer"])

    def test_frp_spanish(self):
        result = responder_ignis(example_data(), "¿Cuáles son los valores de FRP?")
        self.assertIn("12.50 MW", result["answer"])
        self.assertIn("22.00 MW", result["answer"])

    def test_does_not_invent_fire_confirmations(self):
        result = responder_ignis(example_data(), "¿Son incendios confirmados?")
        self.assertIn("no la confirmación de un incendio", result["answer"])
        self.assertIsNone(result["chart"])

    def test_unknown_question_is_not_fabricated(self):
        result = responder_ignis(example_data(), "¿Cuál es la temperatura de Marte?")
        self.assertIn("No reconozco todavía", result["answer"])
        self.assertIsNone(result["chart"])

    def test_uruguay_filter(self):
        df = example_data().copy()
        df.loc[len(df)] = ["2025-03-05", 42.0, 11.0, "VIIRS", 4, "FIRMS"]
        result = responder_ignis(df, "¿Cuántos registros hay en Uruguay?")
        self.assertIn("3 registros", result["answer"])

    def test_contact_url_encodes_user_text(self):
        build = extract_preparar_aporte()
        url, markdown = build("Fuente documental o noticia", "Incendio en Durazno",
                              "Encontré un reporte fechado 2022-01-08 para verificar.",
                              "https://example.org/reporte")
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "github.com")
        self.assertEqual(parsed.path, "/sarapcoffee/ignis-uy-historico/issues/new")
        fields = parse_qs(parsed.query)
        self.assertIn("Incendio en Durazno", fields["title"][0])
        self.assertIn("2022-01-08", fields["body"][0])
        self.assertIn("https://example.org/reporte", markdown)

    def test_feedback_requires_real_github_publish(self):
        source = (ROOT / "ignis_feedback.py").read_text(encoding="utf-8")
        self.assertIn('if issues is True:', source)
        self.assertIn('st.link_button(', source)
        self.assertIn('has_issues', source)
        self.assertIn('Submit new issue', source)
        self.assertIn('st.download_button(', source)

    def test_main_has_page_and_no_widget_reassignment(self):
        source = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")
        self.assertIn('NAV_PAGES[14]', source)
        self.assertIn('mostrar_contacto_team()', source)
        self.assertIn('st.chat_input(', source)
        self.assertIn('on_click=_ignis_navigate_to', source)

    def test_syntax(self):
        for filename in ("ignis_historico.py", "ignis_ask.py", "ignis_feedback.py"):
            with self.subTest(filename=filename):
                path = ROOT / filename
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
