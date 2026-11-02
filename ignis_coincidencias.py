"""IGNIS V3.7: pares exploratorios entre MODIS y VIIRS.
No calibra sensibilidad, cobertura ni FRP; no confirma un mismo incendio.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

COLUMNAS=['fecha_utc','modis','viirs','distancia_km','diferencia_min','lat_modis','lon_modis','lat_viirs','lon_viirs','frp_modis','frp_viirs']

def _minuto(v):
    if pd.isna(v): return np.nan
    try:
        h=int(float(v)); hh,mm=divmod(h,100)
        if 0<=hh<=23 and 0<=mm<=59:return hh*60+mm
    except (ValueError,TypeError,OverflowError):pass
    return np.nan

def _xyz(lat,lon):
    a=np.radians(lat); b=np.radians(lon)
    return np.column_stack([np.cos(a)*np.cos(b),np.cos(a)*np.sin(b),np.sin(a)])

def emparejar(df, ano=None, radio_km=5.0, ventana_min=30):
    """Un par como máximo por observación dentro de cada comparación MODIS-VIIRS.
    Opera en UTC y cada día, con distancia geodésica aproximada (cuerda terrestre).
    La coincidencia no implica equivalencia instrumental ni evento compartido.
    """
    if not 0 < float(radio_km) <= 50: raise ValueError('radio_km entre 0 y 50')
    if not 0 <= int(ventana_min) <= 1440: raise ValueError('ventana_min entre 0 y 1440')
    if df is None or df.empty: return pd.DataFrame(columns=COLUMNAS)
    z=df.copy()
    z['fecha_utc']=pd.to_datetime(z['fecha'],utc=True,errors='coerce').dt.strftime('%Y-%m-%d')
    z['latitude']=pd.to_numeric(z['latitude'],errors='coerce')
    z['longitude']=pd.to_numeric(z['longitude'],errors='coerce')
    z['minuto']=z['acq_time'].map(_minuto) if 'acq_time' in z else np.nan
    z=z.dropna(subset=['fecha_utc','latitude','longitude','minuto','instrumento'])
    z=z[z.latitude.between(-90,90)&z.longitude.between(-180,180)]
    if ano is not None: z=z[z.fecha_utc.str[:4]==str(int(ano))]
    if z.empty:return pd.DataFrame(columns=COLUMNAS)
    z['familia']=np.where(z.instrumento.astype(str).str.upper().str.startswith('MODIS'),'MODIS','VIIRS')
    records=[]
    # Deduplicación no transitiva: MODIS--VIIRS S-NPP y MODIS--VIIRS NOAA-20 por separado.
    for day, g in z.groupby('fecha_utc',sort=True):
        ma=g[g.familia=='MODIS']; vb=g[g.familia=='VIIRS']
        if ma.empty or vb.empty:continue
        for nombre,vi in vb.groupby('instrumento',sort=True):
            a=ma.reset_index(drop=True); b=vi.reset_index(drop=True)
            xyz1=_xyz(a.latitude.to_numpy(),a.longitude.to_numpy()); xyz2=_xyz(b.latitude.to_numpy(),b.longitude.to_numpy())
            # Radio angular -> distancia euclídea de cuerda sobre esfera unitaria.
            chord=2*np.sin(float(radio_km)/(2*6371.0088))
            pairs=cKDTree(xyz1).query_ball_tree(cKDTree(xyz2),r=chord)
            options=[]
            for i, js in enumerate(pairs):
                for j in js:
                    diff=abs(float(a.iloc[i].minuto)-float(b.iloc[j].minuto))
                    if diff>ventana_min:continue
                    d=6371.0088*2*np.arcsin(min(1.,np.linalg.norm(xyz1[i]-xyz2[j])/2))
                    options.append((diff,d,i,j))
            used_a=set(); used_b=set()
            for diff,d,i,j in sorted(options):
                if i in used_a or j in used_b:continue
                used_a.add(i);used_b.add(j)
                x=a.iloc[i];y=b.iloc[j]
                records.append([day,str(x.instrumento),str(y.instrumento),round(float(d),3),int(diff),float(x.latitude),float(x.longitude),float(y.latitude),float(y.longitude),x.get('frp',np.nan),y.get('frp',np.nan)])
    return pd.DataFrame(records,columns=COLUMNAS)

def resumir_pares(pares):
    if pares.empty:return pd.DataFrame(columns=['Mes','Par instrumental','Pares','Distancia mediana (km)','Diferencia mediana (min)'])
    z=pares.copy(); z['Mes']=pd.to_datetime(z.fecha_utc).dt.strftime('%Y-%m');z['Par instrumental']=z.modis+' / '+z.viirs
    return z.groupby(['Mes','Par instrumental']).agg(Pares=('distancia_km','size'),**{'Distancia mediana (km)':('distancia_km','median'),'Diferencia mediana (min)':('diferencia_min','median')}).reset_index().round(2)
