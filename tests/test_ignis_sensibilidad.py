"""Pruebas deterministas del laboratorio de sensibilidad (sin datos externos)."""
import unittest

import pandas as pd

from ignis_sensibilidad import (
    comparar_resoluciones,
    diagnostico_comparabilidad,
    preparar_observaciones,
    presencia_mensual,
)


def observaciones():
    return pd.DataFrame([
        {"fecha": "2026-01-15", "latitude": -33.01, "longitude": -56.01, "instrumento": "MODIS"},
        {"fecha": "2026-01-15", "latitude": -33.015, "longitude": -56.015, "instrumento": "VIIRS S-NPP"},
        {"fecha": "2026-01-15", "latitude": -33.48, "longitude": -56.48, "instrumento": "MODIS"},
        {"fecha": "2026-01-15", "latitude": -33.58, "longitude": -56.58, "instrumento": "VIIRS NOAA-20"},
        {"fecha": "2026-02-01", "latitude": -33.015, "longitude": -56.015, "instrumento": "VIIRS NOAA-21"},
        {"fecha": "2025-01-15", "latitude": -33.01, "longitude": -56.01, "instrumento": "MODIS"},
        {"fecha": "2025-01-15", "latitude": -33.015, "longitude": -56.015, "instrumento": "VIIRS S-NPP"},
    ])


class TestSensibilidad(unittest.TestCase):
    def test_coincidencia_cambia_con_la_escala(self):
        t = comparar_resoluciones(observaciones(), 2026)
        valores = list(t["Celdas-día con ambos"])
        self.assertEqual(valores, [1, 1, 1, 2])
        self.assertEqual(list(t["Días con coincidencia"]), [1, 1, 1, 1])

    def test_filtro_anual_no_mezcla_dias_iguales(self):
        t = comparar_resoluciones(observaciones(), 2025)
        self.assertEqual(t["Celdas-día con ambos"].tolist(), [1, 1, 1, 1])
        self.assertEqual(t["Meses con ambas familias"].tolist(), [1, 1, 1, 1])

    def test_sin_registros_no_equivale_a_cobertura(self):
        t = comparar_resoluciones(observaciones(), 2011)
        self.assertTrue((t["Celdas-día con ambos"] == 0).all())
        d = diagnostico_comparabilidad(pd.DataFrame())
        self.assertFalse(d["cobertura_satelital_verificada"])
        self.assertFalse(d["serie_armonizada_validada"])

    def test_descarta_datos_invalidos_y_sensores_no_reconocidos(self):
        datos = pd.concat([
            observaciones(),
            pd.DataFrame([
                {"fecha": "2026-01-15", "latitude": 120, "longitude": -56, "instrumento": "MODIS"},
                {"fecha": "2026-01-15", "latitude": -33, "longitude": -56, "instrumento": "UNKNOWN"},
                {"fecha": "fecha errónea", "latitude": -33, "longitude": -56, "instrumento": "VIIRS"},
            ]),
        ], ignore_index=True)
        self.assertEqual(len(preparar_observaciones(datos)), len(observaciones()))

    def test_presencia_no_infiere_meses_no_importados(self):
        meses = presencia_mensual(observaciones())
        self.assertEqual(len(meses), 3)
        self.assertEqual(int(meses["Ambas presentes"].sum()), 2)
        febrero = meses[meses["Mes UTC"] == "2026-02"].iloc[0]
        self.assertEqual(int(febrero["MODIS"]), 0)
        self.assertFalse(bool(febrero["Ambas presentes"]))

    def test_duplicados_no_aumentan_celdas_dia(self):
        datos = pd.concat([observaciones(), observaciones().iloc[:2]], ignore_index=True)
        antes = comparar_resoluciones(observaciones(), 2026)
        despues = comparar_resoluciones(datos, 2026)
        pd.testing.assert_frame_equal(antes, despues)

    def test_no_coincidencia_entre_dias_distintos(self):
        data = pd.DataFrame([
            {"fecha": "2026-01-15", "latitude": -33, "longitude": -56, "instrumento": "MODIS"},
            {"fecha": "2026-01-16", "latitude": -33, "longitude": -56, "instrumento": "VIIRS"},
        ])
        self.assertTrue((comparar_resoluciones(data)["Celdas-día con ambos"] == 0).all())

    def test_rechaza_resolucion_invalida_y_columnas_ausentes(self):
        with self.assertRaises(ValueError):
            comparar_resoluciones(observaciones(), 2026, (0,))
        with self.assertRaises(ValueError):
            comparar_resoluciones(pd.DataFrame({"fecha": ["2026-01-01"]}))


if __name__ == "__main__":
    unittest.main()
