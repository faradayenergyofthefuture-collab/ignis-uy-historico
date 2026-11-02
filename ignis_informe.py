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
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.path import Path as MPath
from scipy.ndimage import gaussian_filter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from PIL import Image as PILImage

BASE=Path(__file__).resolve().parent
MONTHS=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
CMAP=LinearSegmentedColormap.from_list('ignis',['#42206a','#8440a9','#dc4b95','#ff975a','#ffe36c'])

def image_asset(name,w=2.7*cm):
    p=BASE/name
    if not p.exists():return None
    with PILImage.open(p) as im: aw,ah=im.size
    return RLImage(str(p),width=w,height=w*ah/aw,kind='proportional')

def plot_buffer(fig):
    buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=175,bbox_inches='tight',facecolor='white');plt.close(fig);buffer.seek(0);return buffer

def calendar_figure(df):
    counts=df.groupby(['anio','mes']).size()
    years=list(range(2000,2027)); cells=np.full((12,len(years)),np.nan)
    for (y,m),n in counts.items():
        if 2000<=int(y)<=2026 and 1<=int(m)<=12: cells[int(m)-1,int(y)-2000]=n
    fig,ax=plt.subplots(figsize=(10.5,3.5)); cmap=CMAP.copy();cmap.set_bad('#eef0f5');image=ax.imshow(np.ma.masked_invalid(cells),aspect='auto',cmap=cmap,interpolation='nearest')
    ax.set_xticks(range(0,27,2),years[::2],fontsize=7);ax.set_yticks(range(12),[x[:3] for x in MONTHS],fontsize=8);ax.tick_params(length=0)
    ax.set_title('Calendario histórico de registros por mes (archivos incorporados)',fontsize=11,pad=10)
    fig.colorbar(image,ax=ax,shrink=.8,label='Registros');fig.tight_layout();return plot_buffer(fig)


def daily_calendar_figure(year, ano):
    """Calendario visual de meses con registros; huecos no implican cero actividad."""
    if year.empty:
        return None
    # La columna dia es una fecha normalizada en el Maestro IGNIS.
    dates = pd.to_datetime(year['dia'], errors='coerce').dropna()
    if dates.empty:
        return None
    daily = dates.dt.date.value_counts().to_dict()
    months = sorted(set(dates.dt.month))
    cols = min(3, len(months))
    rows = (len(months) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(10.2, 2.35 * rows + .3), squeeze=False)
    maximum = max(daily.values()) if daily else 1
    import matplotlib.colors as mcolors
    norm = mcolors.Normalize(vmin=1, vmax=max(2, maximum))
    for k, month in enumerate(months):
        ax = axes[k // cols][k % cols]
        ax.set_xlim(0, 7); ax.set_ylim(7.0, -.7); ax.axis('off')
        ax.set_title(f'{MONTHS[month-1]} {ano}', loc='left', fontsize=11, fontweight='bold', color='#173967', pad=5)
        for j, name in enumerate(['L', 'M', 'X', 'J', 'V', 'S', 'D']):
            ax.text(j+.5, .35, name, ha='center', va='center', fontsize=8, color='#4d5a70')
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(int(ano), int(month))
        for wi, week in enumerate(weeks):
            for di, day in enumerate(week):
                if day.month != month:
                    continue
                n = daily.get(day)
                face = CMAP(norm(n)) if n is not None else '#eef1f6'
                rect = plt.Rectangle((di+.055, wi+1.05), .89, .84, facecolor=face, edgecolor='#d1d7e0', linewidth=.6)
                ax.add_patch(rect)
                ax.text(di+.5, wi+1.33, str(day.day), ha='center', va='center', fontsize=7.3,
                        color='white' if n is not None else '#6e7785')
                if n is not None:
                    ax.text(di+.5, wi+1.70, str(n), ha='center', va='center', fontsize=9,
                            fontweight='bold', color='white')
    for k in range(len(months), rows*cols):
        axes[k // cols][k % cols].axis('off')
    fig.tight_layout(pad=1.3)
    return plot_buffer(fig)

def trend_figure(df):
    agg=df.groupby(['anio','instrumento']).size().unstack(fill_value=0)
    fig,ax=plt.subplots(figsize=(10,3.3));agg.index=agg.index.astype(int).astype(str)
    agg.plot.bar(ax=ax,width=.75,rot=45,color=['#435a9e','#df718c','#7a4ca5','#ecae61'][:len(agg.columns)])
    ax.set_ylabel('Registros FIRMS');ax.set_xlabel('Año presente en archivos');ax.grid(axis='y',alpha=.2);ax.legend(fontsize=7,loc='upper left');ax.set_title('Conteo anual por familia instrumental (no normalizado)',fontsize=10)
    fig.tight_layout();return plot_buffer(fig)

def map_figure(df):
    raw=json.loads((BASE/'uruguay_contorno.geojson').read_text(encoding='utf-8'))
    geometry=raw['features'][0]['geometry'];ring=geometry['coordinates'][0] if geometry['type']=='Polygon' else geometry['coordinates'][0][0]
    border=np.asarray(ring,dtype=float)
    clean=df[['longitude','latitude']].apply(pd.to_numeric,errors='coerce').dropna()
    clean=clean[clean.longitude.between(-59,-52)&clean.latitude.between(-36,-29)]
    if clean.empty:return None
    xedges=np.linspace(-58.8,-52.8,125);yedges=np.linspace(-35.4,-29.8,125)
    hist,*_=np.histogram2d(clean.longitude,clean.latitude,bins=[xedges,yedges]);dense=gaussian_filter(hist.T,sigma=2.5)
    x=(xedges[1:]+xedges[:-1])/2;y=(yedges[1:]+yedges[:-1])/2
    xx,yy=np.meshgrid(x,y);mask=MPath(border).contains_points(np.c_[xx.ravel(),yy.ravel()]).reshape(xx.shape)
    dense[~mask]=np.nan;dense[dense<.06]=np.nan
    fig,ax=plt.subplots(figsize=(9.4,6.0));ax.set_facecolor('#0b1230')
    ax.fill(border[:,0],border[:,1],color='#211c4a',alpha=.9)
    img=ax.imshow(dense,extent=[xedges[0],xedges[-1],yedges[0],yedges[-1]],origin='lower',cmap=CMAP,interpolation='bilinear',alpha=.95,aspect='auto')
    plot=clean.sample(min(1800,len(clean)),random_state=42)
    ax.scatter(plot.longitude,plot.latitude,s=2.4,color='#e8eaff',alpha=.4,zorder=3)
    ax.plot(border[:,0],border[:,1],color='#a5cfff',lw=1.5,zorder=4)
    for name,lon,lat in [('Artigas',-56.0,-30.45),('Durazno',-56.52,-33.22),('Canelones',-56.28,-34.55),('Maldonado',-54.95,-34.73),('Rocha',-54.32,-34.12)]:
        ax.text(lon,lat,name,color='white',fontsize=7,bbox=dict(facecolor='#14142f',alpha=.65,edgecolor='none',pad=2))
    ax.set(xlim=(-58.85,-52.65),ylim=(-35.45,-29.75),xlabel='Longitud',ylabel='Latitud')
    ax.tick_params(colors='#31374b',labelsize=7);fig.colorbar(img,ax=ax,shrink=.7,label='Densidad visual relativa (no calibrada)')
    fig.tight_layout();return plot_buffer(fig)

def generar_informe_pdf(datos,ano,region,sensores,alertas_func=None):
    df=datos.copy();year=df[df.anio==ano]
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=1.75*cm,rightMargin=1.75*cm,topMargin=1.8*cm,bottomMargin=1.85*cm,title='IGNIS UY - Informe científico de actividad térmica',author='Proyecto IGNIS UY')
    S=getSampleStyleSheet();S.add(ParagraphStyle(name='PaperT',parent=S['Title'],fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=colors.HexColor('#143462'),spaceAfter=7))
    S.add(ParagraphStyle(name='PaperSub',parent=S['Normal'],alignment=TA_CENTER,fontSize=9,leading=13,textColor=colors.HexColor('#4a5670'),spaceAfter=8))
    S.add(ParagraphStyle(name='PaperH',parent=S['Heading2'],fontSize=12.1,leading=16,textColor=colors.HexColor('#234f8e'),spaceBefore=14,spaceAfter=7,keepWithNext=True))
    S.add(ParagraphStyle(name='PaperBody',parent=S['BodyText'],fontSize=9,leading=13,alignment=TA_JUSTIFY,spaceAfter=7))
    S.add(ParagraphStyle(name='PaperCaption',parent=S['Normal'],fontSize=8,leading=11,textColor=colors.HexColor('#506077'),spaceAfter=9))
    P=lambda t,style='PaperBody':Paragraph(str(t),S[style]); story=[]
    left=image_asset('logo_ignis_informe.png',2.7*cm);right=image_asset('logo_nasa_informe.png',2.3*cm)
    if left and right:
        t=Table([[left,Paragraph('IGNIS UY<br/><font size="8">Proyecto de investigación</font>',S['PaperT']),right]],colWidths=[3.4*cm,9.8*cm,2.9*cm],hAlign='CENTER');t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,0),'LEFT'),('ALIGN',(2,0),(2,0),'RIGHT'),('BOTTOMPADDING',(0,0),(-1,-1),12)]));story.append(t)
    story.extend([P('Análisis histórico de actividad térmica en Uruguay','PaperT'),P('NASA FIRMS · Instrumentos MODIS y VIIRS · Informe técnico exploratorio','PaperSub'),P(f'<b>Año:</b> {ano} &nbsp;&nbsp; <b>Recorte:</b> {escape(region)} &nbsp;&nbsp; <b>Sensores:</b> {escape(", ".join(sensores))}'),P('Fecha de emisión (UTC): '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')),P('<b>Resumen.</b> Este documento sintetiza exclusivamente las observaciones satelitales incorporadas al Maestro IGNIS. Las detecciones son anomalías térmicas, no incendios confirmados; no representan superficies quemadas, ni una tasa de incendios. La comparación MODIS–VIIRS es exploratoria y no constituye una serie calibrada.'),P('1. Objetivo y alcance','PaperH'),P('Describir la distribución temporal y geográfica de las detecciones en el recorte elegido; contextualizar el año seleccionado frente al material histórico cargado; identificar señales estadísticas preliminares y documentar sus limitaciones. No se asume cobertura satelital completa de los meses sin registros.'),P('2. Resultados del año seleccionado','PaperH')])
    rows=[['Indicador','Resultado'],['Registros del año',str(len(year))],['Días con registros',str(year.dia.nunique())],['Familias instrumentales',', '.join(sorted(year.instrumento.unique())) or 'Sin registros']]
    rows.append(['Mes de máximo registro',MONTHS[int(year.groupby('mes').size().idxmax())-1] if len(year) else 'No disponible'])
    for k,v in sorted(year.groupby('instrumento').size().to_dict().items()):rows.append([f'Registros {k}',str(v)])
    table=Table(rows,colWidths=[8.5*cm,8*cm],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4ebf6')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd4e1')),('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.append(table)
    story.append(P('3. Calendario diario y estacionalidad','PaperH'))
    monthly=year.groupby('mes').size().to_dict()
    if monthly:
        story.append(P('<b>Meses con registros incorporados:</b> ' + ' · '.join(f'{MONTHS[int(m)-1]}: {n}' for m,n in sorted(monthly.items()))))
    else:
        story.append(P('El año seleccionado no contiene registros en los archivos incorporados.'))
    story.append(P('Los meses que no figuran no tienen observaciones en los archivos cargados. Esto no demuestra ausencia de actividad térmica ni cobertura satelital completa.'))
    visual=daily_calendar_figure(year,ano)
    if visual:
        story.extend([RLImage(visual,width=16.0*cm,height=(2.35 * ((len(monthly)+2)//3) + .3)*16.0/10.2*cm),
            P('Calendario diario. En cada casillero coloreado, el número inferior indica observaciones FIRMS del día. Casilleros claros: sin registros en el material cargado; no equivalen a días sin incendios.','PaperCaption')])
    if len(df):story.extend([RLImage(calendar_figure(df),width=16.0*cm,height=5.3*cm),P('Figura 1. Distribución histórica mensual de los registros cargados. Los casilleros claros no certifican ausencia de actividad ni cobertura completa.','PaperCaption')])
    story.append(P('4. Contexto histórico y comparación entre sensores','PaperH'))
    story.append(P(f'El histórico cargado contiene {len(df):,} observaciones únicas distribuidas en {df.anio.nunique()} años con registros. Los recuentos no están normalizados por cobertura, revisitas o sensibilidad.'))
    if len(df):story.extend([RLImage(trend_figure(df),width=16*cm,height=5.1*cm),P('Figura 2. Cantidad de observaciones por año e instrumento. No debe interpretarse como tendencia climática o incidencia de incendios.','PaperCaption')])
    story.append(P('5. Mapa térmico de Uruguay — año seleccionado','PaperH'))
    chosen=year
    map_data=map_figure(chosen) if len(chosen) else None
    if map_data:story.extend([RLImage(map_data,width=15.8*cm,height=10.1*cm),P('Figura 3. Distribución espacial exclusiva del año seleccionado. Contorno general de Natural Earth. No es densidad calibrada ni superficie quemada.','PaperCaption')])
    else:story.append(P('No hay coordenadas válidas del año seleccionado para elaborar el mapa. No se sustituyen por datos de otros años.'))
    story.append(P('6. Actividad inusual y trazabilidad documental','PaperH'))
    candidates=[]
    if alertas_func is not None:
        for sensor in sorted(df.instrumento.unique()):candidates.extend(alertas_func(df,sensor))
    found=[x for x in candidates if int(x['Año'])==ano]
    story.append(P(f'Se detectaron {len(found)} candidatos estadísticos preliminares para {ano}. Criterio piloto: por instrumento y mes, al menos 5 registros, por lo menos el doble de la mediana, y tres años de comparación. No son alertas operativas.'))
    if found:
        r=[['Mes','Instrumento','Registros','Mediana','Relación']]
        for x in found[:16]:r.append([MONTHS[int(x['Mes'])-1][:3],str(x['Sensor']),str(x['Detecciones']),str(x['Mediana otros años']),str(x['Índice frente a mediana'])])
        tb=Table(r,colWidths=[2.1*cm,4.4*cm,3.2*cm,3.2*cm,3.2*cm],repeatRows=1);tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4ebf6')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#cbd5e1')),('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(tb)
    story.append(P('La biblioteca documental incluida en el proyecto contiene expedientes de 2023; estos no se atribuyen automáticamente a otros años, lugares o registros FIRMS. Para establecer trazabilidad factual es necesario documentar fuentes independientes, fechas y coincidencia espacial.'))
    story.append(P('7. Armonización MODIS–VIIRS','PaperH'))
    instruments=set(df.instrumento.unique());comparison=('MODIS' in instruments and 'VIIRS' in instruments)
    if comparison:story.append(P('Hay observaciones de familias MODIS y VIIRS en los archivos cargados. Se presentan por separado: no se ha realizado una calibración cuantitativa interinstrumental ni se han resuelto todos los duplicados físicos entre sensores. La armonización queda pendiente de ajustar cobertura, resolución, revisitas, ventanas de observación y umbrales de detección.'))
    else:story.append(P('La comparación interinstrumental no corresponde todavía: en el recorte histórico cargado no coexisten ambas familias MODIS y VIIRS. El encabezado del proyecto describe una línea de investigación futura, no una armonización ya validada.'))
    story.append(P('8. Procedencia, reproducibilidad y limitaciones','PaperH'))
    story.append(P('Fuente primaria: archivos NASA FIRMS suministrados por el usuario y registros normalizados almacenados en el Maestro IGNIS. El Maestro se exporta manualmente y debe conservarse con los ZIP originales. El PDF se genera a partir del estado cargado en la sesión y los filtros activos.'))
    story.append(P('Limitaciones principales: cobertura temporal no certificada; resolución y sensibilidad diferentes por instrumento; revisitas orbitales no normalizadas; artefactos geográficos del contorno de referencia; y detecciones no verificadas como incendios. Los espacios vacíos en calendario y mapas significan ausencia de registros <i>en los archivos incorporados</i>.'))
    story.append(P('<b>Uso previsto:</b> informe técnico de investigación y base documental para el equipo IGNIS UY; no constituye un producto de alerta o una certificación de incendios.'))
    def footer(canvas,document):
        canvas.saveState();w,h=A4;canvas.setStrokeColor(colors.HexColor('#ccd5e5'));canvas.line(1.75*cm,1.35*cm,w-1.75*cm,1.35*cm)
        canvas.setFont('Helvetica',7);canvas.setFillColor(colors.HexColor('#526480'));canvas.drawString(1.75*cm,1.06*cm,'IGNIS UY | Informe técnico exploratorio · NASA FIRMS');canvas.drawRightString(w-1.75*cm,1.06*cm,f'Página {document.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
