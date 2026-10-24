"""Construye candidatos por reglas explícitas; no entrena ni modifica fuentes.

Las tasas nacionales usan todos los conteos antes del control de soporte.
Los candidatos tienen unidad municipio × intervalo × sexo, nunca personas.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse
import json
import platform
from pathlib import Path
import time

import numpy as np
import pandas as pd
from clean_data import file_hash, require
from build_descriptive import METRICS, compare_sums
from build_cluster_features import snapshot_inputs
from evaluate_participation_patterns import atomic_bytes, write_table, save_figure, safe_ratio, utc

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BANDS = ['18-34', '35-59', '60-100']
KEYS = ['EDOCVE', 'MPIOCVE', 'age_band', 'SEXO']
MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
PROFILE_KEYS = ['EDOCVE', 'MPIOCVE', 'SEXO']
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
IDS = {band: name for band, name in zip(BANDS, ['young', 'adult', 'older'])}
AGE_NAMES = {'young': '18–34 años', 'adult': '35–59 años', 'older': '60–100 años'}
SEX_NAMES = {'0': 'Hombres', '1': 'Mujeres', '2': 'No binario'}
COUNTS = ['LN', 'SV', 'NV', 'NS']
NEAR_THRESHOLD = .02


def write_json(path, value):
    """JSON estricto: NaN/Infinity no son datos intercambiables con React."""
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'))


def table_text(frame):
    """Escapa barras para conservar tablas Markdown válidas."""
    def cell(value):
        if isinstance(value, (float, np.floating)):
            return 'n/d' if not np.isfinite(value) else f'{value:,.4f}'
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, frame.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in frame.itertuples(index=False, name=None)])


def national_reference(frame):
    """Referencia de todos los segmentos, incluidos los de soporte insuficiente."""
    result = frame.groupby(['age_band', 'SEXO'], as_index=False, observed=True)[METRICS].sum()
    result['national_specified_count'] = result.SV + result.NV
    result['national_rate'] = safe_ratio(result.SV, result.national_specified_count)
    return result


def exact_direction(sv, denominator, national_sv, national_denominator):
    """El empate se decide con enteros Python, sin tolerancias flotantes."""
    return np.array([0 if int(d) == 0 or int(nd) == 0 else
                     (1 if int(s)*int(nd) > int(ns)*int(d) else
                      -1 if int(s)*int(nd) < int(ns)*int(d) else 0)
                     for s, d, ns, nd in zip(sv, denominator, national_sv, national_denominator)], dtype=np.int8)


def assign_candidates(frame):
    """Conserva todas las filas y separa regla, soporte y disponibilidad."""
    require(not frame.duplicated(KEYS).any(), 'Segmentos duplicados.')
    require(frame.LN.eq(frame.SV + frame.NV + frame.NS).all(), 'Conteos inválidos.')
    result = frame.copy()
    reference = national_reference(frame)
    result = result.merge(reference[['age_band', 'SEXO', 'SV', 'national_specified_count', 'national_rate']].rename(
        columns={'SV': 'national_SV'}), on=['age_band', 'SEXO'], validate='many_to_one')
    result['specified_count'] = result.SV + result.NV
    result['local_turnout'] = safe_ratio(result.SV, result.specified_count)
    result['participation_delta'] = result.local_turnout - result.national_rate
    result['unspecified_rate'] = safe_ratio(result.NS, result.LN)
    result['in_scope'] = result.age_band.isin(BANDS) & result.SEXO.isin(['0', '1'])
    result['low_ln'] = result.LN.lt(100)
    result['low_specified'] = result.specified_count.lt(100)
    result['few_source_rows'] = result.source_row_count.lt(5)
    result['sufficient_support'] = ~(result.low_ln | result.low_specified | result.few_source_rows)
    result['high_ns'] = result.unspecified_rate.ge(.10)
    result['direction'] = exact_direction(result.SV, result.specified_count, result.national_SV, result.national_specified_count)
    result['near_reference'] = result.participation_delta.abs().le(NEAR_THRESHOLD)
    result['rule_candidate_id'] = pd.Series(pd.NA, index=result.index, dtype='string')
    for band, prefix in IDS.items():
        for direction, suffix in [(1, 'favorable'), (-1, 'unfavorable')]:
            mask = result.in_scope & result.local_turnout.notna() & result.direction.eq(direction) & result.age_band.eq(band)
            result.loc[mask, 'rule_candidate_id'] = prefix + '_' + suffix
    result['assignment_status'] = np.select([
        ~result.in_scope, result.local_turnout.isna(), ~result.sufficient_support, result.direction.eq(0)
    ], ['complementary', 'undefined_rate', 'insufficient_support', 'at_reference'], default='supported_candidate')
    result['candidate_id'] = result.rule_candidate_id.where(result.assignment_status.eq('supported_candidate'))
    require(result.candidate_id.notna().equals(result.assignment_status.eq('supported_candidate')), 'Asignación no disjunta.')
    return result, reference


def join_r2(segments, assignments):
    """Una sola etiqueta local por municipio/sexo; no expande observaciones."""
    columns = [*PROFILE_KEYS, 'is_eligible', 'pending_reason', 'k2_seed17']
    lookup = assignments[columns].rename(columns={'is_eligible': 'r2_eligible', 'pending_reason': 'r2_pending_reason',
                                                   'k2_seed17': 'r2_label'})
    result = segments.merge(lookup, on=PROFILE_KEYS, how='left', validate='many_to_one')
    require(len(result) == len(segments), 'R2 duplicó segmentos.')
    require(result[METRICS].sum().equals(segments[METRICS].sum()), 'R2 cambió los conteos.')
    return result


def profile_summary(frame, total_ln):
    rows = []
    for candidate, group in frame.groupby('candidate_id', observed=True):
        n, den = len(group), int(group.specified_count.sum())
        expected = float(np.sum(group.specified_count * group.national_rate) / den)
        row = dict(candidate_id=candidate, age_band=group.age_band.iloc[0], segments=n,
                   municipalities=len(group[MUNICIPAL_KEYS].drop_duplicates()), states=group.EDOCVE.nunique(),
                   **{name: int(group[name].sum()) for name in METRICS}, specified_count=den,
                   participation_observed=float(group.SV.sum()/den), matched_peer_reference=expected,
                   participation_delta=float(group.SV.sum()/den-expected),
                   mean_segment_delta=float(group.participation_delta.mean()),
                   delta_q1=float(group.participation_delta.quantile(.25)),
                   delta_median=float(group.participation_delta.median()), delta_q3=float(group.participation_delta.quantile(.75)),
                   delta_min=float(group.participation_delta.min()), delta_max=float(group.participation_delta.max()),
                   near_reference_segments=int(group.near_reference.sum()), near_reference_fraction=float(group.near_reference.mean()),
                   high_ns_segments=int(group.high_ns.sum()), high_ns_fraction=float(group.high_ns.mean()),
                   unspecified_rate=float(group.NS.sum()/group.LN.sum()),
                   nominal_coverage=float(group.LN.sum()/total_ln),
                   women_segment_fraction=float(group.SEXO.eq('1').mean()),
                   women_nominal_fraction=float(group.loc[group.SEXO.eq('1'), 'LN'].sum()/group.LN.sum()),
                   specified_min=int(group.specified_count.min()), specified_median=float(group.specified_count.median()),
                   source_rows_median=float(group.source_row_count.median()),
                   sections_median=float(group.section_count.median()),
                   sections_min=int(group.section_count.min()),
                   low_section_segments=int(group.section_count.lt(5).sum()),
                   r2_missing_segments=int(group.r2_label.isna().sum()))
        for kind in ['U', 'R', 'M']:
            row['nominal_share_'+kind] = float(group['LN_'+kind].sum()/group.LN.sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values('candidate_id').reset_index(drop=True)


def schema_object(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def build_schema():
    """Contrato estándar JSON Schema 2020-12, separado de datos candidatos."""
    text = dict(type='string', minLength=1)
    count = dict(type='integer', minimum=0)
    rate = dict(type=['number', 'null'], minimum=0, maximum=1)
    delta = dict(type=['number', 'null'], minimum=-1, maximum=1)
    strings = dict(type='array', items=text, minItems=1)
    strategy = schema_object({key: text for key in ['evidence', 'objective', 'message', 'channel_hypothesis', 'activity', 'evaluation_metric', 'validation_required']})
    peer = schema_object(dict(sex_code=dict(type='string', enum=['0', '1']), sex_label=text, national_rate=rate,
                              national_SV=count, national_NV=count))
    territory = schema_object(dict(state_code=text, state_name=text, segments=count, LN=count,
                                   share_of_candidate_LN=rate, share_of_state_core_LN=rate))
    card = schema_object(dict(id=text, status=dict(const='candidate'), name=text, definition=text,
        age_band=dict(type='string', enum=BANDS), direction=dict(type='string', enum=['favorable', 'unfavorable']),
        counts=schema_object({key: count for key in [*METRICS, 'specified_count', 'segments', 'municipalities', 'states']}),
        participation=schema_object(dict(observed=rate, matched_peer_reference=rate, delta=delta, mean_segment_delta=delta,
            median_segment_delta=delta, unspecified_rate=rate, near_reference_fraction=rate, high_ns_fraction=rate)),
        coverage=schema_object(dict(nominal_fraction=rate, women_segment_fraction=rate, women_nominal_fraction=rate,
                                    r2_missing_segments=count)),
        context=schema_object({key: rate for key in ['urban_nominal_fraction', 'rural_nominal_fraction', 'mixed_nominal_fraction']}),
        peers=dict(type='array', items=peer, minItems=2, maxItems=2),
        territories=dict(type='array', items=territory, minItems=1),
        chart=text, interpretation=text, strategy=strategy, limitations=strings))
    payload = schema_object(dict(schema_version=dict(const='1.0.0'), election_year=dict(const=2024),
        status=dict(const='candidate'), method=dict(const='rule_based_segmentation'),
        unit=dict(const='municipality_age_band_sex'), rate_unit=dict(const='proportion'),
        near_reference_threshold=dict(const=NEAR_THRESHOLD), population=text,
        profiles=dict(type='array', items=card, minItems=1, maxItems=6)))
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'Candidatos agregados de participación de ParticipaMX', **payload}


def validate_contract(value, schema, path='$'):
    """Valida exhaustivamente los keywords usados por este contrato cerrado.

    No sustituye un motor JSON Schema general; rechaza keywords desconocidos.
    El mismo esquema puede consumirse con cualquier validador 2020-12.
    """
    supported = {'$schema', 'title', 'type', 'properties', 'required', 'additionalProperties', 'items',
                 'minItems', 'maxItems', 'minLength', 'minimum', 'maximum', 'const', 'enum'}
    require(set(schema) <= supported, f'Keyword no soportado en {path}.')
    if 'const' in schema:
        require(type(value) is type(schema['const']) and value == schema['const'], f'Constante incorrecta: {path}')
    if 'enum' in schema:
        require(value in schema['enum'], f'Categoría incorrecta: {path}')
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    checks = {'null': value is None, 'object': isinstance(value, dict), 'array': isinstance(value, list),
              'string': isinstance(value, str), 'integer': type(value) is int,
              'number': type(value) in (int, float) and np.isfinite(value)}
    if types:
        require(any(checks[t] for t in types), f'Tipo incorrecto: {path}')
    if value is None:
        return
    if isinstance(value, dict):
        require(set(schema.get('required', [])) <= set(value), f'Campo requerido ausente: {path}')
        properties = schema.get('properties', {})
        require(schema.get('additionalProperties') is not False or set(value) <= set(properties), f'Campo desconocido: {path}')
        for key, item in value.items():
            if key in properties:
                validate_contract(item, properties[key], path+'.'+key)
    elif isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), f'Lista vacía: {path}')
        require(len(value) <= schema.get('maxItems', float('inf')), f'Demasiados elementos: {path}')
        for i, item in enumerate(value):
            validate_contract(item, schema['items'], f'{path}[{i}]')
    elif isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), f'Texto vacío: {path}')
    elif type(value) in (int, float):
        require(np.isfinite(value), f'Número no finito: {path}')
        require(value >= schema.get('minimum', -float('inf')) and value <= schema.get('maximum', float('inf')), f'Fuera de dominio: {path}')


def strategy_for(row):
    favorable = row.candidate_id.endswith('_favorable')
    band = row.age_band
    activity = {'18-34': 'Taller abierto de primera participación y verificación de información electoral.',
                '35-59': 'Módulo abierto de consulta de trámites, calendario y mecanismos de participación.',
                '60-100': 'Jornada accesible de información sobre derechos, asistencia y organización de la jornada.'}[band]
    return dict(evidence=f"En {band}, la diferencia agregada frente a pares es {row.participation_delta*100:+.2f} pp; no identifica motivaciones.",
        objective='Sostener acceso a información cívica y evaluar su alcance.' if favorable else 'Evaluar si información cívica accesible aumenta conocimiento y acceso, sin presumir una causa de menor participación.',
        message='Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.',
        channel_hypothesis='Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.',
        activity=activity + (' Invitar voluntariamente a compartir información oficial, sin asumir liderazgo.' if favorable else ' Recabar barreras declaradas voluntariamente antes de diseñar apoyos.'),
        evaluation_metric='Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.',
        validation_required='Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.')


def make_cards(summary, national, territories):
    cards = []
    for row in summary.itertuples(index=False):
        direction = 'favorable' if row.candidate_id.endswith('_favorable') else 'unfavorable'
        name = AGE_NAMES[row.candidate_id.split('_')[0]] + (' · por encima de sus pares' if direction == 'favorable' else ' · por debajo de sus pares')
        peers = national[national.age_band.eq(row.age_band) & national.SEXO.isin(['0', '1'])]
        states = territories[territories.candidate_id.eq(row.candidate_id)].sort_values(['LN', 'EDOCVE'], ascending=[False, True]).head(3)
        cards.append(dict(id=row.candidate_id, status='candidate', name=name,
            definition=f'Segmentos municipio × sexo H/M × {row.age_band}, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente '+('positiva.' if direction == 'favorable' else 'negativa.'),
            age_band=row.age_band, direction=direction,
            counts={key: int(getattr(row, key)) for key in [*METRICS, 'specified_count', 'segments', 'municipalities', 'states']},
            participation=dict(observed=row.participation_observed, matched_peer_reference=row.matched_peer_reference,
                delta=row.participation_delta, mean_segment_delta=row.mean_segment_delta, median_segment_delta=row.delta_median,
                unspecified_rate=row.unspecified_rate, near_reference_fraction=row.near_reference_fraction, high_ns_fraction=row.high_ns_fraction),
            coverage=dict(nominal_fraction=row.nominal_coverage, women_segment_fraction=row.women_segment_fraction,
                          women_nominal_fraction=row.women_nominal_fraction, r2_missing_segments=row.r2_missing_segments),
            context=dict(urban_nominal_fraction=row.nominal_share_U, rural_nominal_fraction=row.nominal_share_R, mixed_nominal_fraction=row.nominal_share_M),
            peers=[dict(sex_code=x.SEXO, sex_label=SEX_NAMES[x.SEXO], national_rate=x.national_rate, national_SV=int(x.SV), national_NV=int(x.NV)) for x in peers.itertuples()],
            territories=[dict(state_code=x.EDOCVE, state_name=x.state_name_label, segments=int(x.segments), LN=int(x.LN),
                share_of_candidate_LN=x.share_of_candidate_LN, share_of_state_core_LN=x.share_of_state_core_LN) for x in states.itertuples()],
            chart=f'analysis/charts/profile_candidates_review/card_{row.candidate_id}.png',
            interpretation='Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.',
            strategy=strategy_for(row), limitations=[
                f'{row.near_reference_fraction*100:.2f} % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas.',
                'La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza.',
                'Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas.',
                'NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes.',
                'Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.']))
    return dict(schema_version='1.0.0', election_year=2024, status='candidate', method='rule_based_segmentation',
                unit='municipality_age_band_sex', rate_unit='proportion', near_reference_threshold=NEAR_THRESHOLD,
                population='Segmentos H/M de 18–100 con soporte; las demás observaciones se conservan por separado.', profiles=cards)


def build_charts(segments, summary, histories, r2, charts):
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    colors = ['#138a72' if x.endswith('_favorable') else '#b86138' for x in summary.candidate_id]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    axes[0].barh(summary.candidate_id, summary.LN/1e6, color=colors); axes[0].set_xlabel('LN (millones)')
    data = [segments.loc[segments.candidate_id.eq(c), 'participation_delta'].to_numpy()*100 for c in summary.candidate_id]
    axes[1].boxplot(data, vert=False, tick_labels=summary.candidate_id, showfliers=False)
    axes[1].axvspan(-2, 2, color='grey', alpha=.16); axes[1].axvline(0, color='black', lw=.8)
    axes[1].set_xlabel('Diferencia contra pares nacionales (pp)');fig.suptitle('Seis reglas candidatas: tamaño y distribución, no clusters naturales')
    save_figure(fig, charts/'candidate_overview.png')
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout='constrained')
    for ax, row in zip(axes.flat, summary.itertuples()):
        group = segments[segments.candidate_id.eq(row.candidate_id)]
        for sex, color in [('0', '#3972b7'), ('1', '#a95596')]:
            ax.hist(group.loc[group.SEXO.eq(sex), 'participation_delta']*100, bins=np.arange(-70, 71, 2), histtype='step', label=SEX_NAMES[sex], color=color)
        ax.axvspan(-2, 2, color='grey', alpha=.18);ax.axvline(0, color='black', lw=.7)
        ax.set(title=row.candidate_id, xlabel='Diferencia (pp)', ylabel='Segmentos');ax.legend()
    fig.suptitle('Frontera cero y zona descriptiva ±2 pp; frecuencias sin ponderar')
    save_figure(fig, charts/'threshold_distributions.png')
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    bottom = np.zeros(len(summary))
    for kind, label, color in [('U', 'Urbana', '#5486b4'), ('R', 'Rural', '#8aab56'), ('M', 'Mixta', '#dcab5a')]:
        values = summary['nominal_share_'+kind].to_numpy(); ax.bar(summary.candidate_id, values, bottom=bottom, label=label, color=color);bottom += values
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.tick_params(axis='x', rotation=25);ax.legend(ncols=3)
    ax.set(title='Composición LN por tipo de sección electoral', ylabel='Proporción de LN; no residencia individual')
    save_figure(fig, charts/'section_context.png')
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    for (band, sex), g in histories.groupby(['age_band', 'SEXO'], observed=True):
        ax.plot(g.election_year, g.national_rate, marker='o', label=band+' · '+SEX_NAMES[sex])
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_xticks(YEARS);ax.legend(ncols=3)
    ax.set(title='Referencias nacionales: cortes transversales, no seguimiento de personas', ylabel='SV / (SV+NV)')
    save_figure(fig, charts/'historical_peer_references.png')
    pivot = r2.pivot(index='candidate_id', columns='r2_status', values='segments').fillna(0).reindex(summary.candidate_id)
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    proportions = pivot.div(pivot.sum(axis=1), axis=0)
    proportions.plot.bar(stacked=True, ax=ax, rot=25);ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set(title='Contexto R2 por candidato: unión muchos a uno', ylabel='Segmentos; no observaciones R2 independientes', xlabel='')
    save_figure(fig, charts/'r2_context.png')
    for row in summary.itertuples():
        group = segments[segments.candidate_id.eq(row.candidate_id)]
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout='constrained')
        for sex in ['0', '1']:
            g = group[group.SEXO.eq(sex)]
            axes[0].hist(g.participation_delta*100, bins=24, histtype='step', lw=1.6, label=SEX_NAMES[sex])
        axes[0].axvspan(-2, 2, color='grey', alpha=.2);axes[0].axvline(0, color='black', lw=.7)
        axes[0].set(xlabel='Diferencia contra pares (pp)', ylabel='Segmentos');axes[0].legend()
        axes[1].bar(['Observada', 'Referencia\ncon mezcla local'], [row.participation_observed, row.matched_peer_reference], color=['#438f83', '#8997aa'])
        axes[1].set_ylim(0, 1);axes[1].yaxis.set_major_formatter(PercentFormatter(1))
        axes[1].set_title(f'LN={row.LN:,}; {row.municipalities:,} municipios\nNS/LN={row.unspecified_rate:.2%}; cerca de cero={row.near_reference_fraction:.2%}')
        fig.suptitle(row.candidate_id+' · candidato por reglas, 2024')
        save_figure(fig, charts/f'card_{row.candidate_id}.png')


def build_report(summary, status, sensitivity, territories, national, history_summary, context_difference, r2, coverage, antecedents, alternatives, payload, protected_n):
    display = summary[['candidate_id', 'segments', 'municipalities', 'states', 'LN', 'SV', 'NV', 'NS', 'participation_observed',
                       'matched_peer_reference', 'participation_delta', 'nominal_coverage']].copy()
    lines = ['# Candidatos sociodemográficos agregados de participación · 2024', '',
        '**Seis candidatos son viables como segmentación explícita para revisión, no como seis clusters naturales.** Cada uno reúne segmentos con soporte y diferencias medibles frente a pares nacionales; edad y signo de participación definen las etiquetas. El contexto U/R/M enriquece la descripción, pero no valida seis tipos independientes. No se declaran perfiles definitivos.', '',
        'Se propone revisar las seis fichas, mostrar intensidad y advertencia cerca de cero, y conservar R2 como complemento. Reducir a cuatro o cinco no aumenta cobertura: las fusiones diagnósticas sólo eliminan detalle etario o mezclan signos opuestos. La evidencia no exige un número natural de perfiles.', '',
        '## Alcance y alineación con el reto', '',
        'Se atienden los entregables de cuatro a seis perfiles descritos en la solicitud: reglas, caracterización demográfica/territorial, fichas visuales y estrategias cívicas. La convocatoria oficial no está incorporada en el repositorio y la búsqueda pública de esta revisión no localizó una fuente primaria verificable del Reto 1. La conformidad formal con la rúbrica queda pendiente; no se afirma certificación oficial.', '',
        'Se revisaron los informes demographic_pilot, demographic_representation_comparison, participation_pattern_review, pattern_algorithm_comparison, age_band_representation_review, cluster_feature_review, technical_cleaning, outlier_review y el plan de limpieza. Se reutilizan broad/life_stage, contratos, diccionarios oficiales conservados y referencias nacionales. No se entrenó ningún modelo, no se reinterpretaron CSV ni registros limpios.', '',
        'Unidad B = municipio × intervalo × sexo. Unidad R2 = municipio × sexo con tasas de tres edades como coordenadas. Una segmentación por reglas, un clustering aprendido y el comportamiento individual son conceptos distintos. Ningún registro analítico identifica votantes individuales.', '',
        '## Regla, denominadores y población', '',
        'Para cada intervalo y sexo la referencia es ΣSV/Σ(SV+NV), usando **todos** los segmentos originales de 2024 antes de seleccionar soporte. La participación local es SV/(SV+NV), NULL con denominador cero; NS no se suma a NV. El signo se determina por productos cruzados de enteros Python, evitando errores de redondeo y desbordamiento int64. Un empate exacto queda `at_reference`, sin forzarlo a favorable/desfavorable.', '',
        'Las fichas principales requieren H/M, 18–100, LN≥100, SV+NV≥100 y filas fuente≥5, con tasa definida. NS≥10 % advierte cobertura y **no excluye** automáticamente. `rule_candidate_id` conserva la pertenencia por signo de los segmentos definidos sin soporte; `candidate_id` sólo identifica fichas con soporte. `assignment_status` es disjunto; las banderas de calidad pueden superponerse. 101+ y SEXO=2 quedan complementarios sin inventar pares H/M.', '',
        'Las filas fuente son celdas originales, no personas ni secciones independientes. Se mantiene la edad exacta por referencia al Parquet previo y su hash, sin sustituirla por el intervalo. Claves territoriales y SEXO siguen como texto; district_reference_year se conserva.', '',
        table_text(status), '',
        'Las proporciones del informe están en [0,1]; multiplicar por 100 para porcentaje. Las diferencias de proporciones se multiplican por 100 para puntos porcentuales (pp). Los seis candidatos son disjuntos a nivel de segmento y sus conteos sí se suman; sus municipios se superponen y **no** se suman como cobertura única.', '',
        'Referencias nacionales H/M del núcleo:', '', table_text(national[national.age_band.isin(BANDS)&national.SEXO.isin(['0','1'])][['age_band','SEXO','LN','SV','NV','NS','national_rate']]), '',
        '## Tamaño, participación y cobertura', '', table_text(display), '', table_text(pd.DataFrame([coverage])), '',
        'La referencia agregada de cada ficha ajusta la mezcla local de sexo: Σ(denominador del segmento × referencia de su mismo sexo/banda)/Σdenominador. La diferencia agregada resta esa referencia de ΣSV/Σ(SV+NV). Se conserva también media simple, mediana y cuartiles de diferencias, que responden a otra ponderación. No se resta una única tasa nacional incondicional ni se promedian tasas municipales para obtener la participación agregada.', '',
        '![Tamaño y diferencias](../charts/profile_candidates_review/candidate_overview.png)', '',
        table_text(summary[['candidate_id','delta_q1','delta_median','delta_q3','specified_min','specified_median','sections_min','sections_median','low_section_segments','high_ns_fraction','near_reference_fraction']]), '',
        '## Frontera e intensidad: sensibilidad', '',
        'La frontera cero es una convención transparente, no una discontinuidad electoral. Se mide la zona inclusiva abs(Δ)≤1, 2 y 5 pp. Estas bandas son diagnósticos operativos, no errores de estimación ni umbrales oficiales. Los segmentos próximos a cero mantienen su etiqueta provisional y una advertencia; no se afirma que ±0.01 pp describa conductas distintas. La versión conservadora para comunicar diferencias destacaría magnitud y podría dejar esa zona sin rótulo favorable/desfavorable, previa decisión humana.', '',
        table_text(sensitivity), '',
        '![Frontera e intensidad](../charts/profile_candidates_review/threshold_distributions.png)', '',
        'Las bandas descriptivas de no especificación [SV/LN, (SV+NS)/LN] abarcan escenarios extremos de NS, no intervalos de confianza. Se calcula qué segmentos conservarían el signo ante todos esos escenarios respecto de la referencia observada fija. Esto no resuelve la no especificación de la propia referencia nacional; también se guarda el diagnóstico más exigente contra su intervalo NS. No son imputaciones ni predicciones.', '',
        '## Edad, sexo y contexto territorial', '',
        table_text(context_difference), '',
        'Diferencias U/R/M entre signos de la misma edad se expresan como distancia de variación total de composiciones LN (0 idénticas, 1 disjuntas). No demuestran separación natural ni efectos causales. Se muestran volumen por entidad y proporción de su núcleo estatal: el mayor volumen de un estado no equivale a mayor prevalencia relativa. No se inventan regiones socioculturales.', '',
        table_text(territories.sort_values(['candidate_id','LN'],ascending=[True,False]).groupby('candidate_id',observed=True).head(3)[['candidate_id','state_name_label','segments','LN','share_of_candidate_LN','share_of_state_core_LN']]), '',
        '![Secciones electorales](../charts/profile_candidates_review/section_context.png)', '',
        'U/R/M significa sección Urbana/Rural/Mixta del marco electoral, no localidad ni residencia urbana individual. Las sumas LN_U/LN_R/LN_M concilian con cada segmento. Se dispone de secciones distintas **por segmento** y de un inventario territorial general, pero no de sus claves por banda/sexo en los agregados reutilizados. Por eso se informa distribución de section_count y no una suma falsa de secciones únicas por candidato. Una sección puede aportar a ambos sexos y varios candidatos.', '',
        '## Antecedentes de clustering y alternativas de cuatro/cinco', '', table_text(antecedents), '',
        'Estas métricas se reutilizan del piloto B broad/life_stage, K=4/5/6, semilla 17; no son nuevas validaciones de las reglas. En broad se enlazan etiquetas originales a los mismos row_id y se guardan cruces descriptivos. No se calcula ARI entre broad y life_stage ni entre B y R2. Los informes posteriores hallaron gradientes y componentes superpuestas; la nitidez de una regla no prueba existencia de clusters.', '',
        table_text(alternatives), '',
        'Sólo se diagnostican fusiones explícitas sobre los mismos segmentos: cuatro reúne adultos y mayores del mismo signo; cinco reúne ambos signos de mayores. No se cambia la referencia por banda ni se reconstruyen observaciones. La reducción conserva exactamente cobertura/LN, pero aumenta heterogeneidad o mezcla signos: no se promueve una alternativa de cuatro/cinco sin una mejora sustantiva de claridad respaldada por revisión electoral. La tasa y el signo son parte de la definición; no usar Silhouette para “demostrar” esos perfiles.', '',
        '## Complemento R2', '', table_text(r2), '',
        'Se reutiliza R2 K=2, semilla 17. La etiqueta local 0 favorece relativamente el contraste joven frente a mayor y 1 el contraste inverso, según las curvas previas; “favorece” aquí describe forma tras retirar nivel, no participación absoluta alta. Se guardan medias de curvas para verificar esa interpretación. La unión es muchos a uno por entidad/municipio/sexo, sin expandir filas B, y se conserva el estado no disponible. Cada segmento contribuye una vez a los cruces; sus hermanos comparten etiqueta R2 y no son observaciones R2 independientes. R2 nunca determina candidate_id.', '',
        '![R2 como contexto](../charts/profile_candidates_review/r2_context.png)', '',
        '## Historia compatible y límites', '',
        'Los diccionarios conservados definen edad cumplida al día de la elección, H/M y SV/NV/NS de manera comparable. Se verificaron categorías y referencias sobre broad 2009–2024, y sus siete conteos aditivos contra año/entidad descriptivos. Se agregan nacionalmente por las mismas bandas H/M: son cortes transversales repetidos, no trayectorias de personas o municipios. La ausencia histórica de SEXO=2 no significa cero personas de esa categoría.', '',
        table_text(history_summary), '',
        '![Historia de las referencias](../charts/profile_candidates_review/historical_peer_references.png)', '',
        'No existe correspondencia territorial oficial validada. Las claves repetidas no prueban límites constantes; los distritos usan marco 2021 en 2009–2021 y 2023 en 2024. No se publican transiciones municipales de perfiles. Hay NS y disponibilidad de cuadernillos diferentes; presidenciales 2012/2018/2024 e intermedias 2009/2015/2021 tienen contextos distintos. La fuente de cuadernillos no cubre casillas especiales ni voto del extranjero según su diccionario; LN aquí significa el nominal reportado, no un censo validado de personas únicas. No se atribuyen cambios exclusivamente a conducta ciudadana.', '',
        '## Fichas y estrategias preliminares', '',
        'Las propuestas son de educación cívica y participación no partidista. El hallazgo de nivel relativo respalda dónde revisar acceso y cobertura; no demuestra causas ni eficacia de una intervención. Los canales son hipótesis abiertas, sin suponer preferencias por edad o sexo. Las actividades diferenciadas no deben restringir acceso a otros grupos.', '']
    for card in payload['profiles']:
        lines += ['### '+card['name'], '', '`'+card['id']+'` · candidato sujeto a revisión.', '', card['definition'], '',
                  f"LN={card['counts']['LN']:,}; segmentos={card['counts']['segments']:,}; municipios={card['counts']['municipalities']:,}; observada={card['participation']['observed']:.2%}; referencia con mezcla local={card['participation']['matched_peer_reference']:.2%}; diferencia={card['participation']['delta']*100:+.2f} pp.", '',
                  'Sexo: mujeres '+f"{card['coverage']['women_segment_fraction']:.2%} de segmentos y {card['coverage']['women_nominal_fraction']:.2%} del LN.", '',
                  'Entidades destacadas por volumen: '+', '.join(t['state_name'] for t in card['territories'])+'.', '',
                  f"![{card['id']}](../charts/profile_candidates_review/card_{card['id']}.png)", '', card['interpretation'], '']
        for label, field in [('Hallazgo','evidence'),('Objetivo','objective'),('Mensaje','message'),('Canal como hipótesis','channel_hypothesis'),('Actividad','activity'),('Evaluación','evaluation_metric'),('Validación','validation_required')]:
            lines += [f"- **{label}:** {card['strategy'][field]}"]
        lines += ['', 'Limitaciones: '+' '.join(card['limitations']), '']
    lines += ['## Contrato React, validaciones y reproducción', '',
        'Se separan contracts/profile_payload.schema.json (JSON Schema 2020-12), candidates/profile_candidates.json (seis fichas) y examples/profile_payload.example.json (una ficha derivada de las mismas cifras). No son datos publicados ni un contrato definitivo; no se escribió en public/data ni React. Nombres de campos en inglés, textos en español, tasas proporcionales, NULL explícito y JSON sin NaN/Infinity. No hay nombres de personas ni etiquetas individuales.', '',
        'El validador local estricto cubre todos los keywords usados por este esquema y rechaza otros; no pretende implementar JSON Schema general. El esquema estándar permite validación adicional con un motor 2020-12 en la integración. Se prueban campos extra, ausentes, tipos, límites y ejemplos no válidos. Las comprobaciones semánticas adicionales concilian conteos y tasas del payload con los Parquet.', '',
        f'Se verifican conservación de las 17,735 filas B, 9,773,730 filas fuente, LN=98,330,348 y los cuatro conteos; SEXO=2 conserva 105 filas/LN. Se concilian siete métricas por entidad contra descriptivos; referencia nacional original antes del filtro, orden/claves únicas, unión R2 sin expansión, partición de estados, conteos de perfiles, mezclas contextuales y lectura posterior de Parquet. Los hashes de {protected_n:,} archivos previos se verifican antes/después; manifiestos previos se contrastan con sus artefactos relevantes. La base exacta sigue trazable por hash. No se ejecutan modelos ni se crean commits.', '',
        'Resultados: reference/ conserva todos los segmentos y referencias; candidates/ incluye fichas y resumen; diagnostics/ contiene calidad, sensibilidad, sexo, territorio, NS, R2, cruces de modelos y alternativas; historical/ conserva referencias compatibles; contracts/ y examples/ están separados. metadata/run_manifest.json registra versiones, parámetros, fuentes y hashes; _SUCCESS sólo se escribe tras verificar todo.', '',
        '```powershell', '.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/build_profile_candidates.py', '.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_profile_candidates.py', '```', '',
        'Los destinos existentes se rechazan: para repetir usar --output, --charts y --report nuevos. No se sobrescriben resultados anteriores.', '',
        '## Respuestas para la decisión y pendientes', '',
        '1. **Seis viables:** sí como candidatos por reglas con soporte y advertencias; no seis clases naturales demostradas.',
        '2. **Diferenciación:** la edad y el signo son explícitos; intensidad y contexto se cuantifican. U/R/M se superpone y no convierte los cortes en tipos separados.',
        '3. **Tamaño/cobertura:** tablas y fichas anteriores, con LN, segmentos y cobertura municipal no aditiva.',
        '4. **Fronteras:** cero e intervalos son convencionales; la zona ±2 pp debe mostrarse y revisarse, no ocultarse.',
        '5. **Número:** revisar seis como matriz informativa; cuatro/cinco no ganan cobertura y sus fusiones pierden información. No seleccionar número definitivo por narrativa.',
        '6. **R2:** aporta forma relativa joven–mayor por municipio/sexo, sin determinar las etiquetas principales ni fingir concordancia de unidades.',
        '7. **Estrategias:** información cívica accesible, talleres y evaluación de conocimiento/alcance; eficacia, barreras y canales siguen siendo hipótesis.',
        '8. **React:** fichas candidatas, conteos, tasas, referencias por sexo, cobertura, contexto, territorios, estrategias y limitaciones, con contrato separado; publicación pendiente.',
        '9. **Jurado:** agregación ecológica, gradientes, reglas arbitrarias, NS, soporte desigual, categorías complementarias y comparabilidad histórica limitada. No inferir motivación ni comportamiento individual.',
        '10. **Siguiente revisión:** cotejar convocatoria oficial y rúbrica, validar interpretación electoral y lenguaje, acordar zona neutral/umbral, revisar cobertura territorial y privacidad de presentación, validar estrategias con población, confirmar diccionario/contrato en React y aprobar fichas/documento técnico definitivos. No se resuelven esos pendientes mediante nuevos clusters.', '']
    return '\n'.join(lines)


def run(root, output, charts, report):
    start = time.perf_counter()
    require(not output.exists() and not charts.exists() and not report.exists(), 'Destino existente; elegir rutas nuevas.')
    print('A: protección de entradas y comprobación de manifiestos', flush=True)
    protected = snapshot_inputs(root, output, charts)
    for folder in ['analysis/scripts', 'src', 'public', 'docs']:
        for path in (root/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ['.pyc']:
                protected[str(path)] = file_hash(path)
    # La validación no modifica scripts: sus hashes se registran como fuentes.
    output.mkdir(parents=True);charts.mkdir(parents=True)
    manifest = dict(status='running', started_at_utc=utc(), protected_hashes=protected,
                    parameters=dict(min_LN=100, min_specified_count=100, min_source_rows=5,
                                    high_ns=.10, near_reference=NEAR_THRESHOLD, intensity_thresholds=[.01,.02,.05]),
                    versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__), errors=[])
    manifest_path = output/'metadata/run_manifest.json'
    write_json(manifest_path, manifest)
    try:
        sources = ['contextual_feature_review', 'demographic_pilot', 'participation_pattern_review',
                   'pattern_algorithm_comparison', 'age_band_representation_review', 'cluster_features']
        for source in sources:
            folder = root/'data/processed'/source
            previous = json.loads((folder/'metadata/run_manifest.json').read_text(encoding='utf-8'))
            marker = json.loads((folder/'_SUCCESS').read_text(encoding='utf-8'))
            require(previous['status']=='validated', 'Experimento no validado: '+source)
            require(marker['manifest_sha256']==file_hash(folder/'metadata/run_manifest.json'), 'Marcador incoherente: '+source)
            # Contrasta todos los hashes declarados de artefactos; pueden ser rutas relativas a raíz o absolutas.
            declared = previous.get('artifact_hashes', {})
            for name, digest in declared.items():
                path = Path(name) if Path(name).is_absolute() else root/name
                if not path.exists():
                    path = folder/name
                require(path.exists() and file_hash(path)==digest, 'Artefacto previo alterado: '+name)
        input_path = root/'data/processed/contextual_feature_review/reference/context_segments_broad.parquet'
        raw = pd.read_parquet(input_path)
        matrix = pd.read_parquet(root/'data/processed/cluster_features/matrices/b_broad/metadata.parquet')
        compare_sums(raw, matrix, KEYS)
        for key in ['EDOCVE', 'MPIOCVE', 'SEXO']:
            require(raw[key].map(lambda x:isinstance(x,str)).all(), 'Código no textual: '+key)
        require(len(raw)==17735 and int(raw.source_row_count.sum())==9773730, 'Población B inesperada.')
        segments, national = assign_candidates(raw.drop(columns=['national_rate','national_SV','national_specified_count'],errors='ignore'))
        require(np.allclose(segments.participation_delta, segments.participation_deviation_national, equal_nan=True), 'Referencia previa distinta.')
        old_reference = pd.read_csv(root/'data/processed/demographic_pilot/metadata/national_reference_broad.csv',dtype={'SEXO':str})
        # Las columnas nacionales previas se verifican mediante los conteos, no sólo sus tasas.
        compare_sums(national, old_reference, ['age_band','SEXO'])
        for kind in ['U','R','M']:
            require(raw['LN_'+kind].ge(0).all(), 'Contexto negativo.')
        require(raw[[f'LN_{k}' for k in ['U','R','M']]].sum(axis=1).eq(raw.LN).all(), 'Mezcla U/R/M no concilia.')
        for field in COUNTS:
            require(raw[[field+'_'+k for k in ['U','R','M']]].sum(axis=1).eq(raw[field]).all(), 'Conteos contextuales distintos.')
        r2_input = pd.read_parquet(root/'data/processed/participation_pattern_review/assignments/r2.parquet')
        segments = join_r2(segments, r2_input)
        state = pd.read_parquet(root/'data/processed/descriptive/state/table.parquet')
        compare_sums(segments, state[state.election_year.eq(2024)], ['EDOCVE'])
        require(segments.loc[segments.SEXO.eq('2'),'source_row_count'].sum()==105, 'SEXO=2 alterado.')
        require(segments.loc[segments.SEXO.eq('2'),'LN'].sum()==105, 'LN SEXO=2 alterado.')
        write_table(output/'reference/segments_2024.parquet',segments)
        write_table(output/'reference/national_reference.parquet',national)
        write_table(output/'reference/pending_segments.parquet',segments[segments.candidate_id.isna()])
        exact_path = root/'data/processed/cluster_features/reference/exact_age_2024.parquet'
        write_json(output/'reference/exact_age_reference.json',dict(path=str(exact_path.relative_to(root)),sha256=file_hash(exact_path),modified=False))
        print('B: auditoría de candidatos, umbrales y contexto',flush=True)
        supported = segments[segments.candidate_id.notna()].copy()
        total_ln = int(segments.LN.sum())
        summary = profile_summary(supported,total_ln)
        require(len(summary)==6, 'No hay seis candidatos con respaldo: revisar diagnóstico antes de publicar fichas.')
        require(summary[METRICS].sum().equals(supported[METRICS].sum()), 'Resumen no conserva conteos.')
        write_table(output/'candidates/summary.parquet',summary)
        status = segments.groupby('assignment_status',as_index=False,observed=True).agg(segments=('LN','size'),LN=('LN','sum'),SV=('SV','sum'),NV=('NV','sum'),NS=('NS','sum'),source_row_count=('source_row_count','sum'))
        write_table(output/'diagnostics/assignment_status.csv',status)
        quality = segments.groupby(['assignment_status','low_ln','low_specified','few_source_rows','high_ns'],as_index=False,observed=True).agg(segments=('LN','size'),LN=('LN','sum'))
        write_table(output/'diagnostics/quality_reasons.csv',quality)
        sensitivity = []
        for threshold in [.0,.01,.02,.05]:
            for candidate, g in supported.groupby('candidate_id',observed=True):
                near=g.participation_delta.abs().le(threshold)
                sensitivity.append(dict(candidate_id=candidate,threshold_pp=threshold*100,near_segments=int(near.sum()),near_fraction=float(near.mean()),
                                        near_LN=int(g.loc[near,'LN'].sum()),strong_segments=int((~near).sum()),strong_LN=int(g.loc[~near,'LN'].sum())))
        sensitivity=pd.DataFrame(sensitivity);write_table(output/'diagnostics/threshold_sensitivity.csv',sensitivity)
        territorial = supported.groupby(['candidate_id','EDOCVE','state_name_label'],as_index=False,observed=True).agg(segments=('LN','size'),municipalities=('MPIOCVE','nunique'),**{x:(x,'sum') for x in METRICS})
        core_state=segments[segments.in_scope].groupby('EDOCVE').LN.sum()
        territorial['share_of_candidate_LN']=territorial.LN/territorial.candidate_id.map(summary.set_index('candidate_id').LN)
        territorial['share_of_state_core_LN']=territorial.LN/territorial.EDOCVE.map(core_state)
        write_table(output/'diagnostics/territorial_distribution.parquet',territorial)
        sex=supported.groupby(['candidate_id','SEXO'],as_index=False,observed=True)[METRICS].sum()
        sex['segments']=supported.groupby(['candidate_id','SEXO'],observed=True).size().to_numpy()
        write_table(output/'diagnostics/sex_composition.csv',sex)
        context=[]
        for band in BANDS:
            pair=summary[summary.age_band.eq(band)].set_index('candidate_id')
            a=pair.loc[IDS[band]+'_favorable'];b=pair.loc[IDS[band]+'_unfavorable']
            context.append(dict(age_band=band,context_total_variation=float(sum(abs(a['nominal_share_'+k]-b['nominal_share_'+k]) for k in ['U','R','M'])/2),
                                mean_delta_gap_pp=float((a.mean_segment_delta-b.mean_segment_delta)*100),
                                median_delta_gap_pp=float((a.delta_median-b.delta_median)*100),
                                women_segment_fraction_gap=float(a.women_segment_fraction-b.women_segment_fraction)))
        context=pd.DataFrame(context);write_table(output/'diagnostics/context_comparison.csv',context)
        ns=supported[['row_id','candidate_id','LN','SV','NV','NS','national_SV','national_specified_count','national_rate','participation_delta','high_ns']].copy()
        ns['local_lower']=ns.SV/ns.LN;ns['local_upper']=(ns.SV+ns.NS)/ns.LN
        ns['sign_robust_fixed_reference']=np.where(ns.participation_delta.gt(0),ns.local_lower.gt(ns.national_rate),ns.local_upper.lt(ns.national_rate))
        peer=segments[['age_band','SEXO','national_rate']].drop_duplicates().merge(national[['age_band','SEXO','LN','SV','NS']],on=['age_band','SEXO'],validate='one_to_one')
        peer['peer_lower']=peer.SV/peer.LN;peer['peer_upper']=(peer.SV+peer.NS)/peer.LN
        ns=ns.merge(supported[['row_id','age_band','SEXO']],on='row_id',validate='one_to_one').merge(peer[['age_band','SEXO','peer_lower','peer_upper']],on=['age_band','SEXO'],validate='many_to_one')
        ns['sign_robust_both_bounds']=np.where(ns.participation_delta.gt(0),ns.local_lower.gt(ns.peer_upper),ns.local_upper.lt(ns.peer_lower))
        write_table(output/'diagnostics/ns_sensitivity.parquet',ns)
        ns_summary=ns.groupby('candidate_id',as_index=False,observed=True).agg(segments=('LN','size'),high_ns_segments=('high_ns','sum'),robust_fixed_reference=('sign_robust_fixed_reference','sum'),robust_both_bounds=('sign_robust_both_bounds','sum'))
        write_table(output/'diagnostics/ns_summary.csv',ns_summary)
        supported['r2_status']=supported.r2_label.map({0:'r2_0',1:'r2_1'}).fillna('unavailable')
        r2=supported.groupby(['candidate_id','r2_status'],as_index=False,observed=True).agg(segments=('LN','size'),**{x:(x,'sum') for x in METRICS})
        r2['within_candidate_segment_fraction']=r2.segments/r2.candidate_id.map(summary.set_index('candidate_id').segments)
        write_table(output/'diagnostics/r2_crosswalk.csv',r2)
        r2_profiles=pd.read_parquet(root/'data/processed/participation_pattern_review/reference/profiles.parquet')
        r2_curves=r2_profiles.merge(r2_input[[*PROFILE_KEYS,'k2_seed17']],on=PROFILE_KEYS,validate='one_to_one').groupby('k2_seed17',as_index=False,observed=True)[['shape_18_34','shape_35_59','shape_60_100']].mean()
        write_table(output/'diagnostics/r2_curves.csv',r2_curves)
        coverage=dict(available_segments=len(segments),classified_segments=len(supported),municipalities=len(supported[MUNICIPAL_KEYS].drop_duplicates()),
            original_municipalities=len(segments[MUNICIPAL_KEYS].drop_duplicates()),LN=int(supported.LN.sum()),nominal_fraction=float(supported.LN.sum()/total_ln),
            high_ns_segments=int(supported.high_ns.sum()),near_reference_fraction=float(supported.near_reference.mean()))
        write_json(output/'diagnostics/coverage.json',coverage)
        # Fusiones de diagnóstico: no crean fichas ni se interpretan como clusters.
        alternatives=[]
        for design in ['six','four','five']:
            labels=supported.candidate_id.copy()
            if design=='four':
                labels=labels.str.replace('adult_','adult_older_',regex=False).str.replace('older_','adult_older_',regex=False)
                # Asignación explícita evita reemplazos repetidos del prefijo compuesto.
                labels=supported.candidate_id.map(lambda x: 'adult_older_'+x.split('_',1)[1] if not x.startswith('young_') else x)
            elif design=='five':
                labels=supported.candidate_id.map(lambda x:'older_all' if x.startswith('older_') else x)
            g=supported.assign(design_id=labels)
            means=g.groupby('design_id',observed=True).participation_delta.transform('mean')
            mixed=g.groupby('design_id',observed=True).direction.nunique().gt(1)
            alternatives.append(dict(design=design,groups=int(labels.nunique()),segments=len(g),LN=int(g.LN.sum()),
                                     within_group_delta_sd_pp=float(np.sqrt(np.mean((g.participation_delta-means)**2))*100),
                                     groups_mixing_signs=int(mixed.sum()),coverage_gain=0))
        alternatives=pd.DataFrame(alternatives);write_table(output/'diagnostics/alternative_mergers.csv',alternatives)
        print('C: antecedentes reutilizados e historia nacional compatible',flush=True)
        metrics=pd.read_csv(root/'data/processed/demographic_pilot/metadata/model_metrics.csv')
        antecedents=metrics[metrics.scheme.isin(['broad','life_stage'])&metrics.scaling.eq('standard')&metrics.scope.eq('joint')&metrics.scenario.eq('main')&metrics.seed.eq(17)&metrics.k.isin([4,5,6])][['scheme','k','n','silhouette','age_r2','age_band_purity','within_age_sex_rate_r2']]
        write_table(output/'diagnostics/clustering_antecedents.csv',antecedents)
        old_labels=pd.read_parquet(root/'data/processed/demographic_pilot/contexts/broad_standard_joint_main/labels.parquet')
        joined=segments[['row_id','candidate_id','assignment_status',*KEYS,*METRICS]].merge(old_labels[['row_id','k04_seed17','k05_seed17','k06_seed17']],on='row_id',validate='one_to_one')
        require(len(joined)==len(segments),'Cruce con B incompleto.')
        write_table(output/'diagnostics/previous_b_labels.parquet',joined)
        for k in [4,5,6]:
            label=f'k{k:02d}_seed17'
            cross=joined.groupby(['candidate_id',label],as_index=False,observed=True,dropna=False).agg(segments=('LN','size'),LN=('LN','sum'))
            write_table(output/f'diagnostics/previous_b_k{k}_crosswalk.csv',cross)
        dictionaries=json.loads((root/'data/processed/descriptive/metadata/source_dictionaries.json').read_text(encoding='utf-8'))
        hist=[];hist_summary=[];reconciliation=[]
        for year in YEARS:
            text=' '.join(item['text'] for item in dictionaries[str(year)])
            require(all(word in text for word in ['SV','NV','NS','EDAD','Hombres','Mujeres']), 'Diccionario incompatible.')
            f=pd.read_parquet(root/f'analysis/reports/representation_evaluation/grouped_candidates/broad/part-{year}.parquet')
            require(set(f.age_band)<=set(BANDS+['101+']), 'Intervalo histórico inesperado.')
            require(set(f.SEXO)<=({'0','1','2'} if year==2024 else {'0','1'}), 'Sexo histórico inesperado.')
            compare_sums(f,state[state.election_year.eq(year)],['EDOCVE'])
            for entity, g in f.groupby('EDOCVE',observed=True):
                original=state[state.election_year.eq(year)&state.EDOCVE.eq(entity)].iloc[0]
                for metric in METRICS:
                    reconciliation.append(dict(election_year=year,EDOCVE=entity,metric=metric,difference=int(g[metric].sum()-original[metric])))
            national_hist=national_reference(f);national_hist=national_hist[national_hist.age_band.isin(BANDS)&national_hist.SEXO.isin(['0','1'])].copy()
            national_hist['election_year']=year;national_hist['unspecified_rate']=national_hist.NS/national_hist.LN
            hist.append(national_hist)
            hist_summary.append(dict(election_year=year,election_type='presidential' if year in [2012,2018,2024] else 'midterm',
                                     municipalities=len(f[MUNICIPAL_KEYS].drop_duplicates()),core_LN=int(national_hist.LN.sum()),
                                     participation_observed=float(national_hist.SV.sum()/(national_hist.SV.sum()+national_hist.NV.sum())),
                                     unspecified_rate=float(national_hist.NS.sum()/national_hist.LN.sum())))
        histories=pd.concat(hist,ignore_index=True);history_summary=pd.DataFrame(hist_summary)
        write_table(output/'historical/national_peer_references.parquet',histories)
        write_table(output/'historical/compatibility_summary.csv',history_summary)
        write_table(output/'metadata/state_reconciliation.csv',pd.DataFrame(reconciliation))
        require(pd.DataFrame(reconciliation).difference.eq(0).all(),'Historia no conciliada.')
        print('D: fichas, contrato, gráficas y validación final',flush=True)
        payload=make_cards(summary,national,territorial)
        schema=build_schema();validate_contract(payload,schema)
        example={**payload,'profiles':payload['profiles'][:1]};validate_contract(example,schema)
        write_json(output/'contracts/profile_payload.schema.json',schema)
        write_json(output/'candidates/profile_candidates.json',payload)
        write_json(output/'examples/profile_payload.example.json',example)
        require(sum(p['counts']['LN'] for p in payload['profiles'])==int(supported.LN.sum()),'JSON no concilia.')
        build_charts(segments,summary,histories,r2,charts)
        text=build_report(summary,status,sensitivity[sensitivity.threshold_pp.eq(2)],territorial,national,history_summary,context,r2,coverage,antecedents,alternatives,payload,len(protected))
        atomic_bytes(report,text.encode('utf-8'))
        # Incluye resultados NS en evidencia y en el informe sin inventar robustez.
        with report.open('a',encoding='utf-8') as stream:
            stream.write('\n## Sensibilidad explícita a NS\n\n'+table_text(ns_summary)+'\n\nLos conteos robustos son escenarios extremos descriptivos, no probabilidades ni intervalos de confianza.\n')
        for name,digest in protected.items():
            require(file_hash(Path(name))==digest,'Archivo protegido modificado: '+name)
        for candidate in payload['profiles']:
            require((charts/f"card_{candidate['id']}.png").exists(),'Ficha sin gráfica.')
        for file in output.rglob('*.parquet'):
            pd.read_parquet(file)
        validate_contract(json.loads((output/'candidates/profile_candidates.json').read_text(encoding='utf-8')),schema)
        manifest.update(status='validated',finished_at_utc=utc(),seconds=time.perf_counter()-start,protected_files=len(protected),
                        model_fits=0,coverage=coverage,report_sha256=file_hash(report),
                        artifact_hashes={str(p.relative_to(root)):file_hash(p) for p in [*output.rglob('*'),*charts.rglob('*'),report]
                                         if p.is_file() and p!=manifest_path},
                        validation=dict(state_checks=len(reconciliation),count_conservation=True,json_contract=True,parquet_roundtrip=True,protected_unchanged=True))
        write_json(manifest_path,manifest)
        write_json(output/'_SUCCESS',dict(status='validated',manifest_sha256=file_hash(manifest_path)))
        print(json.dumps(dict(status='validated',coverage=coverage,seconds=time.perf_counter()-start),ensure_ascii=False),flush=True)
    except Exception as exc:
        manifest.update(status='failed',errors=[repr(exc)],finished_at_utc=utc());write_json(manifest_path,manifest)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/processed/profile_candidates_review')
    parser.add_argument('--charts',default='analysis/charts/profile_candidates_review')
    parser.add_argument('--report',default='analysis/reports/profile_candidates_review.md')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    paths=[(root/Path(x)).resolve() for x in [args.output,args.charts,args.report]]
    require(all(p.is_relative_to(root) for p in paths),'Destinos fuera del proyecto.')
    run(root,*paths)


if __name__=='__main__':
    main()
