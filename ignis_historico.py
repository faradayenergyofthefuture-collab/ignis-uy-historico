"""IGNIS UY Histórico v2.0 — prototipo de análisis reproducible NASA FIRMS.
El archivo maestro se exporta y se vuelve a importar; Streamlit Cloud no ofrece persistencia local garantizada.
"""
import io, json, zipfile, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

st.set_page_config(page_title='IGNIS UY | Histórico 2000–2026',page_icon='🛰️',layout='wide',initial_sidebar_state='collapsed')
BASE=Path(__file__).resolve().parent
REGIONES={
 'Uruguay (rectángulo aproximado)':(-35.2,-30.,-58.6,-53.),
 'Durazno':(-33.460,-33.280,-56.750,-56.440),
 'Cerro del Toro (Maldonado)':(-34.880,-34.840,-55.280,-55.230),
 'Treinta y Tres (zona Vergara)':(-32.985,-32.879,-54.069,-53.920),
 'Canelones (Atlántida/Salinas)':(-34.788,-34.724,-55.890,-55.810),
 'Lavalleja':(-34.116,-34.044,-54.940,-54.842),
 'Artigas':(-30.505,-30.443,-56.576,-56.499),
}
COLS=['fecha','latitude','longitude','instrumento','satellite','acq_time','frp','confidence','fuente','id_registro']
PALETTE=['#191d49','#422b87','#7646b3','#bf3f9d','#f46b64','#ffce62']

st.markdown('''<style>
.stApp {background:radial-gradient(ellipse at 88% 0%,#1b2355 0%,#0e1327 31%,#080d19 70%);color:#eef3ff}
.block-container{padding-top:1.3rem;padding-bottom:3rem;max-width:1600px}
h1,h2,h3{color:#f1f4ff!important;letter-spacing:-.025em}
h1{font-size:2.2rem!important}h2{font-size:1.45rem!important}
[data-testid="stMetric"]{background:linear-gradient(120deg,rgba(44,32,96,.7),rgba(20,36,69,.8));border:1px solid #444e85;border-radius:15px;padding:15px}
[data-testid="stMetricValue"]{color:#f8f6ff}
[data-testid="stTabs"] button{font-weight:600;color:#d7dcff}
button[data-baseweb="tab"][aria-selected="true"]{color:#b79bff!important;border-bottom-color:#9c83ff!important}
[data-testid="stAlert"]{border-radius:12px}
.hero{border:1px solid #3d5390;border-radius:20px;padding:18px 24px;margin-bottom:16px;background:linear-gradient(105deg,rgba(20,37,82,.94),rgba(42,31,94,.84),rgba(12,30,57,.86))}
.hero-title{font-weight:850;font-size:clamp(24px,3.2vw,42px);line-height:1.2;color:#fff}
.hero-sub{color:#bac7ef;font-size:14px;margin-top:7px}
.kicker{color:#ab9cff;font-size:13px;text-transform:uppercase;letter-spacing:2px;font-weight:700}
.small-note{font-size:13px;color:#aab6d5}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def parse_firms(blob, filename):
    result=[]; errors=[]; sources=[]
    try:
        if filename.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                entries=[(n,z.read(n)) for n in z.namelist() if n.lower().endswith('.csv') and not n.startswith('__MACOSX/')]
        else: entries=[(filename,blob)]
    except Exception as e: return pd.DataFrame(columns=COLS),[f'{filename}: ZIP no válido ({e})'],[]
    for name,raw in entries:
        try:
            df=pd.read_csv(io.BytesIO(raw),low_memory=False)
            df.columns=[x.strip().lower() for x in df.columns]
            if not {'latitude','longitude','acq_date'}.issubset(df):
                errors.append(f'{name}: falta latitude, longitude o acq_date');continue
            sat=df.get('satellite',pd.Series('',index=df.index)).fillna('').astype(str).str.upper()
            ins=df.get('instrument',pd.Series('',index=df.index)).fillna('').astype(str).str.upper()
            low=name.lower()
            if ins.eq('MODIS').all() or 'm-c61' in low or 'modis' in low:
                instrument='MODIS'
            elif ins.eq('VIIRS').all() or any(t in low for t in ('viirs','j1v','sv-c2')):
                if sat.isin(['N20','NOAA-20','J1']).all() or any(t in low for t in ('j1v','noaa20','noaa-20')):instrument='VIIRS NOAA-20'
                elif sat.isin(['SNPP','S-NPP','NPP']).all() or any(t in low for t in ('sv-c2','snpp','s-npp')):instrument='VIIRS S-NPP'
                else:instrument='VIIRS (plataforma no identificada)'
            else:
                errors.append(f'{name}: instrumento no identificado, omitido');continue
            out=pd.DataFrame(index=df.index)
            out['fecha']=pd.to_datetime(df.acq_date,utc=True,errors='coerce').dt.strftime('%Y-%m-%d')
            out['latitude']=pd.to_numeric(df.latitude,errors='coerce')
            out['longitude']=pd.to_numeric(df.longitude,errors='coerce')
            out['instrumento']=instrument
            out['satellite']=sat
            out['acq_time']=df.get('acq_time',pd.Series('',index=df.index)).fillna('').astype(str).str.replace(r'\.0$','',regex=True).str.zfill(4)
            out['frp']=pd.to_numeric(df.get('frp',pd.Series(np.nan,index=df.index)),errors='coerce')
            out['confidence']=df.get('confidence',pd.Series('',index=df.index)).fillna('').astype(str)
            out['fuente']=filename+' :: '+name
            out=out.dropna(subset=['fecha','latitude','longitude'])
            out=out[out.latitude.between(-90,90)&out.longitude.between(-180,180)].copy()
            # Mantener identidad estable entre cargas, sin usar el nombre del ZIP.
            identity=out[['fecha','latitude','longitude','instrumento','satellite','acq_time','frp','confidence']].fillna('').astype(str).agg('|'.join,axis=1)
            out['id_registro']=identity.map(lambda t:hashlib.sha256(t.encode()).hexdigest()[:24])
            result.append(out[COLS]);sources.append({'archivo':filename,'csv':name,'sensor':instrument,'registros_validos':len(out),'primer_dia':out.fecha.min() if len(out) else '', 'ultimo_dia':out.fecha.max() if len(out) else '', 'sha256':hashlib.sha256(raw).hexdigest()})
        except Exception as e: errors.append(f'{name}: error ({type(e).__name__}: {e})')
    return (pd.concat(result,ignore_index=True) if result else pd.DataFrame(columns=COLS)),errors,sources

def normalizar(df):
    if df is None or df.empty:return pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in df:df[c]=np.nan if c in ('latitude','longitude','frp') else ''
    df=df[COLS].copy()
    df['fecha']=pd.to_datetime(df.fecha,utc=True,errors='coerce').dt.strftime('%Y-%m-%d')
    for col in ['latitude','longitude','frp']:df[col]=pd.to_numeric(df[col],errors='coerce')
    df=df.dropna(subset=['fecha','latitude','longitude'])
    df=df.drop_duplicates('id_registro',keep='first').reset_index(drop=True)
    return df

@st.cache_data(show_spinner=False)
def leer_maestro(blob):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if 'observaciones.csv' not in z.namelist():raise ValueError('Falta observaciones.csv')
            df=pd.read_csv(io.BytesIO(z.read('observaciones.csv')),dtype={'acq_time':str,'id_registro':str},low_memory=False)
            info=json.loads(z.read('manifest.json')) if 'manifest.json' in z.namelist() else {}
        return normalizar(df), info, None
    except Exception as e:return pd.DataFrame(columns=COLS),{},str(e)

def crear_maestro(df):
    bio=io.BytesIO()
    manifest={'proyecto':'IGNIS UY','version_formato':'2','registros':len(df),'advertencia':'Observaciones FIRMS, no incendios confirmados. Los ZIP no se conservan en este archivo.'}
    with zipfile.ZipFile(bio,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('observaciones.csv',df.to_csv(index=False))
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return bio.getvalue()

def filtrar(df, region, sensores):
    a,b,c,d=REGIONES[region]
    return df[df.latitude.between(a,b)&df.longitude.between(c,d)&df.instrumento.isin(sensores)].copy()

def dotar_tiempo(df):
    d=df.copy();t=pd.to_datetime(d.fecha,errors='coerce',utc=True)
    d['anio']=t.dt.year;d['mes']=t.dt.month;d['dia']=t.dt.strftime('%Y-%m-%d');d['temporada']=np.where(d.mes==12,d.anio+1,d.anio)
    return d

def heatmap_mensual(df, nombre):
    if df.empty:st.info('Todavía no hay observaciones para este instrumento.');return
    counts=df.groupby(['anio','mes']).size().reset_index(name='total')
    years=range(2000,2027)
    matrix=counts.pivot(index='mes',columns='anio',values='total').reindex(index=range(1,13),columns=years)
    # NaN intentionally denotes no uploaded evidence for that month; never infer zero coverage.
    fig=go.Figure(go.Heatmap(z=matrix.values,x=[str(y) for y in years],y=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Set','Oct','Nov','Dic'],colorscale=[[0,'#302355'],[.25,'#6240a4'],[.5,'#b944a5'],[.75,'#ef777b'],[1,'#ffdb68']],colorbar={'title':'Registros'},hovertemplate='Año %{x} · %{y}<br>Detecciones %{z}<extra></extra>',xgap=2,ygap=2))
    fig.update_layout(title=nombre,template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',height=440,margin=dict(l=25,r=15,t=50,b=30),xaxis=dict(tickangle=-55),yaxis=dict(autorange='reversed'))
    st.plotly_chart(fig,use_container_width=True)
    st.caption('Celdas vacías = no hay detecciones en el material cargado; la cobertura efectiva del satélite no está verificada. No se interpretan automáticamente como cero actividad.')

def resumen_estacional(df, sensor):
    # Compare same month and instrument, across loaded calendar years; 3-year minimum.
    z=df[df.instrumento==sensor]
    m=z.groupby(['anio','mes']).size().rename('n').reset_index()
    warnings=[]
    for _,r in m.iterrows():
        historical=m[(m.mes==r.mes)&(m.anio!=r.anio)]
        if len(historical)<3:continue
        med=float(historical.n.median())
        if r.n>=5 and r.n>=2*max(med,1):
            warnings.append({'Año':int(r.anio),'Mes':int(r.mes),'Sensor':sensor,'Detecciones':int(r.n),'Mediana otros años':med,'Índice frente a mediana':round(r.n/max(med,1),2)})
    return warnings

logo=BASE/'logo_ignis.png'
header_left,header_right=st.columns([1,7])
with header_left:
    if logo.exists():st.image(str(logo),width=115)
    else:st.write('🛰️')
with header_right:
    st.markdown('<div class="hero"><div class="kicker">IGNIS UY · NASA Space Apps Challenge 2026</div><div class="hero-title">Histórico de actividad térmica</div><div class="hero-sub">Armonización exploratoria MODIS–VIIRS · Uruguay 2000–2026 · análisis basado exclusivamente en datos incorporados</div></div>',unsafe_allow_html=True)

st.info('Los registros son anomalías térmicas, no incendios confirmados. Este prototipo no proporciona alertas operativas ni mide superficies quemadas.')
tabs=st.tabs(['📂 Carga de datos','📊 Resumen NASA por año','📚 Histórico 2000–2026','🗺️ Mapa de Uruguay','⚠️ Alertas y trazabilidad','🗓️ Calendario final'])
with tabs[0]:
    st.subheader('Incorporación al histórico')
    st.write('Cargá ZIP/CSV FIRMS de una o varias temporadas. Para **guardar lo acumulado entre sesiones**, descargá el **Maestro IGNIS** actualizado y volvé a importarlo la próxima vez. Los datos **no se guardan automáticamente en la nube**.')
    master=st.file_uploader('1 · Maestro IGNIS anterior (opcional, archivo ZIP exportado por esta aplicación)',type=['zip'],key='master')
    rawfiles=st.file_uploader('2 · Nuevos ZIP o CSV NASA FIRMS (varios simultáneamente)',type=['zip','csv'],accept_multiple_files=True,key='raws')
    base=pd.DataFrame(columns=COLS)
    if master:
        base,meta,error=leer_maestro(master.getvalue())
        if error:st.error('No se pudo importar el maestro: '+error)
        else:st.success(f'Maestro recuperado: {len(base):,} registros')
    inputs=[];inventory=[];problems=[]
    for a in (rawfiles or []):
        new,issues,sources=parse_firms(a.getvalue(),a.name)
        inputs.append(new);inventory.extend(sources);problems.extend(issues)
    if inputs:
        combined=normalizar(pd.concat([base]+inputs,ignore_index=True))
    else:combined=normalizar(base)
    for problem in problems:st.warning(problem)
    aa,bb,cc=st.columns(3)
    aa.metric('Registros del maestro anterior',f'{len(base):,}')
    bb.metric('Observaciones nuevas, netas',f'{max(len(combined)-len(base),0):,}')
    cc.metric('Registros acumulados, sin duplicados',f'{len(combined):,}')
    if inventory:st.dataframe(pd.DataFrame(inventory),use_container_width=True,hide_index=True)
    if len(combined):
        st.download_button('⬇️ Descargar Maestro IGNIS actualizado (guardar para la próxima sesión)',crear_maestro(combined),file_name='IGNIS_MAESTRO_HISTORICO.zip',mime='application/zip',type='primary')
        st.caption('Guarda este archivo en tu computadora. El ZIP maestro contiene observaciones normalizadas, no los ZIP NASA originales: conservá también los originales como respaldo documental.')
    else:st.info('Para comenzar, cargá uno de los archivos MODIS de 2000. También podés importar un maestro ya construido.')

# Widgets outside tabs only depend on the current upload set. The corresponding results are shown within tabs.
if 'combined' not in locals():combined=pd.DataFrame(columns=COLS)
if len(combined):
    st.markdown('#### Controles compartidos de análisis')
    c1,c2=st.columns([2,3])
    with c1:reg=st.selectbox('Región / caso',list(REGIONES),key='region')
    with c2:sens=st.multiselect('Familias instrumentales',sorted(combined.instrumento.dropna().unique()),default=sorted(combined.instrumento.dropna().unique()),key='sensores')
    sample=dotar_tiempo(filtrar(combined,reg,sens))
    years=sorted(sample.anio.dropna().astype(int).unique()) if len(sample) else []
    selected=st.selectbox('Año a inspeccionar',years,index=len(years)-1) if years else None
else:sample=pd.DataFrame();selected=None;reg=list(REGIONES)[0];sens=[]

with tabs[1]:
    st.subheader('Resumen del año seleccionado · lo esencial del desafío NASA')
    if sample.empty:st.info('Cargá datos en la primera pestaña; elegí la región para generar el resumen.')
    else:
        yr=sample[sample.anio==selected];a,b,c=st.columns(3)
        a.metric(f'Detecciones {selected}',f'{len(yr):,}')
        b.metric('Días con observaciones',yr.dia.nunique())
        c.metric('Instrumentos detectados',yr.instrumento.nunique())
        st.dataframe(yr.groupby(['mes','instrumento']).size().reset_index(name='registros').rename(columns={'mes':'Mes','instrumento':'Sensor'}),use_container_width=True,hide_index=True)
        st.caption('Estos números se refieren al año calendario elegido y a los archivos suministrados. No son tasas de incendios ni datos normalizados por cobertura.')
        st.download_button('Descargar CSV del año',yr[COLS].to_csv(index=False).encode('utf-8-sig'),file_name=f'IGNIS_{selected}_registros.csv')

with tabs[2]:
    st.subheader('Registro histórico acumulado')
    if sample.empty:st.info('Importá el maestro o cargá ZIP de NASA FIRMS para visualizar el histórico.')
    else:
        x,y,z=st.columns(3);x.metric('Registros en el recorte',f'{len(sample):,}');y.metric('Años con registros',sample.anio.nunique());z.metric('Sensores presentes',sample.instrumento.nunique())
        sensors=sorted(sample.instrumento.unique())
        for sensor in sensors:heatmap_mensual(sample[sample.instrumento==sensor],sensor)
        st.subheader('Temporadas estivales · diciembre anterior + enero/febrero')
        summer=sample[sample.mes.isin([12,1,2])]
        ss=summer.groupby(['temporada','instrumento']).size().reset_index(name='detecciones')
        if len(ss):
            fig=px.bar(ss,x='temporada',y='detecciones',color='instrumento',barmode='group',template='plotly_dark',labels={'temporada':'Temporada estival','detecciones':'Registros'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(ss,use_container_width=True,hide_index=True)
            st.download_button('Descargar resumen por temporada',ss.to_csv(index=False).encode('utf-8-sig'),file_name='IGNIS_temporadas.csv')
        st.warning('La existencia de registros no garantiza cobertura completa. No se comparan directamente los recuentos MODIS y VIIRS ni se estima una tendencia climática validada.')

with tabs[3]:
    st.subheader('Mapa de detecciones térmicas de Uruguay')
    if sample.empty:st.info('Cargá datos antes de abrir el mapa.')
    else:
        periodo=st.radio('Vista', ['Todo el histórico cargado','Año seleccionado'],horizontal=True)
        mapped=sample if periodo=='Todo el histórico cargado' else sample[sample.anio==selected]
        st.caption('Mapa de puntos dentro del rectángulo aproximado de Uruguay; puede incluir ubicaciones fuera de la frontera. No representa incendios ni áreas quemadas.')
        if len(mapped):
            points=mapped[['latitude','longitude']].dropna()
            if len(points)>15000:
                points=points.sample(15000,random_state=42)
                st.caption('Visualización limitada a 15.000 observaciones seleccionadas reproduciblemente; los conteos se mantienen completos.')
            fmap=folium.Map(location=[-32.9,-56],zoom_start=7,tiles='CartoDB dark_matter')
            HeatMap(points.values.tolist(),radius=13,blur=18,min_opacity=.35).add_to(fmap)
            st_folium(fmap,height=535,returned_objects=[],use_container_width=True)
        st.caption('Densidad visual de registros, sin corrección por resolución, cobertura o revisitas de los distintos sensores.')

with tabs[4]:
    st.subheader('Actividad inusual exploratoria y trazabilidad documental')
    if sample.empty:st.info('Se requieren registros históricos para analizar condiciones inusuales.')
    else:
        alerts=[]
        for sensor in sorted(sample.instrumento.unique()):alerts+=resumen_estacional(sample,sensor)
        if alerts:
            alert_df=pd.DataFrame(alerts).sort_values(['Año','Mes'],ascending=False)
            st.warning(f'{len(alert_df)} candidatos de actividad elevada respecto de la mediana mensual de otros años con registros. No son alertas operativas.')
            st.dataframe(alert_df,use_container_width=True,hide_index=True)
        else:st.info('No se identificaron candidatos con el criterio piloto, o faltan años comparables. Esto NO significa ausencia de riesgo.')
        st.caption('Criterio: mismo sensor y mes, al menos 3 otros años con detecciones, mínimo 5 registros y al menos 2 veces la mediana. SIN normalización por cobertura: úsese solo como señal preliminar.')
    case_path=BASE/'biblioteca_ignis'/'evidencias.json'
    if case_path.exists():
        try:
            evidence=json.loads(case_path.read_text(encoding='utf-8'))
            st.markdown('#### Catálogo documental independiente — casos de 2023')
            st.caption('Este catálogo corresponde SOLO a expedientes de 2023; no constituye evidencia de archivos de otros años.')
            options=evidence.get('casos',[])
            if options:
                choice=st.selectbox('Caso documentado',range(len(options)),format_func=lambda k:options[k].get('nombre','Caso '+str(k+1)))
                case=options[choice]
                st.write('**Región:**',case.get('nombre','—'),'· **Fechas UTC:**',', '.join(case.get('fechas_utc',[])))
                st.write(case.get('resumen','Ver los reportes asociados en el documento original.'))
                st.json({'recuentos_guía_2023':case.get('esperados',{}),'aclaracion':'Los recuentos guía de 2023 no proceden de la carga actual.'},expanded=False)
        except Exception as e:st.warning(f'Catálogo no disponible: {e}')

with tabs[5]:
    st.subheader('Calendario final de actividad térmica observada')
    if sample.empty:st.info('El calendario aparecerá al cargar datos.')
    else:
        st.write('Calendario histórico por meses y sensor. Incluye solamente los datos que incorporaste al maestro.')
        for sensor in sorted(sample.instrumento.unique()):heatmap_mensual(sample[sample.instrumento==sensor],sensor)
        if selected is not None:
            st.subheader(f'Calendario diario · {selected}')
            daily=sample[sample.anio==selected].groupby(['dia','instrumento']).size().reset_index(name='detecciones')
            st.dataframe(daily,use_container_width=True,hide_index=True)
            st.download_button('Descargar calendario diario CSV',daily.to_csv(index=False).encode('utf-8-sig'),file_name=f'IGNIS_calendario_{selected}.csv')
        st.caption('Para comparar un mes actual con su mediana histórica hacen falta meses con observaciones comparables, mismos instrumentos y una evaluación de cobertura. No se interpreta una ausencia de registros como ausencia de fuego.')

st.divider()
st.caption('IGNIS UY Histórico · prototipo de investigación · entradas NASA FIRMS · evidencia documental del equipo separada · respaldo manual del maestro obligatorio.')
