"""Revisión de extremos desde agregados y frecuencias ya calculadas.

No vuelve a leer CSV de los ZIP ni procesa los 54 millones de registros.
No altera datos ni gráficas anteriores: limita sólo la vista principal a 18–100.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import tempfile
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from clean_data import YEARS, file_hash, require, save_csv, save_json
from build_descriptive import COUNTS, METRICS, SEX_LABELS, pct, number, markdown_table

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "participamx_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

AGE_BANDS = [("101-110", 101, 110), ("111-120", 111, 120), ("over_120", 121, np.inf)]
BAND_LABELS = {"101-110": "101–110", "111-120": "111–120", "over_120": ">120"}


def distribution_statistics(values, weights=None):
    """Cuantiles lineales de frecuencias enteras: igual a expandir sin expandir."""
    values = np.asarray(values, dtype=np.float64)
    weights = np.ones(len(values), dtype=np.int64) if weights is None else np.asarray(weights)
    require(len(values) == len(weights) and np.isfinite(values).all(), "Valores o pesos no válidos.")
    require(np.isfinite(weights).all() and (weights >= 0).all() and np.equal(weights, np.floor(weights)).all(), "Los pesos deben ser frecuencias enteras no negativas.")
    keep = weights > 0
    values, weights = values[keep], weights[keep].astype(np.int64)
    if not len(values):
        return {}
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cumulative = np.cumsum(weights)
    count = int(cumulative[-1])
    def quantile(probability):
        rank = (count - 1) * probability
        low, high = int(np.floor(rank)), int(np.ceil(rank))
        left, right = values[np.searchsorted(cumulative, [low, high], side="right")]
        return float(left + (right - left) * (rank - low))
    q1, median, q3 = [quantile(probability) for probability in (.25, .5, .75)]
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (values < lower) | (values > upper)
    inside = ~mask
    mean = float(np.dot(values, weights) / count)
    return dict(count=count, mean=mean, std=float(np.sqrt(np.dot((values-mean)**2, weights)/(count-1))) if count > 1 else 0.0,
                min=float(values[0]), q1=q1, median=median, q3=q3, iqr=iqr, max=float(values[-1]),
                p95=quantile(.95), p99=quantile(.99), lower_fence=lower, upper_fence=upper,
                outlier_count=int(weights[mask].sum()), outlier_value_sum=float(np.dot(values[mask], weights[mask])),
                zero_count=int(weights[values==0].sum()), whislo=float(values[inside][0]), whishi=float(values[inside][-1]),
                fliers=np.unique(values[mask]).tolist())


def age_statistics(age):
    rows, bands, visibility = [], [], []
    for year, frame in age.groupby("election_year", sort=True):
        require(frame.LN.eq(frame.SV + frame.NV + frame.NS).all(), "Identidad fallida en edades agregadas.")
        for weight in ("source_row_count", "LN"):
            stats = distribution_statistics(frame.age_value, frame[weight])
            mask = (frame.age_value < stats["lower_fence"]) | (frame.age_value > stats["upper_fence"])
            totals = frame.loc[mask, ["source_row_count", *COUNTS]].sum()
            rows.append(dict(election_year=int(year), weighting=weight, **stats,
                             **{f"outlier_{name}": int(totals[name]) for name in ["source_row_count", *COUNTS]}))
        for label, lower, upper in AGE_BANDS:
            selected = frame[frame.age_value.between(lower, upper)]
            totals = selected[["source_row_count", *COUNTS]].sum()
            specified = int(totals.SV + totals.NV)
            bands.append(dict(election_year=int(year), age_interval=label,
                aggregate_groups=len(selected), **{name: int(totals[name]) for name in ["source_row_count", *COUNTS]},
                specified_count=specified, participation_observed=float(totals.SV/specified) if specified else None))
        full = frame[["source_row_count", *COUNTS]].sum()
        hidden = frame.loc[frame.age_value.gt(100), ["source_row_count", *COUNTS]].sum()
        visible = full-hidden
        full_rate = full.SV/(full.SV+full.NV)
        visible_rate = visible.SV/(visible.SV+visible.NV)
        visibility.append(dict(election_year=int(year), hidden_source_rows=int(hidden.source_row_count),
            hidden_LN=int(hidden.LN), hidden_row_share=float(hidden.source_row_count/full.source_row_count),
            hidden_LN_share=float(hidden.LN/full.LN), full_observed=float(full_rate),
            displayed_observed=float(visible_rate), displayed_minus_full_pp=float(100*(visible_rate-full_rate))))
    return rows, bands, visibility


def count_statistics(root, municipalities):
    """Distingue conteos por celda original de totales municipales."""
    rows = []
    for year in YEARS:
        frequencies = pd.read_csv(root/f"analysis/reports/value_frequencies_{year}.csv", dtype={"value": str}, na_filter=False)
        for name in ["LN", "SV", "NV"]:
            selected = frequencies[frequencies.column.eq(name)]
            rows.append(dict(election_year=year, level="source_cell", variable=name,
                **distribution_statistics(selected.value.astype('int64'), selected["count"])))
            rows.append(dict(election_year=year, level="municipality", variable=name,
                **distribution_statistics(municipalities.loc[municipalities.election_year.eq(year), name])))
    return rows


def unspecified_statistics(municipalities):
    rows = []
    for year, frame in municipalities.groupby('election_year', sort=True):
        for weight in ('municipality', 'LN'):
            stats = distribution_statistics(frame.unspecified_rate, frame.LN if weight=='LN' else None)
            mask = (frame.unspecified_rate < stats['lower_fence']) | (frame.unspecified_rate > stats['upper_fence'])
            selected = frame[mask]
            rows.append(dict(election_year=int(year), weighting=weight, **stats,
                outlier_municipalities=len(selected), outlier_source_rows=int(selected.source_row_count.sum()),
                outlier_LN=int(selected.LN.sum()), outlier_NS=int(selected.NS.sum()),
                high_NS_municipalities=int(frame.unspecified_rate.ge(.10).sum()),
                national_unspecified_rate=float(frame.NS.sum()/frame.LN.sum())))
    return rows


def scan_extreme_rates(source, min_specified_count=100, batch_size=100_000):
    """Revisa 2.4 millones de grupos agregados; conserva sólo resúmenes y ejemplos."""
    dataset = ds.dataset(source/'municipality_age_sex', format='parquet')
    metrics = ["source_row_count", *COUNTS]
    summaries = {}
    examples = pd.DataFrame()
    keys = ['election_year','EDOCVE','MPIOCVE','age_value','SEXO']
    columns = [*keys, 'state_name_label','municipality_name_label',*metrics,'specified_count',
               'participation_observed','unspecified_rate','sex_2_source_rows','sex_2_nominal_count']
    source_totals = Counter()
    for batch in dataset.scanner(columns=columns, batch_size=batch_size, use_threads=False,
                                 batch_readahead=1,fragment_readahead=1).to_batches():
        frame = batch.to_pandas()
        require(frame.LN.eq(frame.SV+frame.NV+frame.NS).all(), 'Identidad fallida en agregado demográfico.')
        require(frame.participation_observed.isna().equals(frame.specified_count.eq(0)), 'Tasas no definidas incorrectas.')
        for metric in [*metrics,'sex_2_source_rows','sex_2_nominal_count']:
            source_totals[metric] += int(frame[metric].sum())
        defined = frame.participation_observed.notna()
        extreme = defined & (frame.participation_observed.le(.05) | frame.participation_observed.ge(.95))
        small = defined & frame.specified_count.lt(min_specified_count)
        categories = dict(all_groups=np.ones(len(frame), dtype=bool),
            observed_undefined=~defined, rate_extreme=extreme, small_specified=small,
            extreme_small_specified=extreme & small, exact_zero=frame.participation_observed.eq(0),
            exact_one=frame.participation_observed.eq(1))
        for label, mask in categories.items():
            selected = frame.loc[mask]
            for year, group in selected.groupby('election_year'):
                entry = summaries.setdefault((int(year),label), Counter())
                entry['aggregate_groups'] += len(group)
                for metric in metrics:
                    entry[metric] += int(group[metric].sum())
        candidates = frame.loc[extreme & small].sort_values(['specified_count',*keys]).head(12)
        examples = pd.concat([examples,candidates],ignore_index=True).sort_values(['specified_count',*keys]).head(12)
    rows = [dict(election_year=year, category=label, **{key:int(counts[key]) for key in ['aggregate_groups',*metrics]})
            for (year,label),counts in sorted(summaries.items())]
    return rows, examples, source_totals


def box_values(row, label):
    return dict(label=str(label),med=row['median'],q1=row['q1'],q3=row['q3'],
                whislo=row['whislo'],whishi=row['whishi'],fliers=row['fliers'])


def plot_age_boxes(rows, output):
    fig, axes = plt.subplots(1,2,figsize=(13,5),sharey=True)
    for axis, weight, title in zip(axes,['source_row_count','LN'],['Ponderación: filas fuente','Ponderación: LN reportada']):
        values = [row for row in rows if row['weighting']==weight]
        axis.bxp([box_values(row,row['election_year']) for row in values],
                 flierprops=dict(marker='.',markersize=4,alpha=.5))
        axis.axhline(100,color='#ba542b',linestyle='--',linewidth=1,label='Límite de la vista principal')
        axis.set_title(title)
        axis.set_xlabel('Año electoral')
        axis.set_ylabel('Edad exacta')
        axis.set_ylim(15,145)
        axis.grid(axis='y',alpha=.2)
        axis.legend(fontsize=8,loc='lower right')
    fig.suptitle('Cuartiles exactos y bigotes a 1.5 IQR; puntos = edades distintas fuera de los bigotes',fontsize=11)
    fig.tight_layout()
    fig.savefig(output/'age_boxplots.png',dpi=170)
    plt.close(fig)


def plot_reviewed_profiles(age, output, thresholds):
    """Selecciona coordenadas visibles, sin recortar valores ni cambiar tasas."""
    selected = age[age.age_value.between(18,100)]
    colors = {'0':'#286b9d','1':'#ab427b','2':'#bd7a12'}
    fig, axes = plt.subplots(2,3,figsize=(17,9),sharex=True,sharey=True)
    for axis,year in zip(axes.flat,YEARS):
        frame = selected[selected.election_year.eq(year)]
        for sex in ['0','1','2']:
            values = frame[frame.SEXO.eq(sex)].sort_values('age_value')
            if values.empty:
                continue
            # Usa las banderas de soporte ya definidas, sin decidir exclusiones.
            low = values.has_low_support | values.is_observed_undefined
            if sex=='2':
                axis.scatter(values.age_value,values.participation_observed,marker='x',s=23,
                             color=colors[sex],label='No binario: sólo puntos',zorder=4)
            else:
                curve = values.set_index('age_value').participation_observed.where(~low.to_numpy()).reindex(range(18,101))
                axis.plot(curve.index,curve,color=colors[sex],label=SEX_LABELS[sex],linewidth=1.8)
                scarce = values[low & values.participation_observed.notna()]
                axis.scatter(scarce.age_value,scarce.participation_observed,facecolors='none',edgecolors=colors[sex],s=30,zorder=4)
        axis.set_title(str(year))
        axis.set_xlim(18,100)
        axis.set_ylim(-.02,1.05)
        axis.set_xticks([18,30,40,50,60,70,80,90,100])
        axis.set_xlabel('Edad exacta (18–100)')
        axis.set_ylabel('SV / (SV + NV)')
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(alpha=.2)
        handles, labels = axis.get_legend_handles_labels()
        handles.append(Line2D([],[],marker='o',markerfacecolor='none',color='gray',linestyle='None',label='Soporte reducido: sin línea'))
        axis.legend(handles=handles,fontsize=7,loc='lower center')
    fig.suptitle('Participación observada por edad exacta y sexo · seis elecciones\nEdades >100 fuera de esta vista; todas se conservan en los datos y se documentan aparte',fontsize=11)
    fig.text(.5,.005,f"Soporte reducido: LN<{thresholds['min_registered_count']}, SV+NV<{thresholds['min_specified_count']} o filas fuente<{thresholds['min_source_rows']}. SEXO=2: LN total=105; sin conexiones.",ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.025,1,.94))
    fig.savefig(output/'age_sex_profiles_reviewed.png',dpi=170)
    plt.close(fig)


def plot_age_extremes(age, output):
    fig,axes=plt.subplots(2,3,figsize=(17,8),sharex=True)
    for axis,year in zip(axes.flat,YEARS):
        values=age[(age.election_year.eq(year)) & age.age_value.gt(100)].groupby('age_value')[['source_row_count','LN']].sum().reindex(range(101,141),fill_value=0)
        axis.bar(values.index,values.source_row_count,color='#527da6',alpha=.7,label='Filas fuente')
        axis.plot(values.index,values.LN,color='#d07c21',marker='.',linewidth=.8,label='LN reportada')
        axis.axvspan(110.5,120.5,color='#ebd9aa',alpha=.25)
        axis.axvspan(120.5,140.5,color='#e4ada5',alpha=.2)
        axis.set_yscale('symlog',linthresh=1)
        axis.set_title(str(year))
        axis.set_xlabel('Edad exacta >100')
        axis.set_ylabel('Frecuencia (log sobre 1)')
        axis.set_xlim(100.5,140.5)
        axis.grid(axis='y',alpha=.2)
        axis.legend(fontsize=8)
    fig.suptitle('Edades extremas: frecuencias exactas de filas y conteos nominales\nÁreas sombreadas: 111–120 y >120; cero indica ausencia de esa edad en los agregados',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.93))
    fig.savefig(output/'age_extremes.png',dpi=170)
    plt.close(fig)


def plot_count_boxes(rows, output):
    fig,axes=plt.subplots(2,3,figsize=(16,9))
    for row_index,level in enumerate(['source_cell','municipality']):
        for axis,name in zip(axes[row_index],['LN','SV','NV']):
            values=[row for row in rows if row['level']==level and row['variable']==name]
            axis.bxp([box_values(row,row['election_year']) for row in values],flierprops=dict(marker='.',markersize=2,alpha=.3))
            axis.set_yscale('symlog',linthresh=1)
            axis.set_title(f"{name} · {'celda fuente' if level=='source_cell' else 'total municipal'}")
            axis.set_ylabel('Conteo (escala log sobre 1)')
            axis.set_xlabel('Año')
            axis.grid(axis='y',alpha=.2)
    fig.suptitle('Conteos en dos unidades distintas · cuartiles exactos y regla 1.5 IQR\nPuntos = valores distintos fuera de bigotes; no se borraron ni recortaron conteos',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.93))
    fig.savefig(output/'count_boxplots.png',dpi=170)
    plt.close(fig)


def plot_unspecified(rows, output):
    fig,axes=plt.subplots(1,2,figsize=(13,5),sharey=True)
    for axis,weight,title in zip(axes,['municipality','LN'],['Municipios con igual peso','Municipios ponderados por LN']):
        values=[row for row in rows if row['weighting']==weight]
        axis.bxp([box_values(row,row['election_year']) for row in values],flierprops=dict(marker='.',markersize=3,alpha=.3))
        axis.axhline(.10,color='#b85a34',linestyle='--',label='Revisión NS/LN ≥10 %')
        axis.set_title(title)
        axis.set_xlabel('Año electoral')
        axis.set_ylabel('NS / LN municipal')
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(axis='y',alpha=.2)
        axis.legend(fontsize=8)
    fig.suptitle('No especificación municipal: señal de cobertura, no abstención ni error comprobado',fontsize=11)
    fig.tight_layout()
    fig.savefig(output/'unspecified_rate_boxplots.png',dpi=170)
    plt.close(fig)


def write_report(root, charts, evidence, report, age, age_rows, bands, visibility, counts, unspecified, rate_rows, examples, manifest):
    rate_frame=pd.DataFrame(rate_rows)
    group_metrics=['aggregate_groups','source_row_count',*COUNTS]
    hidden=age.loc[age.age_value.gt(100),['source_row_count',*COUNTS]].sum()
    age24=age[age.election_year.eq(2024)]
    max_rows=[]
    for code in ['0','1']:
        frame=age24[age24.SEXO.eq(code)]
        for scope,selected in [('18–140',frame),('18–100',frame[frame.age_value.between(18,100)])]:
            defined=selected[selected.participation_observed.notna()]
            if defined.empty:
                continue
            top=defined.sort_values(['participation_observed','age_value'],ascending=[False,True]).iloc[0]
            max_rows.append([SEX_LABELS[code],scope,int(top.age_value),number(top.LN),number(top.specified_count),pct(top.participation_observed),pct(top.unspecified_rate),'Sí' if top.has_low_support else 'No'])
    def stat_table(rows, level=False):
        return markdown_table(['Año', 'Unidad / peso','Campo','N / peso total','Media','DE','Q1','Mediana','Q3','IQR','Máx.','Fuera IQR'],
            [[r['election_year'],r.get('weighting',r.get('level')),r.get('variable','EDAD'),number(r['count']),*[f"{r[k]:.3f}" for k in ['mean','std','q1','median','q3','iqr','max']],number(r['outlier_count'])] for r in rows])
    def rate_counts(category):
        return rate_frame[rate_frame.category.eq(category)].set_index('election_year')
    all_groups=rate_counts('all_groups')
    extreme=rate_counts('rate_extreme')
    small=rate_counts('extreme_small_specified')
    undefined=rate_counts('observed_undefined')
    lines=['# Revisión estadística de valores atípicos y reglas de visualización','',
        '## Alcance y fuentes','',
        'Esta revisión conserva los datos y las gráficas anteriores. Reutiliza `age_sex_year` (1,350 grupos) y `municipality` (14,779 grupos), y recorre por bloques los 2,389,546 agregados municipio–edad–sexo para estudiar tasas escasas. Los conteos por celda fuente provienen de las frecuencias exactas de la auditoría. No se releen los CSV de los ZIP ni se recorren los 54,872,712 registros limpios; sólo se calculan hashes binarios para comprobar integridad.','',
        'Las unidades no se mezclan: fila fuente = celda de sección/sexo/edad; grupo demográfico = municipio/edad/sexo; municipio = suma de sus celdas en el año. Las filas no equivalen a personas. La ponderación por LN describe conteos nominales reportados dentro de cada elección, sin validación individual ni seguimiento de personas únicas entre años.','',
        '## Método estadístico y plausibilidad','',
        'Se calcularon cuartiles lineales exactos, mediana, IQR=Q3−Q1 y límites Q1−1.5 IQR y Q3+1.5 IQR. Con frecuencias enteras se usan los mismos rangos que al expandir cada valor tantas veces como su peso, sin realizar esa expansión. La DE usa ddof=1 en esa distribución de frecuencias; no estima incertidumbre ni un efecto de diseño. No se muestrea ni se aplican modelos.','',
        'Para EDAD hay dos distribuciones: ponderación por `source_row_count`, que reproduce exactamente la auditoría por filas, y por LN, que aproxima la distribución nominal reportada. Los puntos fuera de IQR son señales dependientes de la unidad y de la ponderación. Las bandas 101–110, 111–120 y >120 son cortes descriptivos de revisión de plausibilidad, no códigos oficiales ni límites de edad válidos. No se declara incorrecta una edad por pertenecer a una banda o superar IQR.','',
        stat_table(age_rows),'',
        'El peso de filas asigna mucha presencia a edades con numerosas celdas pequeñas. La ponderación por LN da más peso a las edades que reúnen más registros nominales. Un límite IQR negativo no define una edad mínima admisible; un límite superior menor de 100 bajo LN tampoco convierte a las personas mayores en errores. En 2015 no hay edades fuera del IQR por filas, aunque hay edades hasta 117 años.','',
        markdown_table(['Año','Peso','Límite superior IQR','Filas fuente fuera','LN fuera','SV fuera','NV fuera','NS fuera'],
            [[r['election_year'],r['weighting'],f"{r['upper_fence']:.1f}",*[number(r[f'outlier_{c}']) for c in ['source_row_count',*COUNTS]]] for r in age_rows]),'',
        '![Boxplots de edad](../charts/outliers/age_boxplots.png)','',
        '## Edades extremas: conteos y participación','',
        markdown_table(['Año','Intervalo','Filas fuente','LN','SV','NV','NS','SV+NV','Participación observada'],
            [[r['election_year'],BAND_LABELS[r['age_interval']],*[number(r[c]) for c in ['source_row_count',*COUNTS,'specified_count']],pct(r['participation_observed'])] for r in bands]),'',
        f"En las seis elecciones, EDAD>100 representa {number(hidden.source_row_count)} filas fuente y LN={number(hidden.LN)}, con SV={number(hidden.SV)}, NV={number(hidden.NV)} y NS={number(hidden.NS)}. Son sumas de observaciones de elecciones distintas, no personas únicas. Las tasas de cada intervalo se calculan como suma SV dividida por suma SV+NV, nunca como promedio de tasas individuales. Un intervalo vacío (por ejemplo, >120 en 2015) tiene conteos cero y participación no definida, no participación cero.",'',
        'Los histogramas de edades exactas muestran ambas frecuencias; donde no se observa una edad se dibuja una barra de frecuencia cero, sin crear registros analíticos. Los ejes logarítmicos de conteos sólo cambian la representación gráfica.','',
        '![Frecuencias extremas](../charts/outliers/age_extremes.png)','',
        '## Comparación de la vista completa y la vista 18–100','',
        markdown_table(['Año','Filas >100','% filas','LN >100','% LN','Participación completa','Participación del subconjunto visible','Diferencia visible−completa (pp)'],
            [[r['election_year'],number(r['hidden_source_rows']),f"{100*r['hidden_row_share']:.4f} %",number(r['hidden_LN']),f"{100*r['hidden_LN_share']:.4f} %",pct(r['full_observed']),pct(r['displayed_observed']),f"{r['displayed_minus_full_pp']:.5f}"] for r in visibility]),'',
        'La última comparación es un diagnóstico del peso del subconjunto mostrado, no un cambio del indicador nacional. Los indicadores nacionales y las tasas de cada punto de edad/sexo permanecen sin alteración. No se reponderan ni se redistribuyen edades >100 en la vista.','',
        markdown_table(['Sexo','Vista','Edad del primer máximo','LN','SV+NV','Tasa observada','NS/LN','Soporte reducido'],max_rows),'',
        'La selección del máximo desempata por edad ascendente; no identifica una edad óptima ni una asociación causal. Las tasas de 100 % con LN o denominadores de una o pocas unidades son exactas para ese grupo observado, pero no robustas para interpretar un patrón general.','',
        'Reglas exclusivas de visualización:','',
        '1. La vista principal muestra 18–100 inclusive, con los seis años y la misma escala vertical 0–100 %. Las edades >100 permanecen en las tablas y en el gráfico de extremos; el corte 100 no es una regla de limpieza o de entrenamiento.',
        '2. Hombres y mujeres se comparan con líneas únicamente en tramos con soporte suficiente. Los valores escasos definidos se muestran con círculos huecos y la línea se interrumpe; los no definidos dejan un hueco y no se conectan por interpolación.',
        f"3. Se reutilizan los umbrales descriptivos existentes: LN<{manifest['thresholds']['min_registered_count']}, SV+NV<{manifest['thresholds']['min_specified_count']} o filas fuente<{manifest['thresholds']['min_source_rows']}. Son advertencias operativas, no intervalos de confianza ni criterios oficiales de validez.",
        '4. SEXO=2 de 2024 se muestra sólo con puntos, sin líneas entre edades; su base total es LN=105 y no se presenta como una tendencia histórica comparable. No se mueve ni agrupa ningún punto de edad.',
        '5. Las gráficas anteriores en analysis/charts/descriptive/ se conservan. Los nuevos archivos se escriben exclusivamente en analysis/charts/outliers/.','',
        'Antes (todas las edades):','',
        '![Vista anterior](../charts/descriptive/age_sex_profiles.png)','',
        'Después (vista principal y soporte explícito):','',
        '![Vista revisada](../charts/outliers/age_sex_profiles_reviewed.png)','',
        'Al retirar sólo las coordenadas >100 de la vista principal desaparecen los picos de esas edades y se amplían los detalles del intervalo mostrado. Los puntos no binarios pueden seguir alcanzando 0 % o 100 % por sus denominadores pequeños; se diferencian de las curvas de hombres y mujeres. Ninguna mejora visual valida la plausibilidad de las edades que sí aparecen.','',
        '## LN, SV y NV: conteos elevados y unidad de análisis','',
        stat_table(counts),'',
        'Los cuartiles y conteos atípicos de `source_cell` reproducen la distribución de celdas originales desde sus frecuencias ya auditadas. En `municipality`, cada municipio del año tiene igual peso y el campo es su total, no el valor de una celda. Los resultados no son intercambiables. Los conteos municipales grandes pueden reflejar tamaño territorial; la regla IQR no prueba errores ni autoriza recortes.','',
        markdown_table(['Año','Unidad','Campo','Observaciones fuera IQR','Suma del campo en observaciones fuera IQR'],
            [[r['election_year'],r['level'],r['variable'],number(r['outlier_count']),number(r['outlier_value_sum'])] for r in counts]),'',
        'Las frecuencias univariadas de la auditoría permiten sumar el propio campo señalado, pero no reconstruir conjuntamente los otros conteos de esas mismas celdas. No se inventa esa información ni se relee toda la base para obtenerla. Un mismo registro puede ser atípico en varios campos: no se suman esas frecuencias como observaciones únicas.','',
        '![Conteos y unidades](../charts/outliers/count_boxplots.png)','',
        '## NS como proporción de cobertura','',
        'Se estudia NS/LN municipal, con igual peso por municipio y con peso LN. La media ponderada por LN coincide con NS nacional / LN nacional. La distribución de razones por celda original no puede reconstruirse a partir de los histogramas separados de NS y LN. El IQR=0 del conteo NS original marca cualquier positivo: no sirve por sí solo para concluir que existe un error.','',
        markdown_table(['Año','Peso','Q1 NS/LN','Mediana','Q3','IQR','Límite superior','Municipios fuera IQR','LN de esos municipios','NS de esos municipios','Municipios NS/LN≥10 %','NS/LN nacional'],
            [[r['election_year'],r['weighting'],*[pct(r[c]) for c in ['q1','median','q3','iqr','upper_fence']],number(r['outlier_municipalities']),number(r['outlier_LN']),number(r['outlier_NS']),r['high_NS_municipalities'],pct(r['national_unspecified_rate'])] for r in unspecified]),'',
        'Los límites IQR de una proporción pueden quedar fuera de [0,1]; son referencias estadísticas, no límites de dominio, y no se recortan para cambiar la regla. La no especificación puede reflejar disponibilidad o captura de cuadernillos. No equivale a abstención, participación cero o valores imputables.','',
        '![No especificación municipal](../charts/outliers/unspecified_rate_boxplots.png)','',
        '## Tasas extremas con denominadores pequeños','',
        f"Se revisan los agregados municipio–edad–sexo. Una tasa extrema se define operativamente como ≤5 % o ≥95 %, siempre con SV+NV>0; denominador pequeño significa SV+NV<{manifest['thresholds']['min_specified_count']}. Esta definición es descriptiva y configurable por el contrato; no es una prueba de error ni elimina grupos. Las tasas no definidas se contabilizan aparte.",'',
        markdown_table(['Año','Grupos totales','Tasas extremas','Extremas y denominador pequeño','Filas fuente que representan','LN','SV','NV','NS','Grupos no definidos'],
            [[year,number(all_groups.loc[year,'aggregate_groups']),number(extreme.loc[year,'aggregate_groups']),number(small.loc[year,'aggregate_groups']),*[number(small.loc[year,c]) for c in ['source_row_count',*COUNTS]],number(undefined.loc[year,'aggregate_groups'])] for year in YEARS]),'',
        'Ejemplos deterministas de tasas extremas con denominador pequeño (orden por denominador y claves; no constituyen una selección para limpiar):','',
        markdown_table(['Año','Entidad/municipio','Edad','SEXO','LN','SV+NV','Observada','NS/LN'],
            [[int(r.election_year),f"{r.EDOCVE}/{r.MPIOCVE} · {r.municipality_name_label}",int(r.age_value),r.SEXO,number(r.LN),number(r.specified_count),pct(r.participation_observed),pct(r.unspecified_rate)] for r in examples.itertuples()]),'',
        'Los umbrales 5/95 y 100 son señales para revisar estabilidad del denominador, no probabilidad de que el dato sea falso. Los valores 0 y 1 pueden ser válidos cuando hay uno o pocos registros especificados; los grupos sin especificación son NULL. Los resúmenes de categorías se superponen y no se suman como grupos únicos.','',
        '## Posible influencia en clustering: explicación, sin ejecutar modelos','',
        'K-Means minimiza distancias cuadráticas a centroides. Por ello, si edades o conteos extremos entran en la representación, pueden desplazar centroides y dominar la geometría; el efecto depende de la unidad, variables y escalas elegidas. Es una implicación del objetivo, no un resultado modelado aquí. [Documentación primaria de scikit-learn](https://scikit-learn.org/stable/modules/clustering.html#k-means).','',
        'En clustering jerárquico el efecto depende del enlace: Ward usa variación interna, complete usa distancias máximas, average promedia distancias y single usa mínimos. Los extremos pueden alterar alturas o fusiones, y single puede presentar encadenamiento por puntos puente; no todos los métodos responden igual. Estas son consecuencias posibles de sus definiciones, sin comprobar agrupaciones en ParticipaMX. [Definiciones de enlace de SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html).','',
        'Las tasas extremas con denominadores pequeños y los grupos con NS alto podrían formar perfiles de disponibilidad o ruido si se trataran como igualmente fiables. Los conteos elevados pueden separar tamaños poblacionales en vez de patrones de participación. El límite gráfico 100 no reduce esos riesgos en una futura matriz de análisis, porque no cambia los datos.','',
        '## Decisiones pendientes y validaciones','',
        'Antes del clustering deben decidirse y documentarse: unidad de observación; variables y codificación; relación con tamaño y cobertura; ponderaciones; tratamiento analítico de tasas no definidas y denominadores pequeños; verificación de edades extremas y posibles códigos especiales; continuidad territorial; distancia y enlace o criterio de agrupación; y protocolo de sensibilidad que preserve esta versión completa. Ninguna de estas decisiones se resuelve mediante un boxplot ni por limitar un eje. No se eligió una matriz definitiva, no se normalizó, no se ejecutaron algoritmos y no se corrigió ningún dato.','',
        'Se conciliaron por año los pesos de edad con source_row_count y LN nacionales, los intervalos extremos con su unión EDAD>100 y los conteos con LN=SV+NV+NS. Los cuartiles de filas y conteos originales se contrastaron con la auditoría. El recorrido demográfico concilia todos los conteos con las tablas nacionales y conserva los 105 registros SEXO=2 (LN=105). Los intervalos vacíos y tasas no definidas se mantienen explícitos. Los hashes de ZIP, Parquet limpios, tablas descriptivas, informes de entrada y gráficas anteriores se verificaron antes y después.','',
        f"Reproducir: `.venv/Scripts/python.exe analysis/scripts/analyze_outliers.py`. Evidencia adicional en `{evidence.relative_to(root).as_posix()}`: estadísticas, intervalos, comparación de vistas, tasas extremas y manifiesto con parámetros, versiones y hashes. El script protege los destinos existentes; para otra ejecución elegir rutas nuevas con --charts, --evidence y --report. Las escalas logarítmicas sólo se usan para mostrar frecuencias y conteos, no como normalización ni transformación almacenada de datos.",'']
    text='\n'.join(lines)
    new_prefix=Path(os.path.relpath(charts,report.parent)).as_posix()+'/'
    old_prefix=Path(os.path.relpath(root/'analysis/charts/descriptive',report.parent)).as_posix()+'/'
    text=text.replace('../charts/outliers/',new_prefix).replace('../charts/descriptive/',old_prefix)
    report.write_text(text,encoding='utf-8')


def run_review(root, charts, batch_size=100_000, evidence=None, report=None):
    root,charts=Path(root).resolve(),Path(charts).resolve()
    evidence=Path(evidence).resolve() if evidence else root/'analysis/reports/outliers'
    report=Path(report).resolve() if report else root/'analysis/reports/outlier_review.md'
    require(evidence.is_relative_to(root/'analysis/reports') and report.is_relative_to(root/'analysis/reports'),'Evidencia e informe deben quedar dentro de analysis/reports/.')
    require(not report.exists(),'El informe ya existe; elegir otra ruta con --report.')
    require(charts.is_relative_to(root/'analysis/charts') and not charts.is_relative_to(root/'analysis/charts/descriptive'), 'Destino de gráficas no permitido.')
    require(not charts.exists(), f'El destino ya existe; utilizar otro --charts: {charts}')
    source=root/'data/processed/descriptive'
    manifest_path=source/'metadata/run_manifest.json'
    source_manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    success=json.loads((source/'_SUCCESS').read_text(encoding='utf-8'))
    require(source_manifest['status']=='validated' and success['manifest_sha256']==file_hash(manifest_path),'Agregados no validados.')
    protected={}
    # Verifica archivos binarios sin volver a procesar sus registros.
    for directory in [root/'data/processed/technical_cleaned',source,root/'analysis/charts/descriptive']:
        for path in directory.rglob('*'):
            if path.is_file(): protected[str(path)]=file_hash(path)
    for path in (root/'data/raw').glob('*.zip'): protected[str(path)]=file_hash(path)
    for relative in ['analysis/cleaning_plan.md','analysis/reports/technical_cleaning.md','analysis/reports/descriptive_analysis.md',
                     *[f'analysis/reports/audit_{y}.json' for y in YEARS],*[f'analysis/reports/value_frequencies_{y}.csv' for y in YEARS]]:
        path=root/relative
        protected[str(path)]=file_hash(path)
    for entry in source_manifest['files']:
        require(protected[str(source/entry['path'])]==entry['sha256'],f"Agregado modificado: {entry['path']}")
    thresholds=json.loads((source/'metadata/table_contract.json').read_text(encoding='utf-8'))['thresholds']
    require(not evidence.exists(),'El directorio de evidencia ya existe; no se sobrescribirá.')
    charts.mkdir(parents=True)
    evidence.mkdir(parents=True)
    started=time.monotonic()
    manifest=dict(status='running',thresholds=thresholds,batch_size=batch_size,protected_hashes=protected,
        versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,pyarrow=pa.__version__,matplotlib=matplotlib.__version__),errors=[])
    save_json(evidence/'run_manifest.json',manifest)
    try:
        age=pd.read_parquet(source/'age_sex_year/table.parquet')
        municipalities=pd.read_parquet(source/'municipality/table.parquet')
        annual=pd.read_parquet(source/'year/table.parquet').set_index('election_year')
        age_rows,bands,visibility=age_statistics(age)
        counts=count_statistics(root,municipalities)
        unspecified=unspecified_statistics(municipalities)
        rate_rows,examples,totals=scan_extreme_rates(source,thresholds['min_specified_count'],batch_size)
        for metric in ['source_row_count',*COUNTS]:
            require(totals[metric]==int(annual[metric].sum()),f'Resumen demográfico no conciliado: {metric}')
        require(totals['sex_2_source_rows']==totals['sex_2_nominal_count']==105,'SEXO=2 no conservado.')
        for year in YEARS:
            selected=age[age.election_year.eq(year)]
            for name in ['source_row_count',*COUNTS]:
                require(int(selected[name].sum())==int(annual.loc[year,name]),f'Edades no conciliadas: {year}/{name}')
            audit=json.loads((root/f'analysis/reports/audit_{year}.json').read_text(encoding='utf-8'))
            stats=next(r for r in age_rows if r['election_year']==year and r['weighting']=='source_row_count')
            for key in ['q1','median','q3','lower_fence','upper_fence']:
                require(stats[key]==audit['statistics']['EDAD'][key],f'Cuartil de edad distinto de auditoría: {year}/{key}')
            for row in [r for r in counts if r['election_year']==year and r['level']=='source_cell']:
                baseline=audit['statistics'][row['variable']]
                for key in ['q1','median','q3','mean','std']:
                    require(np.isclose(row[key],baseline[key]),f'Estadística de conteo distinta: {year}/{key}')
                require(row['outlier_count']==baseline['lower_outliers']+baseline['upper_outliers'],'Atípicos de conteos no conciliados.')
            expected=selected.loc[selected.age_value.gt(100),['source_row_count',*COUNTS]].sum()
            for name in ['source_row_count',*COUNTS]:
                require(sum(r[name] for r in bands if r['election_year']==year)==int(expected[name]),'Intervalos extremos no conciliados.')
        for filename,rows in [('age_statistics.csv',age_rows),('age_intervals.csv',bands),('visibility_comparison.csv',visibility),
                              ('count_statistics.csv',counts),('unspecified_statistics.csv',unspecified),('extreme_rate_summary.csv',rate_rows)]:
            serial=[{key:value for key,value in row.items() if key!='fliers'} for row in rows]
            save_csv(evidence/filename,list(serial[0]),serial)
        examples.to_csv(evidence/'extreme_rate_examples.csv',index=False,encoding='utf-8-sig')
        plot_age_boxes(age_rows,charts)
        plot_reviewed_profiles(age,charts,thresholds)
        plot_age_extremes(age,charts)
        plot_count_boxes(counts,charts)
        plot_unspecified(unspecified,charts)
        write_report(root,charts,evidence,report,age,age_rows,bands,visibility,counts,unspecified,rate_rows,examples,manifest)
        for path,digest in protected.items(): require(file_hash(path)==digest,f'Archivo protegido modificado: {path}')
        manifest.update(status='validated',seconds=round(time.monotonic()-started,2),generated_at_utc=datetime.now(timezone.utc).isoformat(),
            script_sha256=file_hash(Path(__file__)),scanned_demographic_groups=int(source_manifest['table_rows']['municipality_age_sex']),
            hidden_age_totals={name:int(age.loc[age.age_value.gt(100),name].sum()) for name in ['source_row_count',*COUNTS]},
            chart_hashes={p.name:file_hash(p) for p in charts.glob('*.png')})
        save_json(evidence/'run_manifest.json',manifest)
        print(f"VALIDADO: revisión de agregados; {len(manifest['chart_hashes'])} gráficas nuevas; informe: analysis/reports/outlier_review.md",flush=True)
        return manifest
    except Exception as error:
        manifest['status']='failed'
        manifest['errors'].append(dict(type=type(error).__name__,message=str(error)))
        save_json(evidence/'run_manifest.json',manifest)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/outliers'))
    parser.add_argument('--batch-size',type=int,default=100_000)
    parser.add_argument('--evidence',type=Path,default=Path('analysis/reports/outliers'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/outlier_review.md'))
    args=parser.parse_args()
    root=args.root.resolve()
    charts=args.charts if args.charts.is_absolute() else root/args.charts
    require(args.batch_size>0,'batch-size debe ser positivo.')
    evidence=args.evidence if args.evidence.is_absolute() else root/args.evidence
    report=args.report if args.report.is_absolute() else root/args.report
    run_review(root,charts,args.batch_size,evidence,report)


if __name__=='__main__':
    main()
