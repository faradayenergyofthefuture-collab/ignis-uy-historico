"""Pruebas científicas V5: datos sintéticos controlados, sin Internet."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse
import unittest

import pandas as pd

from ignis_calidad import auditar_datos, inventario_mensual, lectura_diagnostica
from ignis_firms_sensor import clasificar_instrumentos
from ignis_pareo_v5 import emparejar_global, preparar_pareo, tiempos_adquisicion
from ignis_worldview import enlace_worldview


def registro(fecha, hora, sensor, lat=-33.0, lon=-56.0, **extra):
    return {
        "fecha": fecha,
        "acq_time": hora,
        "instrumento": sensor,
        "latitude": lat,
        "longitude": lon,
        "frp": extra.get("frp", 8.0),
        "id_registro": extra.get("id_registro", ""),
    }


class TestTiempoUTC(unittest.TestCase):
    def test_hhmm_y_valores_invalidos(self):
        a = pd.DataFrame([
            registro("2026-01-01", "15", "MODIS"),
            registro("2026-01-01", "2359.0", "MODIS"),
            registro("2026-01-01", "2400", "MODIS"),
            registro("2026-01-01", "1262", "MODIS"),
            registro("2026-01-01", "xx", "MODIS"),
        ])
        t = tiempos_adquisicion(a)
        self.assertEqual(t.iloc[0].strftime("%H:%M"), "00:15")
        self.assertEqual(t.iloc[1].strftime("%H:%M"), "23:59")
        self.assertEqual(int(t.isna().sum()), 3)

    def test_sin_hora(self):
        a = pd.DataFrame([{"fecha": "2026-01-01"}])
        self.assertTrue(tiempos_adquisicion(a).isna().all())


class TestPareoV5(unittest.TestCase):
    def test_parea_cruce_medianoche_utc(self):
        a = pd.DataFrame([
            registro("2026-01-01", "2355", "MODIS", id_registro="m"),
            registro("2026-01-02", "0005", "VIIRS NOAA-21", id_registro="v"),
        ])
        pares = emparejar_global(a)
        self.assertEqual(len(pares), 1)
        self.assertTrue(bool(pares.iloc[0]["cruza_dia_utc"]))
        self.assertEqual(float(pares.iloc[0]["diferencia_min"]), 10)

    def test_parea_cruce_de_ano_con_filtro_modis(self):
        a = pd.DataFrame([
            registro("2026-12-31", "2355", "MODIS", id_registro="m"),
            registro("2027-01-01", "0005", "VIIRS NOAA-20", id_registro="v"),
        ])
        self.assertEqual(len(emparejar_global(a,ano=2026)), 1)
        self.assertEqual(len(emparejar_global(a,ano=2027)), 0)

    def test_no_reutiliza_modis_entre_satellites_viirs(self):
        a = pd.DataFrame([
            registro("2026-01-01", "1200", "MODIS",id_registro="m"),
            registro("2026-01-01", "1205", "VIIRS S-NPP",id_registro="v1"),
            registro("2026-01-01", "1206", "VIIRS NOAA-20",id_registro="v2"),
        ])
        pares = emparejar_global(a)
        self.assertEqual(len(pares), 1)
        self.assertEqual(pares.iloc[0]["viirs"], "VIIRS S-NPP")

    def test_multiple_pares_son_unicos(self):
        a = pd.DataFrame([
            registro("2026-01-01", "1200", "MODIS",lat=-33.00,id_registro="m1"),
            registro("2026-01-01", "1210", "MODIS",lat=-33.01,id_registro="m2"),
            registro("2026-01-01", "1203", "VIIRS S-NPP",lat=-33.00,id_registro="v1"),
            registro("2026-01-01", "1212", "VIIRS NOAA-20",lat=-33.01,id_registro="v2"),
        ])
        p = emparejar_global(a,radio_km=5,ventana_min=30)
        self.assertEqual(len(p),2)
        self.assertEqual(set(p.viirs),{"VIIRS S-NPP","VIIRS NOAA-20"})

    def test_descarta_horas_invalidas_y_sensores_ajenos(self):
        a = pd.DataFrame([
            registro("2026-01-01","2400","MODIS"),
            registro("2026-01-01","1200","VIIRS S-NPP"),
            registro("2026-01-01","1200","Landsat"),
            registro("2026-01-01","1200","VIIRS NOAA-21",lat=95),
        ])
        self.assertEqual(len(preparar_pareo(a)),1)
        self.assertTrue(emparejar_global(a).empty)

    def test_umbral_y_filtro_dia(self):
        a = pd.DataFrame([
            registro("2026-01-01","1200","MODIS"),
            registro("2026-01-01","1240","VIIRS S-NPP"),
        ])
        self.assertTrue(emparejar_global(a,ventana_min=30).empty)
        self.assertEqual(len(emparejar_global(a,ventana_min=45)),1)

    def test_deduplicacion_no_cuenta_replicas(self):
        data = pd.DataFrame([
            registro("2026-01-01","1200","MODIS",id_registro="m"),
            registro("2026-01-01","1200","MODIS",id_registro="m"),
            registro("2026-01-01","1205","VIIRS S-NPP",id_registro="v"),
        ])
        self.assertEqual(len(emparejar_global(data)),1)

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            emparejar_global(pd.DataFrame(),radio_km=0)
        with self.assertRaises(ValueError):
            emparejar_global(pd.DataFrame(),ventana_min=1441)


class TestCalidad(unittest.TestCase):
    def test_ausencia_no_equivale_a_cobertura(self):
        a = auditar_datos(pd.DataFrame())
        self.assertFalse(a["cobertura_verificada"])
        self.assertIn("no se puede inferir cobertura",lectura_diagnostica(a)[0])

    def test_filas_invalidas_y_repetidas(self):
        a = pd.DataFrame([
            registro("2026-01-01","1200","MODIS",id_registro="abc"),
            registro("2026-01-01","xx","VIIRS NOAA-20",lat=95,id_registro="abc"),
        ])
        r = auditar_datos(a)
        self.assertEqual(r["filas"],2)
        self.assertEqual(r["coordenadas_validas"],1)
        self.assertEqual(r["horarios_validos"],1)
        self.assertEqual(r["ids_repetidos"],1)

    def test_inventario_mes_ausente_no_significa_cero_fuego(self):
        a = pd.DataFrame([
            registro("2026-01-10","1230","MODIS",id_registro="m"),
            registro("2026-01-10","1240","VIIRS S-NPP",id_registro="v"),
        ])
        tabla = inventario_mensual(a,2026)
        self.assertEqual(len(tabla),24)
        febrero = tabla[tabla["Mes UTC"]=="2026-02"]
        self.assertTrue((febrero["Estado de datos"]=="SIN REGISTROS IMPORTADOS").all())
        self.assertTrue((tabla["Cobertura orbital verificada"]=="NO").all())


class TestImportacionNASA(unittest.TestCase):
    def test_identificacion_por_fila_para_archivo_viirs_mezclado(self):
        datos = pd.DataFrame({
            "instrument": ["VIIRS", "VIIRS", "VIIRS", "MODIS"],
            "satellite": ["N20", "N21", "SNPP", "A"],
        })
        etiquetas = clasificar_instrumentos(datos, "VIIRS_2026.csv")
        self.assertEqual(etiquetas.tolist(), [
            "VIIRS NOAA-20", "VIIRS NOAA-21", "VIIRS S-NPP", "MODIS",
        ])

    def test_satelite_prevalece_sobre_nombre_archivo(self):
        datos = pd.DataFrame({
            "instrument": ["VIIRS", "VIIRS"],
            "satellite": ["N21", "N20"],
        })
        etiquetas = clasificar_instrumentos(datos, "j1v-noaa20.csv")
        self.assertEqual(etiquetas.tolist(), ["VIIRS NOAA-21", "VIIRS NOAA-20"])

    def test_archivo_reconocible_sin_satelite(self):
        datos = pd.DataFrame({
            "instrument": ["VIIRS"],
            "satellite": [""],
        })
        etiquetas = clasificar_instrumentos(datos,"VIIRS_NOAA21_2026.csv")
        self.assertEqual(etiquetas.iloc[0], "VIIRS NOAA-21")

    def test_desconocido_no_se_inventa_instrumento(self):
        datos = pd.DataFrame({
            "instrument": ["ASTER", ""],
            "satellite": ["UNKNOWN", "UNKNOWN"],
        })
        etiquetas = clasificar_instrumentos(datos,"datos.csv")
        self.assertTrue(etiquetas.isna().all())


class TestWorldview(unittest.TestCase):
    def test_parametros_nasa_worldview(self):
        url = enlace_worldview("2026-01-15",-33.4,-56.1,0.2)
        obj=urlparse(url)
        self.assertEqual(obj.hostname,"worldview.earthdata.nasa.gov")
        q=parse_qs(obj.query)
        self.assertEqual(q["t"],["2026-01-15"])
        self.assertEqual(q["p"],["geographic"])
        self.assertEqual(len(q["v"][0].split(",")),4)

    def test_rechaza_entrada_invalida(self):
        with self.assertRaises(ValueError):
            enlace_worldview("2026-01-15",200,0)
        with self.assertRaises(ValueError):
            enlace_worldview("sin fecha",-33,-56)


if __name__ == "__main__":
    unittest.main()
