"""Pruebas estáticas del diseño espacial inmersivo de IGNIS."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "ignis_espacio.py"


class SpaceLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SPACE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(SPACE))

    def test_orbit_payload_is_opt_in(self):
        func = next(n for n in self.tree.body
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "_build_satellite_payload")
        argument = func.args.args[0]
        self.assertEqual(argument.arg, "use_live_tle")
        self.assertEqual(len(func.args.defaults), 1)
        self.assertIsInstance(func.args.defaults[0], ast.Constant)
        self.assertIs(func.args.defaults[0].value, False)

    def test_tle_fetch_is_optional_and_parallel(self):
        self.assertIn("ThreadPoolExecutor(max_workers=5)", self.source)
        self.assertIn('key="ignis_orbit_source"', self.source)
        self.assertIn('orbit_mode == "TLE actuales"', self.source)

    def test_globe_is_in_hero_slot(self):
        self.assertIn('globe_slot = st.empty()', self.source)
        self.assertIn("with globe_slot:", self.source)
        self.assertIn("height=690", self.source)
        self.assertIn("with globe_col:", self.source)

    def test_orbit_controls_and_timeline(self):
        self.assertIn("Explorador orbital", self.source)
        self.assertIn("Fecha de observación", self.source)
        self.assertIn("LÍNEA TEMPORAL", self.source)
        self.assertIn("Focos térmicos", self.source)

    def test_globe_without_data(self):
        self.assertIn("selected_date = None", self.source)
        self.assertNotIn("No hay fechas válidas en el conjunto cargado", self.source)

    def test_scientific_disclaimer(self):
        self.assertIn("no representan pasadas históricas reales", self.source)
        self.assertIn("no corresponden a las fechas históricas FIRMS", self.source)
        self.assertIn("no emite alertas oficiales", self.source)

    def test_no_duplicated_heading(self):
        self.assertNotIn('st.subheader("🌍 ESPACIO / SEGUIMIENTO SATELITAL")',
                         self.source)


if __name__ == "__main__":
    unittest.main()
