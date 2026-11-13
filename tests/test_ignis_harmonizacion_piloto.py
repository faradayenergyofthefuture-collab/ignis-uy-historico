"""Pruebas sintéticas del laboratorio experimental, no validación NASA."""
import unittest

import pandas as pd

from ignis_harmonizacion_piloto import evaluar_prototipo, validar_cobertura


def fixture(n_meses=12):
    datos, oportunidades = [], []
    for k in range(n_meses):
        y = 2023 + k // 12
        m = k % 12 + 1
        for dia in (3, 10, 17):
            fecha = f"{y:04d}-{m:02d}-{dia:02d}"
            oportunidades.extend([
                {"fecha_utc":fecha,"familia":"MODIS","oportunidades":1,"fuente":"TEST SINTÉTICO"},
                {"fecha_utc":fecha,"familia":"VIIRS","oportunidades":1,"fuente":"TEST SINTÉTICO"},
            ])
            for j in range(2):
                datos.append({"fecha":fecha,"instrumento":"MODIS","latitude":-33.0,"longitude":-56.0})
            for j in range(4):
                datos.append({"fecha":fecha,"instrumento":"VIIRS NOAA-20","latitude":-33.0,"longitude":-56.0})
    return pd.DataFrame(datos), pd.DataFrame(oportunidades)


class TestLaboratorio(unittest.TestCase):
    def test_cobertura_reglas_validacion(self):
        _, cobertura = fixture(2)
        self.assertEqual(len(validar_cobertura(cobertura)),12)
        with self.assertRaises(ValueError):
            validar_cobertura(pd.concat([cobertura,cobertura.iloc[[0]]],ignore_index=True))
        a = cobertura.copy()
        a.loc[0,"oportunidades"]=0
        with self.assertRaises(ValueError):
            validar_cobertura(a)
        b = cobertura.copy()
        b.loc[0,"fuente"]=""
        with self.assertRaises(ValueError):
            validar_cobertura(b)

    def test_ajuste_con_holdout_fuera_de_entrenamiento(self):
        datos,cobertura=fixture(12)
        r=evaluar_prototipo(datos,cobertura,bootstrap=100)
        self.assertEqual(r["estado"],"experimental")
        self.assertAlmostEqual(r["factor"],0.5,places=8)
        self.assertAlmostEqual(r["mae_experimental"],0.0,places=8)
        self.assertGreater(r["mae_original"],0)
        self.assertEqual(r["meses_entrenamiento"],8)
        self.assertEqual(r["meses_evaluacion"],4)
        self.assertEqual(r["meses"]["subconjunto"].tolist().count("evaluación"),4)
        self.assertFalse(r["calibracion_cientifica_validada"])
        self.assertFalse(r["cobertura_verificada_independientemente"])
        lo,hi=r["factor_bootstrap_95"]
        self.assertAlmostEqual(lo,0.5,places=8)
        self.assertAlmostEqual(hi,0.5,places=8)

    def test_datos_insuficientes_se_abstienen(self):
        datos,cobertura=fixture(4)
        r=evaluar_prototipo(datos,cobertura)
        self.assertEqual(r["estado"],"insuficiente")
        self.assertNotIn("factor",r)

    def test_no_inventa_ceros_sin_cobertura_ambos(self):
        datos,cobertura=fixture(12)
        sin_viirs=cobertura[cobertura.familia!="VIIRS"]
        r=evaluar_prototipo(datos,sin_viirs)
        self.assertEqual(r["estado"],"insuficiente")
        self.assertNotIn("factor",r)

    def test_referencia_no_puede_ser_cero(self):
        datos,cobertura=fixture(12)
        solo_viirs=datos[datos.instrumento.str.startswith("VIIRS")]
        r=evaluar_prototipo(solo_viirs,cobertura)
        self.assertEqual(r["estado"],"insuficiente")
        self.assertNotIn("factor",r)

    def test_rechaza_parametros_invalidos(self):
        d,c=fixture()
        with self.assertRaises(ValueError):
            evaluar_prototipo(d,c,min_meses=2)


if __name__=="__main__":
    unittest.main()
