"""Determinismo del Explorador V6 y procedencia de exportaciones."""
import hashlib
import io
import json
import unittest
from zipfile import ZipFile

import pandas as pd

from ignis_explorer_data import (
    calendario_instrumental, comparacion_mensual, crear_exportacion, demo_sintetica,
    normalizar_explorador, resumen_explorador, series_anuales,
)


def datos():
    return pd.DataFrame([
        {"fecha":"2023-01-10","latitude":-33.3,"longitude":-56.1,
         "instrumento":"MODIS","satellite":"A","frp":12,
         "id_registro":"m1","fuente":"ensayo A"},
        {"fecha":"2023-01-10","latitude":-33.3,"longitude":-56.1,
         "instrumento":"VIIRS NOAA-20","satellite":"N20","frp":10,
         "id_registro":"v1","fuente":"ensayo B"},
        {"fecha":"2023-02-11","latitude":-33.3,"longitude":-56.1,
         "instrumento":"MODIS","satellite":"T","frp":15,
         "id_registro":"m2","fuente":"ensayo A"},
        {"fecha":"2025-03-11","latitude":-33.5,"longitude":-55.8,
         "instrumento":"VIIRS NOAA-21","satellite":"N21","frp":18,
         "id_registro":"v2","fuente":"ensayo B"},
    ])


class TestExplorerData(unittest.TestCase):
    def test_normalizacion_sin_mutar_entrada(self):
        source = datos()
        snapshot = source.copy(deep=True)
        normal = normalizar_explorador(source)
        pd.testing.assert_frame_equal(source,snapshot)
        self.assertEqual(len(normal),4)
        self.assertEqual(set(normal.familia),{"MODIS","VIIRS"})

    def test_fuentes_sin_registros_no_son_cero(self):
        m = calendario_instrumental(datos(),"MODIS")
        v = calendario_instrumental(datos(),"VIIRS")
        self.assertEqual(float(m.loc[2023,1]),1.0)
        self.assertTrue(pd.isna(m.loc[2023,3]))
        self.assertTrue(pd.isna(m.loc[2024,1]))
        self.assertEqual(float(v.loc[2025,3]),1.0)
        self.assertTrue(pd.isna(v.loc[2023,2]))

    def test_resumen_no_suma_incendios(self):
        r=resumen_explorador(datos())
        self.assertEqual(r["observaciones"],4)
        self.assertEqual(r["meses_con_ambas_familias"],1)
        self.assertEqual(r["anios_con_registros"],2)
        self.assertFalse(r["datos_calibrados"])
        self.assertFalse(r["cobertura_validada"])

    def test_comparacion_mes_y_series(self):
        c=comparacion_mensual(datos())
        self.assertEqual(int(c["Ambos presentes"].sum()),1)
        self.assertEqual(len(c),3)
        anual=series_anuales(datos())
        self.assertEqual(int(anual["Observaciones"].sum()),4)

    def test_descartar_no_reconocidos_y_coordenadas_invalidas(self):
        d = pd.concat([datos(),pd.DataFrame([
            {"fecha":"2023-01-01","latitude":200,"longitude":-56,"instrumento":"MODIS"},
            {"fecha":"2023-01-01","latitude":-33,"longitude":-56,"instrumento":"TERRA"},
            {"fecha":"sin-fecha","latitude":-33,"longitude":-56,"instrumento":"VIIRS"},
        ])],ignore_index=True)
        self.assertEqual(len(normalizar_explorador(d)),4)

    def test_zip_firma_sha_y_notas_cientificas(self):
        archive = crear_exportacion(datos(),"Uruguay",["MODIS","VIIRS NOAA-20"])
        with ZipFile(io.BytesIO(archive)) as zf:
            self.assertEqual(set(zf.namelist()),{
                "observaciones.csv","comparacion_mensual.csv","manifest.json","LEEME.txt"
            })
            manifest=json.loads(zf.read("manifest.json"))
            self.assertEqual(manifest["observation_count"],4)
            self.assertEqual(manifest["region_selected"],"Uruguay")
            self.assertFalse(manifest["scientific_status"]["quantitative_harmonization"])
            self.assertFalse(manifest["scientific_status"]["instrument_coverage_verified"])
            for name,digest in manifest["sha256"].items():
                self.assertEqual(hashlib.sha256(zf.read(name)).hexdigest(),digest)

    def test_sin_datos_no_infiere_cobertura(self):
        m=calendario_instrumental(pd.DataFrame(),"MODIS")
        self.assertEqual(m.shape[0],0)
        r=resumen_explorador(None)
        self.assertEqual(r["observaciones"],0)
        self.assertIsNone(r["ultima_observacion_utc"])

    def test_demo_sintetica_es_determinista_y_etiquetada(self):
        a=demo_sintetica()
        b=demo_sintetica()
        pd.testing.assert_frame_equal(a,b)
        self.assertGreater(len(a),100)
        self.assertTrue(a["fuente"].str.contains("SIMULACION ARTIFICIAL").all())
        self.assertTrue(a["id_registro"].str.startswith("DEMO-").all())

    def test_zip_de_demo_no_afirma_nasa(self):
        out=crear_exportacion(demo_sintetica(),"DEMO",["MODIS"],demo=True)
        with ZipFile(io.BytesIO(out)) as zf:
            manifest=json.loads(zf.read("manifest.json"))
            self.assertTrue(manifest["demo_sintetica"])
            self.assertIn("SINTÉTICOS",manifest["data_source"])
            self.assertIn("NO PROVIENEN DE NASA",zf.read("LEEME.txt").decode("utf-8"))

    def test_familia_invalida(self):
        with self.assertRaises(ValueError):
            calendario_instrumental(datos(),"LANDSAT")


if __name__=="__main__":
    unittest.main()
