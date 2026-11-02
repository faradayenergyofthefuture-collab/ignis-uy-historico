
"""Generador del informe científico IGNIS UY. No modifica datos ni la lógica de ingestión."""
import io, json, calendar
from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.path import Path as MPath
from scipy.ndimage import gaussian_filter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from PIL import Image as PILImage

BASE=Path(__file__).resolve().parent
MONTHS=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
CMAP=LinearSegmentedColormap.from_list('ignis',['#42206a','#8440a9','#dc4b95','#ff975a','#ffe36c'])
BG='#081425'; PANEL='#11203b'; PANEL2='#172949'; WHITE='#eef4ff'; SOFT='#b8c9ee'; CYAN='#67d6ff'; VIOLET='#d9c7ff'


def image_asset(name,w=2.7*cm):
    p=BASE/name
    if not p.exists():
        return None
    with PILImage.open(p) as im:
        aw,ah=im.size
    return RLImage(str(p),width=w,height=w*ah/aw,kind='proportional')


def plot_buffer(fig):
    buffer=io.BytesIO()
    fig.savefig(buffer,format='png',dpi=180,bbox_inches='tight',facecolor=BG)
    plt.close(fig)
    buffer.seek(0)
    return buffer


def family_from_sensor(series):
    s=series.astype(str).str.upper()
    return np.where(s.str.startswith('VIIRS'),'VIIRS','MODIS')


def ensure_time_cols(df):
    z=df.copy()
    if 'anio' not in z.columns or 'mes' not in z.columns or 'dia' not in z.columns:
        t=pd.to_datetime(z['fecha'],errors='coerce',utc=True)
        z['anio']=t.dt.year
        z['mes']=t.dt.month
        z['dia']=t.dt.strftime('%Y-%m-%d')
    return z


def compress_periods(df):
    if df.empty:
        return []
    z=ensure_time_cols(df)
    by_year=z.groupby('anio')['instrumento'].apply(lambda s:' + '.join(sorted(set(map(str,s)))))
    periods=[]; start=prev=sig=None
    for year, signature in by_year.items():
        year=int(year)
        if start is None:
            start=prev=year; sig=signature; continue
        if year==prev+1 and signature==sig:
            prev=year; continue
        periods.append({'Periodo':f'{start}–{prev}' if start!=prev else str(start),'Configuración instrumental':sig})
        start=prev=year; sig=signature
    if start is not None:
        periods.append({'Periodo':f'{start}–{prev}' if start!=prev else str(start),'Configuración instrumental':sig})
    return periods


def resumen_armonizacion(df, ano=None, grid_deg=0.20):
    z=ensure_time_cols(df)
    if z.empty:
        return {'has_both':False,'overlap_years':[], 'overlap_months':pd.DataFrame(), 'coincident_cells':pd.DataFrame(), 'periods':[]}
    z=z.copy()
    z['familia']=family_from_sensor(z['instrumento'])
    counts=z.groupby('familia').size().to_dict()
    has_both=counts.get('MODIS',0)>0 and counts.get('VIIRS',0)>0
    annual=z.groupby(['anio','familia']).size().unstack(fill_value=0) if len(z) else pd.DataFrame()
    overlap_years=[]
    if not annual.empty:
        overlap=annual[(annual.get('MODIS',0)>0)&(annual.get('VIIRS',0)>0)]
        overlap_years=[int(y) for y in overlap.index.tolist()]
    periods=compress_periods(z)
    if not has_both:
        return {'has_both':False,'overlap_years':overlap_years,'overlap_months':pd.DataFrame(), 'coincident_cells':pd.DataFrame(), 'periods':periods}

    q=z[['anio','mes','dia','latitude','longitude','familia']].dropna().copy()
    q['latitude']=pd.to_numeric(q['latitude'],errors='coerce')
    q['longitude']=pd.to_numeric(q['longitude'],errors='coerce')
    q=q.dropna(subset=['latitude','longitude'])
    q['grid_lat']=np.round(q['latitude']/grid_deg).astype(int)
    q['grid_lon']=np.round(q['longitude']/grid_deg).astype(int)
    cells=q.groupby(['anio','mes','dia','grid_lat','grid_lon','familia']).size().reset_index(name='n')
    wide=cells.pivot_table(index=['anio','mes','dia','grid_lat','grid_lon'],columns='familia',values='n',aggfunc='sum',fill_value=0).reset_index()
    wide['coincidencia_modis_viirs']=(wide.get('MODIS',0)>0)&(wide.get('VIIRS',0)>0)
    coinc=wide[wide['coincidencia_modis_viirs']].copy()
    overlap_months=z.groupby(['anio','mes','familia']).size().unstack(fill_value=0)
    overlap_months=overlap_months[(overlap_months.get('MODIS',0)>0)&(overlap_months.get('VIIRS',0)>0)].reset_index()
    if ano is not None:
        overlap_months=overlap_months[overlap_months['anio']==int(ano)].copy()
        coinc=coinc[coinc['anio']==int(ano)].copy()
    coinc_monthly=coinc.groupby(['anio','mes']).size().reset_index(name='celdas_coincidentes') if len(coinc) else pd.DataFrame(columns=['anio','mes','celdas_coincidentes'])
    return {'has_both':True,'overlap_years':overlap_years,'overlap_months':overlap_months,'coincident_cells':coinc_monthly,'periods':periods}


def calendar_figure(df):
    counts=df.groupby(['anio','mes']).size()
    years=list(range(2000,2027)); cells=np.full((12,len(years)),np.nan)
    for (y,m),n in counts.items():
        if 2000<=int(y)<=2026 and 1<=int(m)<=12:
            cells[int(m)-1,int(y)-2000]=n
    fig,ax=plt.subplots(figsize=(10.5,3.6),facecolor=BG)
    ax.set_facecolor(BG)
    cmap=CMAP.copy(); cmap.set_bad('#122034')
    image=ax.imshow(np.ma.masked_invalid(cells),aspect='auto',cmap=cmap,interpolation='nearest')
    ax.set_xticks(range(0,27,2),years[::2],fontsize=7,color=WHITE)
    ax.set_yticks(range(12),[x[:3] for x in MONTHS],fontsize=8,color=WHITE)
    ax.tick_params(length=0,colors=WHITE)
    ax.set_title('Calendario histórico de registros por mes (archivos incorporados)',fontsize=11,pad=10,color=WHITE)
    for spine in ax.spines.values(): spine.set_color('#35527b')
    cbar=fig.colorbar(image,ax=ax,shrink=.8,label='Registros')
    cbar.ax.yaxis.label.set_color(WHITE); cbar.ax.tick_params(colors=WHITE)
    fig.tight_layout()
    return plot_buffer(fig)


def daily_calendar_figure(year, ano):
    if year.empty:
        return None
    dates = pd.to_datetime(year['dia'], errors='coerce').dropna()
    if dates.empty:
        return None
    daily = dates.dt.date.value_counts().to_dict()
    months = sorted(set(dates.dt.month))
    cols = min(3, len(months))
    rows = (len(months) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(10.2, 2.35 * rows + .3), squeeze=False, facecolor=BG)
    maximum = max(daily.values()) if daily else 1
    norm = Normalize(vmin=1, vmax=max(2, maximum))
    for k, month in enumerate(months):
        ax = axes[k // cols][k % cols]
        ax.set_xlim(0, 7); ax.set_ylim(7.0, -.7); ax.axis('off')
        ax.set_facecolor(BG)
        ax.set_title(f'{MONTHS[month-1]} {ano}', loc='left', fontsize=11, fontweight='bold', color=WHITE, pad=5)
        for j, name in enumerate(['L', 'M', 'X', 'J', 'V', 'S', 'D']):
            ax.text(j+.5, .35, name, ha='center', va='center', fontsize=8, color=SOFT)
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(int(ano), int(month))
        for wi, week in enumerate(weeks):
            for di, day in enumerate(week):
                if day.month != month:
                    continue
                n = daily.get(day)
                face = CMAP(norm(n)) if n is not None else '#122034'
                rect = plt.Rectangle((di+.055, wi+1.05), .89, .84, facecolor=face, edgecolor='#29456d', linewidth=.6)
                ax.add_patch(rect)
                ax.text(di+.5, wi+1.33, str(day.day), ha='center', va='center', fontsize=7.3,
                        color='white' if n is not None else SOFT)
                if n is not None:
                    ax.text(di+.5, wi+1.70, str(n), ha='center', va='center', fontsize=9,
                            fontweight='bold', color='white')
    for k in range(len(months), rows*cols):
        axes[k // cols][k % cols].axis('off')
    fig.tight_layout(pad=1.3)
    return plot_buffer(fig)


def trend_figure(df):
    agg=df.groupby(['anio','instrumento']).size().unstack(fill_value=0)
    fig,ax=plt.subplots(figsize=(10,3.6),facecolor=BG)
    ax.set_facecolor(BG)
    if not agg.empty:
        agg.index=agg.index.astype(int).astype(str)
        palette=['#5d7fe6','#ff7e96','#9d74e5','#f1bf66'][:len(agg.columns)]
        agg.plot.bar(ax=ax,width=.75,rot=45,color=palette)
    ax.set_ylabel('Registros FIRMS',color=WHITE)
    ax.set_xlabel('Año presente en archivos',color=WHITE)
    ax.grid(axis='y',alpha=.18,color='#5677a5')
    ax.legend(fontsize=7,loc='upper left',facecolor=BG,edgecolor='#35527b',labelcolor=WHITE)
    ax.tick_params(colors=WHITE,labelsize=7)
    ax.set_title('Conteo anual por familia instrumental (no normalizado)',fontsize=10,color=WHITE)
    for spine in ax.spines.values(): spine.set_color('#35527b')
    fig.tight_layout()
    return plot_buffer(fig)


def map_figure(df):
    raw=json.loads((BASE/'uruguay_contorno.geojson').read_text(encoding='utf-8'))
    geometry=raw['features'][0]['geometry']; ring=geometry['coordinates'][0] if geometry['type']=='Polygon' else geometry['coordinates'][0][0]
    border=np.asarray(ring,dtype=float)
    clean=df[['longitude','latitude']].apply(pd.to_numeric,errors='coerce').dropna()
    clean=clean[clean.longitude.between(-59,-52)&clean.latitude.between(-36,-29)]
    if clean.empty:
        return None
    xedges=np.linspace(-58.8,-52.8,125); yedges=np.linspace(-35.4,-29.8,125)
    hist,*_=np.histogram2d(clean.longitude,clean.latitude,bins=[xedges,yedges]); dense=gaussian_filter(hist.T,sigma=2.5)
    x=(xedges[1:]+xedges[:-1])/2; y=(yedges[1:]+yedges[:-1])/2
    xx,yy=np.meshgrid(x,y); mask=MPath(border).contains_points(np.c_[xx.ravel(),yy.ravel()]).reshape(xx.shape)
    dense[~mask]=np.nan; dense[dense<.06]=np.nan
    fig,ax=plt.subplots(figsize=(9.4,6.0),facecolor=BG); ax.set_facecolor('#0b1230')
    ax.fill(border[:,0],border[:,1],color='#211c4a',alpha=.9)
    img=ax.imshow(dense,extent=[xedges[0],xedges[-1],yedges[0],yedges[-1]],origin='lower',cmap=CMAP,interpolation='bilinear',alpha=.95,aspect='auto')
    plot=clean.sample(min(1800,len(clean)),random_state=42)
    ax.scatter(plot.longitude,plot.latitude,s=2.4,color='#e8eaff',alpha=.4,zorder=3)
    ax.plot(border[:,0],border[:,1],color='#a5cfff',lw=1.5,zorder=4)
    for name,lon,lat in [('Artigas',-56.0,-30.45),('Durazno',-56.52,-33.22),('Canelones',-56.28,-34.55),('Maldonado',-54.95,-34.73),('Rocha',-54.32,-34.12)]:
        ax.text(lon,lat,name,color='white',fontsize=7,bbox=dict(facecolor='#14142f',alpha=.65,edgecolor='none',pad=2))
    ax.set(xlim=(-58.85,-52.65),ylim=(-35.45,-29.75),xlabel='Longitud',ylabel='Latitud')
    ax.tick_params(colors=WHITE,labelsize=7)
    for spine in ax.spines.values(): spine.set_color('#35527b')
    cbar=fig.colorbar(img,ax=ax,shrink=.7,label='Densidad visual relativa (no calibrada)')
    cbar.ax.yaxis.label.set_color(WHITE); cbar.ax.tick_params(colors=WHITE)
    fig.tight_layout()
    return plot_buffer(fig)



def alert_figure(candidates):
    if not candidates:
        return None
    a=pd.DataFrame(candidates).groupby('Año').size()
    fig,ax=plt.subplots(figsize=(10,2.25),facecolor=BG)
    ax.set_facecolor(BG)
    years=list(range(int(a.index.min()),int(a.index.max())+1))
    ax.bar(years,[int(a.get(y,0)) for y in years],color='#bd80e6',width=.68)
    ax.set_ylabel('Candidatos',color=WHITE)
    ax.set_title('Candidatos exploratorios históricos por año (criterio piloto)',fontsize=10,color=WHITE)
    ax.set_xticks(years[::max(1,len(years)//12)]); ax.tick_params(axis='x',labelrotation=40)
    ax.tick_params(colors=WHITE,labelsize=8)
    ax.grid(axis='y',alpha=.2,color=SOFT)
    fig.tight_layout()
    return plot_buffer(fig)

def banner_table(text):
    tb=Table([[Paragraph(text, getSampleStyleSheet()['BodyText'])]], colWidths=[16.3*cm])
    tb.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#13284b')),
        ('BOX',(0,0),(-1,-1),0.6,colors.HexColor('#35527b')),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
    ]))
    return tb


def generar_informe_pdf(datos,ano,region,sensores,alertas_func=None):
    df=ensure_time_cols(datos.copy())
    year=df[df.anio==ano].copy()
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=1.55*cm,rightMargin=1.55*cm,topMargin=1.45*cm,bottomMargin=1.55*cm,title='IGNIS UY - Informe científico de actividad térmica',author='Proyecto IGNIS UY')
    S=getSampleStyleSheet()
    S.add(ParagraphStyle(name='PaperT',parent=S['Title'],fontName='Helvetica-Bold',fontSize=20,leading=24,textColor=colors.HexColor(WHITE),alignment=TA_CENTER,spaceAfter=6))
    S.add(ParagraphStyle(name='PaperSub',parent=S['Normal'],alignment=TA_CENTER,fontSize=10,leading=13,textColor=colors.HexColor(SOFT),spaceAfter=8))
    S.add(ParagraphStyle(name='PaperH',parent=S['Heading2'],fontSize=13,leading=16,textColor=colors.HexColor(CYAN),spaceBefore=12,spaceAfter=6,keepWithNext=True))
    S.add(ParagraphStyle(name='PaperBody',parent=S['BodyText'],fontSize=9.1,leading=13.1,alignment=TA_JUSTIFY,spaceAfter=7,textColor=colors.HexColor(WHITE)))
    S.add(ParagraphStyle(name='PaperBodySoft',parent=S['BodyText'],fontSize=8.7,leading=12.8,alignment=TA_JUSTIFY,spaceAfter=7,textColor=colors.HexColor(SOFT)))
    S.add(ParagraphStyle(name='PaperCaption',parent=S['Normal'],fontSize=8,leading=11,textColor=colors.HexColor(SOFT),spaceAfter=9))
    S.add(ParagraphStyle(name='CallTitle',parent=S['Heading3'],fontSize=12,leading=14,textColor=colors.HexColor(WHITE),spaceAfter=4))
    P=lambda t,style='PaperBody':Paragraph(str(t),S[style])
    story=[]

    left=image_asset('logo_ignis_informe.png',2.3*cm) or image_asset('logo_ignis.png',2.3*cm)
    right=image_asset('logo_nasa_informe.png',2.1*cm) or image_asset('logo_nasa.png',2.1*cm)
    header_center=Paragraph('IGNIS UY<br/><font size="9" color="#b8c9ee">Proyecto de investigación<br/>NASA Space Apps Challenge 2026</font>',S['PaperT'])
    if left and right:
        t=Table([[left,header_center,right]],colWidths=[3.2*cm,10.1*cm,2.7*cm],hAlign='CENTER')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,0),'LEFT'),('ALIGN',(2,0),(2,0),'RIGHT'),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story.append(t)
    else:
        story.append(header_center)
    story.extend([
        P('Análisis histórico de actividad térmica en Uruguay','PaperT'),
        P('NASA FIRMS · Instrumentos MODIS y VIIRS · Informe técnico exploratorio','PaperSub')
    ])

    hero=BASE/'hero_espacio.jpg'
    if hero.exists():
        story.extend([RLImage(str(hero), width=16.0*cm, height=2.75*cm), Spacer(1,0.15*cm)])

    meta=Table([
        [P(f'<b>Año seleccionado:</b> {ano}'), P(f'<b>Recorte:</b> {escape(region)}')],
        [P(f'<b>Sensores activos:</b> {escape(", ".join(sensores))}'), P('Fecha de emisión (UTC): '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))]
    ], colWidths=[8.0*cm,8.0*cm])
    meta.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),colors.HexColor(PANEL)),
        ('BOX',(0,0),(-1,-1),0.7,colors.HexColor('#35527b')),
        ('INNERGRID',(0,0),(-1,-1),0.35,colors.HexColor('#2a4165')),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    story.extend([meta, Spacer(1,0.12*cm)])
    story.append(P('<b>Resumen.</b> Este documento sintetiza exclusivamente las observaciones satelitales incorporadas al Maestro IGNIS. Las detecciones son anomalías térmicas, no incendios confirmados; no representan superficies quemadas ni una tasa de incendios. La comparación MODIS–VIIRS es exploratoria y no constituye una serie calibrada.'))

    story.append(P('1. Objetivo y alcance','PaperH'))
    story.append(P('Describir la distribución temporal y geográfica de las detecciones en el recorte elegido; contextualizar el año seleccionado frente al material histórico cargado; identificar señales estadísticas preliminares, explicar el estado actual de la armonización MODIS–VIIRS y documentar las principales limitaciones del sistema.'))

    story.append(P('2. Resultados del año seleccionado','PaperH'))
    rows=[['Indicador','Resultado'],['Registros del año',str(len(year))],['Días con registros',str(year.dia.nunique())],['Familias instrumentales',', '.join(sorted(map(str,year.instrumento.unique()))) or 'Sin registros']]
    rows.append(['Mes de máximo registro',MONTHS[int(year.groupby('mes').size().idxmax())-1] if len(year) else 'No disponible'])
    for k,v in sorted(year.groupby('instrumento').size().to_dict().items()):
        rows.append([f'Registros {k}',str(v)])
    table=Table(rows,colWidths=[8.2*cm,8.1*cm],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183153')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('BACKGROUND',(0,1),(-1,-1),colors.HexColor(PANEL)),
        ('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor(WHITE)),
        ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#2e4d76')),
        ('FONTSIZE',(0,0),(-1,-1),8.3),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)
    ]))
    story.extend([table, Spacer(1,0.12*cm)])

    story.append(P('3. Calendario diario y estacionalidad','PaperH'))
    monthly=year.groupby('mes').size().to_dict()
    if monthly:
        story.append(P('<b>Meses con registros incorporados:</b> ' + ' · '.join(f'{MONTHS[int(m)-1]}: {n}' for m,n in sorted(monthly.items()))))
    else:
        story.append(P('El año seleccionado no contiene registros en los archivos incorporados.'))
    story.append(P('Los meses no listados no tienen observaciones en los archivos cargados. Esto no demuestra ausencia de actividad térmica ni cobertura satelital completa.','PaperBodySoft'))
    visual=daily_calendar_figure(year,ano)
    if visual:
        rows_months=max(1,(len(set(pd.to_datetime(year["dia"],errors='coerce').dropna().dt.month))+2)//3)
        story.extend([
            RLImage(visual,width=16.0*cm,height=(2.35 * rows_months + .45)*16.0/10.2*cm),
            P('Calendario diario. En cada casillero coloreado, el número inferior indica observaciones FIRMS del día. Casilleros oscuros: sin registros en el material cargado; no equivalen a días sin incendios.','PaperCaption')
        ])
    if len(df):
        story.extend([RLImage(calendar_figure(df),width=16.0*cm,height=5.45*cm),P('Figura 1. Distribución histórica mensual de los registros cargados. Los casilleros vacíos no certifican ausencia de actividad ni cobertura completa.','PaperCaption')])

    story.append(P('4. Contexto histórico y comparación entre sensores','PaperH'))
    story.append(P(f'El histórico cargado contiene {len(df):,} observaciones únicas distribuidas en {df.anio.nunique()} años con registros. Los recuentos no están normalizados por cobertura, revisitas orbitales o sensibilidad instrumental.'))
    if len(df):
        story.extend([RLImage(trend_figure(df),width=16*cm,height=5.2*cm),P('Figura 2. Cantidad de observaciones por año e instrumento. No debe interpretarse como tendencia climática o incidencia de incendios.','PaperCaption')])

    story.append(PageBreak())
    story.append(P('5. Distribución espacial de observaciones — Uruguay','PaperH'))
    map_data=map_figure(year) if len(year) else None
    if map_data:
        story.extend([P(f'<b>Vista A · año {ano}.</b> Solo observaciones correspondientes al año elegido.','PaperBodySoft'), RLImage(map_data,width=14.7*cm,height=8.3*cm),P('Figura 3A. Distribución del año elegido. Densidad visual relativa, sin normalización por cobertura.','PaperCaption')])
    else:
        story.append(P('No hay coordenadas válidas del año seleccionado para elaborar el mapa.'))
    historic_map=map_figure(df) if len(df) else None
    if historic_map:
        story.extend([P('<b>Vista B · histórico acumulado.</b> Incorpora todos los años cargados; no se compara su escala térmica directamente con la vista anual.','PaperBodySoft'),RLImage(historic_map,width=14.7*cm,height=8.3*cm),P('Figura 3B. Distribución del Maestro completo. Ambas vistas muestran registros, no incendios confirmados.','PaperCaption')])

    story.append(PageBreak())
    story.append(P('6. Armonización MODIS–VIIRS: resultados del Maestro','PaperH'))
    story.append(P('Esta sección presenta datos calculados, no una infografía conceptual. La coincidencia requiere mismo día UTC y misma celda geográfica aproximada de 0,20 grados; no equivale a detección del mismo incendio.','PaperBodySoft'))

    armonia=resumen_armonizacion(df, ano)
    instruments=set(map(str,df.instrumento.astype(str).unique()))
    has_modis=any(k.upper().startswith('MODIS') for k in instruments)
    has_viirs=any(k.upper().startswith('VIIRS') for k in instruments)
    if has_modis and has_viirs:
        story.append(P('Coexistencia instrumental comprobada en el Maestro IGNIS. Esto permite una lectura histórica más rica, pero todavía <b>no</b> habilita mezclar recuentos MODIS y VIIRS como si fueran equivalentes físicos directos.'))
        if armonia['overlap_years']:
            story.append(P('Años con coexistencia entre familias instrumentales en el recorte: ' + ', '.join(str(y) for y in armonia['overlap_years']) + '.'))
        periods=armonia.get('periods',[])
        if periods:
            per_rows=[['Período','Configuración instrumental']] + [[p['Periodo'],p['Configuración instrumental']] for p in periods[:8]]
            pt=Table(per_rows,colWidths=[3.2*cm,12.6*cm],repeatRows=1)
            pt.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183153')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('BACKGROUND',(0,1),(-1,-1),colors.HexColor(PANEL2)),('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor(WHITE)),
                ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#2e4d76')),('FONTSIZE',(0,0),(-1,-1),8),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)
            ]))
            story.extend([pt, Spacer(1,0.10*cm)])
        if not armonia['coincident_cells'].empty:
            cc=armonia['coincident_cells'].copy(); cc['Mes']=cc['mes'].map(lambda m: MONTHS[int(m)-1]); cc=cc[['Mes','celdas_coincidentes']]
            story.append(P(f'Coincidencias espacio-temporales exploratorias para {ano}: se detectaron {int(cc["celdas_coincidentes"].sum())} celdas geográficas aproximadas con presencia de MODIS y VIIRS en el mismo día UTC.'))
            cc_rows=[['Mes','Celdas coincidentes']] + cc.values.tolist()
            ct=Table(cc_rows,colWidths=[6.5*cm,9.0*cm],repeatRows=1)
            ct.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183153')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('BACKGROUND',(0,1),(-1,-1),colors.HexColor(PANEL)),('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor(WHITE)),
                ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#2e4d76')),('FONTSIZE',(0,0),(-1,-1),8),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)
            ]))
            story.extend([ct, Spacer(1,0.08*cm)])
        else:
            story.append(P(f'Para el año {ano} no se detectaron coincidencias exploratorias MODIS–VIIRS con el criterio implementado (mismo día UTC y misma celda espacial aproximada). Esto no demuestra ausencia física del fenómeno ni invalida la serie.'))
        story.append(P('Metodología piloto de armonización: coincidencia por día UTC y por celda espacial aproximada de 0.20° (uso exploratorio). El objetivo es relacionar continuidad histórica, no sumar sensores ni calibrar cobertura efectiva.','PaperBodySoft'))
    else:
        story.append(P('Los archivos disponibles no contienen simultáneamente las familias MODIS y VIIRS en el recorte seleccionado. No hay comparación interinstrumental disponible para armonización.'))

    story.append(P('7. Candidatos de actividad inusual y trazabilidad','PaperH'))
    candidates=[]
    if alertas_func is not None:
        for sensor in sorted(df.instrumento.unique()):
            candidates.extend(alertas_func(df,sensor))
    found=[x for x in candidates if int(x['Año'])==ano]
    story.append(P(f'En el histórico completo se identificaron {len(candidates)} candidatos estadísticos exploratorios; {len(found)} corresponden al año {ano}. No son alertas operativas ni incendios confirmados.'))
    if candidates:
        fig_alert=alert_figure(candidates)
        story.extend([RLImage(fig_alert,width=15.7*cm,height=3.4*cm),P('Figura 4. Distribución de candidatos exploratorios históricos. No representa riesgo operativo ni una tasa de incendios.','PaperCaption')])
    story.append(P('Criterio piloto: por instrumento y mes, al menos 5 registros y por lo menos el doble de la mediana de 3 o más años distintos con registros comparables. Sin normalización por cobertura satelital: úsese únicamente como señal preliminar.','PaperBodySoft'))
    if found:
        r=[['Mes','Instrumento','Registros','Mediana','Índice']] + [[MONTHS[int(x['Mes'])-1][:3],str(x['Sensor']),str(x['Detecciones']),str(x['Mediana otros años']),str(x['Índice frente a mediana'])] for x in found[:16]]
        tb=Table(r,colWidths=[2.1*cm,4.8*cm,2.6*cm,3.2*cm,3.3*cm],repeatRows=1)
        tb.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183153')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('BACKGROUND',(0,1),(-1,-1),colors.HexColor(PANEL2)),('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor(WHITE)),
            ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#2e4d76')),('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)
        ]))
        story.extend([tb, Spacer(1,0.1*cm)])
    story.append(P('La biblioteca documental incluida en el proyecto contiene expedientes de 2023; estos no se atribuyen automáticamente a otros años, lugares o registros FIRMS. Para establecer trazabilidad factual es necesario documentar fuentes independientes, fechas y coincidencia espacial.'))

    story.append(P('8. Procedencia, reproducibilidad y limitaciones','PaperH'))
    story.append(P('Fuente primaria: archivos NASA FIRMS suministrados por el usuario y registros normalizados almacenados en el Maestro IGNIS. El Maestro se exporta manualmente y debe conservarse junto con los ZIP originales. El PDF se genera a partir del estado cargado en la sesión y los filtros activos.'))
    story.append(P('Limitaciones principales: cobertura temporal no certificada; resolución y sensibilidad diferentes por instrumento; revisitas orbitales no normalizadas; artefactos del contorno de referencia; y detecciones no verificadas como incendios. Los espacios vacíos en calendario y mapas significan ausencia de registros <i>en los archivos incorporados</i>.'))
    story.append(P('<b>Uso previsto:</b> informe técnico de investigación y base documental para el equipo IGNIS UY; no constituye un producto operativo de alerta ni una certificación de incendios.'))

    def draw_bg(canvas, document, first=False):
        canvas.saveState()
        w,h=A4
        canvas.setFillColor(colors.HexColor(BG))
        canvas.rect(0,0,w,h,fill=1,stroke=0)
        # La banda espacial ya se dibuja como elemento del documento;
        # no superponerla a la portada ni a los logos.
        canvas.setStrokeColor(colors.HexColor('#2c4770'))
        canvas.line(1.55*cm,1.15*cm,w-1.55*cm,1.15*cm)
        canvas.setFont('Helvetica',7)
        canvas.setFillColor(colors.HexColor(SOFT))
        canvas.drawString(1.55*cm,0.86*cm,'IGNIS UY | Informe técnico exploratorio · NASA FIRMS')
        canvas.drawRightString(w-1.55*cm,0.86*cm,f'Página {document.page}')
        canvas.restoreState()

    doc.build(story,onFirstPage=lambda c,d: draw_bg(c,d,True),onLaterPages=lambda c,d: draw_bg(c,d,False))
    return out.getvalue()
