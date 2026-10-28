"""Contenido editorial en español y renderizado de fichas experimentales."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from build_profile_naming import ORDER, SECTION, SEX, table_markdown


DESCRIPTIONS = {
    "young_favorable": "Estos segmentos de 18–34 años reúnen la mayor diferencia positiva agregada de las seis fichas: +7.69 puntos frente a su referencia. La intensidad varía entre municipios. El cruce por sexo y tipo de sección electoral muestra diferencias internas, aunque sus composiciones U/R/M se parecen a las de la otra categoría joven. La etiqueta agregada tampoco describe todos sus subsegmentos.",
    "young_unfavorable": "Estos segmentos de 18–34 años registran la participación absoluta más baja de las seis fichas: 43.26 %. La comparación válida es con su referencia de 50.10 %, ajustada a la mezcla de sexo. El cruce por tipo de sección electoral muestra resultados diferentes dentro de la misma edad y sexo; algunos subsegmentos incluso cambian de signo respecto de su categoría agregada.",
    "adult_favorable": "Estos segmentos de 35–59 años tienen la presencia municipal más extensa de las seis fichas: 1,641 municipios. Su participación agregada es 69.33 %, frente a una referencia de 62.82 %. Las diferencias positivas son más amplias en secciones electorales rurales que urbanas al resumir esta categoría, pero no abarcan uniformemente a todos sus subsegmentos ni prueban un efecto del contexto.",
    "adult_unfavorable": "Estos segmentos de 35–59 años concentran el mayor volumen nominal de las seis fichas, con 22.44 millones de registros LN. Su participación agregada es 57.00 %, frente a una referencia de 62.96 %. La distancia negativa varía por sexo y tipo de sección electoral. El volumen no equivale a mayor extensión municipal, y algunos subsegmentos presentan una diferencia positiva.",
    "older_favorable": "Estos segmentos de 60–100 años presentan la participación absoluta más alta de las seis fichas: 77.26 %. Su referencia también es elevada, 71.48 %, por lo que la diferencia relativa no es la mayor. Las tasas agregadas por tipo de sección electoral son cercanas, sin demostrar equivalencia estadística ni comportamiento uniforme. Las mujeres predominan en LN, pero no en número de segmentos.",
    "older_unfavorable": "Estos segmentos de 60–100 años muestran la mayor distancia negativa agregada frente a su referencia: −7.34 puntos. Su participación es 64.10 %, una tasa que no es la más baja de las seis fichas. El cruce por sexo y tipo de sección electoral sitúa distancias más amplias en secciones rurales y mixtas, sin describir por igual a todos los subsegmentos.",
}

JOINT_NOTES = {
    "young_favorable": "Entre mujeres de 18–34, la diferencia es +11.34 pp en secciones rurales y +7.04 pp en urbanas; entre hombres es +6.66 y +7.18 pp, respectivamente. El orden rural/urbano cambia según sexo: no existe una única ventaja rural común. La composición U/R/M apenas diferencia las dos fichas jóvenes (variación total 0.0165 en V1).",
    "young_unfavorable": "Entre hombres de 18–34, las secciones rurales registran 33.48 % frente a su referencia de 43.74 % (−10.26 pp), y las urbanas 38.74 % (−5.00 pp). Entre mujeres, la mayor distancia negativa corresponde a mixtas (−10.01 pp), no a rurales (−7.31 pp). Las composiciones U/R/M de ambas fichas jóvenes son similares; no sustentan dos tipos juveniles urbanos/rurales.",
    "adult_favorable": "En 35–59, la diferencia rural es +8.96 pp en hombres y +9.53 pp en mujeres; la urbana es +5.30 y +5.86 pp. Este orden se observa en ambos sexos dentro de la ficha seleccionada. No estima un efecto rural: cambian los municipios y su composición, y las referencias sólo ajustan banda/sexo.",
    "adult_unfavorable": "En 35–59, la distancia urbana es −5.04 pp en hombres y −5.55 pp en mujeres; la mixta es −7.77 y −8.84 pp. El menor alejamiento urbano agregado también aparece al separar sexos. No convierte en positivos todos los segmentos urbanos ni demuestra que la sección determine la participación.",
    "older_favorable": "En 60–100, los hombres registran diferencias de +4.95 a +6.07 pp según tipo de sección; las mujeres, de +5.42 a +6.24 pp. El máximo entre hombres es rural y entre mujeres urbano. Las tasas agregadas U/R/M van de 76.71 % a 77.44 %: una amplitud de 0.73 pp, sin prueba de equivalencia ni homogeneidad local.",
    "older_unfavorable": "En 60–100, las distancias rurales son −9.98 pp en hombres y −9.76 pp en mujeres; las urbanas son −6.10 y −6.22 pp. La diferencia entre los deltas agregados de hombres y mujeres es sólo 0.03 pp; no respalda un nombre centrado en una gran separación por sexo. El contraste observado es contextual, no causal.",
}

LIMIT = "Resume agregados municipales de 2024, no rasgos personales, causas, necesidades ni eficacia de intervenciones. El rango o superlativo se limita a estas seis fichas y no prueba seis clases naturales."
SOURCES = {
    "v1_profiles": {"path": "data/processed/participamx_multiyear/elections/2024/profiles.json", "selector": "data[profile_id=ID]", "fields": ["segments", "municipalities", "LN", "participation_observed", "matched_peer_reference", "participation_delta", "women_segment_fraction", "women_nominal_fraction", "near_reference_fraction", "nominal_share_U", "nominal_share_R", "nominal_share_M"]},
    "v1_segments": {"path": "data/processed/participamx_multiyear/elections/2024/tables/segments.parquet", "selector": "candidate_id=ID; todos sus padres con soporte V1", "fields": ["row_id", "EDOCVE", "MPIOCVE", "age_band", "SEXO", "LN", "SV", "NV", "NS", "specified_count", "participation_delta", "direction", "national_SV", "national_specified_count"]},
    "national_references": {"path": "data/processed/participamx_multiyear/elections/2024/tables/national_references.parquet", "selector": "age_band del perfil; SEXO=0 o 1; antes de seleccionar soporte", "fields": ["SV", "national_specified_count", "national_rate"]},
    "v2_cells": {"path": "analysis/profile_v2/results/reference/all_observations.parquet", "selector": "v1_parent_profile=ID; conservar hijos con y sin soporte", "fields": ["row_id", "age_band", "SEXO", "TIPOSEC", "LN", "SV", "NV", "NS", "source_row_count", "section_count", "is_eligible", "reference_age_sex", "reference_age_sex_section", "v1_parent_delta"]},
    "profile_evidence": {"path": "evidence/profile_summary.csv", "base": "this_output", "selector": "profile_id=ID", "fields": ["delta_pp", "delta_sd_pp", "eligible_cells", "eligible_flip_cells", "eligible_flip_LN", "undefined_cells"]},
    "joint_evidence": {"path": "evidence/profile_sex_section.csv", "base": "this_output", "selector": "profile_id=ID, SEXO, TIPOSEC", "fields": ["LN", "SV", "NV", "NS", "specified_count", "participation_observed", "matched_age_sex_reference", "delta_pp", "eligible_cells", "eligible_flip_cells"]},
    "section_evidence": {"path": "evidence/profile_section.csv", "base": "this_output", "selector": "profile_id=ID, TIPOSEC", "fields": ["share_of_profile_LN", "participation_observed", "matched_age_sex_reference", "delta_pp"]},
    "sex_evidence": {"path": "evidence/profile_sex.csv", "base": "this_output", "selector": "profile_id=ID, SEXO", "fields": ["participation_observed", "matched_age_sex_reference", "delta_pp"]},
    "territory_evidence": {"path": "evidence/profile_state.csv", "base": "this_output", "selector": "profile_id=ID, EDOCVE; ordenar LN descendente", "fields": ["state_name_label", "LN", "share_of_profile_LN", "state_core_LN", "share_of_state_core_LN"]},
    "reversal_evidence": {"path": "evidence/eligible_sign_reversals.parquet", "base": "this_output", "selector": "candidate_id=ID; is_eligible y exact_sign_opposes_parent", "fields": ["row_id", "row_id_parent", "LN", "SV", "NV", "specified_count", "exact_child_direction", "direction", "delta_age_sex", "v1_parent_delta"]},
    "reversal_quality": {"path": "evidence/reversal_quality.csv", "base": "this_output", "selector": "profile_id=ID, population=eligible_children/all_children/pending_children", "fields": ["defined_cells", "flip_cells", "flip_LN", "flip_near_reference_cells", "flip_parent_near_reference_cells", "flip_high_ns_cells", "flip_few_sections_cells"]},
    "v2_review": {"path": "analysis/profile_v2/results/reports/final_recommendation.md", "selector": "Recuperación V1; recomendaciones, alcance y cambios al desagregar"},
    "prior_interpretation": {"path": "analysis/reports/profile_interpretation_2024.md", "selector": "Comparación común; ficha con el mismo ID; variación total de las composiciones jóvenes"},
}


def proposal_specs(profile_id, s, record, sections):
    def item(name, feature, proof, limit, sources):
        return {"name": name, "distinctive_feature": feature, "statistical_justification": proof,
                "limitation": limit, "sources": sources}
    if profile_id == "young_favorable":
        return [
            item("Participación joven con mayor diferencia positiva", "Mayor diferencia positiva agregada de las seis fichas.",
                 f"{record['participation_observed']*100:.2f} % frente a {record['matched_peer_reference']*100:.2f} %; Δ={s['delta_pp']:+.2f} pp, mayor que +6.51 y +5.78 pp de las otras fichas positivas.", LIMIT + " No es la mayor participación absoluta.", ["v1_profiles", "profile_evidence"]),
            item("Participación joven diversa en su intensidad", "Mayor dispersión descriptiva de diferencias entre segmentos V1.",
                 f"DE poblacional sin pesos de Δ={s['delta_sd_pp']:.2f} pp, máximo de las seis; Q1–Q3={record['delta_q1']*100:+.2f} a {record['delta_q3']*100:+.2f} pp.", "La dispersión depende de selección por signo y referencia; no es incertidumbre ni un rasgo exclusivo de toda la juventud.", ["v1_segments", "profile_evidence"]),
            item("Participación joven con contrastes rurales por sexo", "El orden rural/urbano de la diferencia cambia por sexo.",
                 "Mujeres: rural +11.34 pp y urbana +7.04; hombres: rural +6.66 y urbana +7.18, siempre contra su banda/sexo.", "Destaca un cruce descriptivo dentro de una ficha; no identifica residencia ni un efecto causal. Es menos sencillo para una tarjeta.", ["joint_evidence", "v2_cells", "national_references"])]
    if profile_id == "young_unfavorable":
        return [
            item("Participación joven en el nivel más bajo", "Menor tasa absoluta entre las seis fichas.",
                 f"Participación {record['participation_observed']*100:.2f} %, referencia {record['matched_peer_reference']*100:.2f} %, Δ={s['delta_pp']:+.2f} pp. Es el mínimo de las seis tasas, no el mayor déficit relativo.", LIMIT + " No significa desinterés ni permite identificar personas que no votaron.", ["v1_profiles", "profile_evidence"]),
            item("Participación joven con más volumen que extensión", "Más LN pero menos municipios que la otra ficha de 18–34.",
                 "LN=19,495,482 y 1,200 municipios frente a LN=17,237,993 y 1,522 municipios de young_favorable.", "La comparación se limita a las dos fichas jóvenes; extensión es cantidad de municipios, no superficie ni dispersión geográfica.", ["v1_profiles"]),
            item("Participación joven con menor nivel rural masculino", "El cruce masculino rural tiene la menor tasa entre sus seis cruces sexo/tipo.",
                 "Hombres, 18–34, rural: 33.48 %, referencia 43.74 %, Δ=−10.26 pp; urbano masculino: 38.74 %.", "Este subconjunto no representa a todas las mujeres ni a todas las secciones de la ficha. Puede inducir una lectura demasiado parcial del título.", ["joint_evidence", "national_references"])]
    if profile_id == "adult_favorable":
        return [
            item("Participación adulta con mayor presencia municipal", "Máximo número de municipios representados entre las seis fichas.",
                 "3,015 segmentos en 1,641 municipios; participación 69.33 %, referencia 62.82 %, Δ=+6.51 pp.", LIMIT + " Presencia no es prevalencia, superficie ni comportamiento de todos los habitantes; los municipios se superponen entre fichas.", ["v1_profiles"]),
            item("Participación adulta con diferencia rural más amplia", "Dentro de la ficha, la diferencia agregada rural supera la urbana y la mixta.",
                 "Rural +9.27 pp; urbana +5.58; mixta +6.95. Al separar sexos, rural +8.96/+9.53 y urbana +5.30/+5.86 pp (hombres/mujeres).", "No es una ficha exclusivamente rural: sólo 20.34 % de su LN procede de secciones rurales. No hay causalidad demostrada.", ["section_evidence", "joint_evidence"]),
            item("Participación adulta extendida con diferencias internas", "Presencia municipal amplia junto con cambios de signo al desagregar.",
                 f"1,641 municipios y {s['eligible_flip_cells']:,} de {s['eligible_cells']:,} hijos elegibles con signo contrario al padre V1.", "Extendida alude únicamente al número de municipios; la heterogeneidad existe en las seis fichas, de modo que diferencia menos que el primer nombre.", ["v1_profiles", "profile_evidence", "reversal_evidence"])]
    if profile_id == "adult_unfavorable":
        return [
            item("Participación adulta con mayor volumen nominal", "Mayor LN reportado de las seis fichas.",
                 "LN=22,444,975 (22.83 % del LN anual), 1,018 municipios; participación 57.00 %, referencia 62.96 %, Δ=−5.96 pp.", LIMIT + " LN no cuenta personas únicas; mayor volumen no equivale a mayor número de municipios ni a necesidad informativa.", ["v1_profiles"]),
            item("Participación adulta con diferencias urbanas menos amplias", "El alejamiento negativo urbano es menor que rural y mixto dentro de la ficha.",
                 "Urbana −5.32 pp, rural −7.27 y mixta −8.32; ambos sexos mantienen ese menor alejamiento urbano frente a mixto.", "No define una clase urbana ni asegura signo negativo en todos los hijos. La mayoría nominal urbana se comparte con las otras cinco fichas.", ["section_evidence", "joint_evidence"]),
            item("Participación adulta con mayor proporción cercana", "Mayor fracción de padres V1 a no más de 2 pp de la referencia entre las seis fichas.",
                 f"{record['near_reference_segments']}/{record['segments']} segmentos: {record['near_reference_fraction']*100:.2f} %, frente a 9.41–15.54 % en las otras fichas.", "Son sólo 18.22 %, no la mayoría. ±2 pp es una cautela convencional, no equivalencia estadística. El título requiere explicar la referencia en el subtítulo.", ["v1_profiles"])]
    if profile_id == "older_favorable":
        return [
            item("Participación de mayores en el nivel más alto", "Mayor tasa absoluta entre las seis fichas.",
                 "Participación 77.26 %, referencia 71.48 %, Δ=+5.78 pp; no es la mayor diferencia positiva relativa.", LIMIT + " No representa a todas las personas de 60–100 ni permite inferir motivación.", ["v1_profiles"]),
            item("Participación de mayores similar entre secciones electorales", "Pequeña amplitud descriptiva entre las tres tasas agregadas por tipo de sección de la ficha.",
                 "Urbana 77.30 %, rural 77.44 % y mixta 76.71 %; amplitud 0.73 pp. Sus referencias mezcladas están entre 71.45 % y 71.60 %.", "Similar es descriptivo, sin prueba de equivalencia. Las medias cercanas no eliminan variación municipal ni cambios de signo locales.", ["section_evidence", "joint_evidence"]),
            item("Participación de mayores con mayoría nominal femenina", "El predominio por LN difiere del predominio por número de segmentos.",
                 "Mujeres: 53.16 % del LN, pero 46.93 % de segmentos; participación femenina 76.91 %, referencia 70.84 %.", "La mayoría es moderada y no exclusiva de esta ficha; no describe residencia ni efecto del sexo. Se prefiere el primer nombre para distinguir las seis.", ["v1_profiles", "sex_evidence"])]
    return [
        item("Participación de mayores con mayor distancia negativa", "Mayor déficit relativo agregado entre las seis fichas.",
             "Participación 64.10 %, referencia 71.44 %, Δ=−7.34 pp, frente a −6.83 y −5.96 de las otras fichas negativas.", LIMIT + " La tasa absoluta no es la menor: supera incluso el 57.39 % de la ficha joven positiva.", ["v1_profiles"]),
        item("Participación de mayores con distancia rural más amplia", "La distancia negativa rural supera en magnitud a urbana y mixta dentro de esta ficha.",
             "Rural −9.86 pp, urbana −6.17 y mixta −9.35; en rural son −9.98 para hombres y −9.76 para mujeres.", "La mayoría del LN procede de secciones urbanas (66.43 %). El nombre destaca un subconjunto, no toda la ficha ni un efecto causal.", ["section_evidence", "joint_evidence", "v1_profiles"]),
        item("Participación de mayores con menor volumen nominal", "Menor LN entre las seis fichas.",
             "LN=8,319,793 (8.46 % del anual), 2,078 segmentos en 1,189 municipios; participación 64.10 %.", "Volumen pequeño entre estas categorías no significa baja cobertura dentro de cada municipio, minoría individual ni escaso interés electoral.", ["v1_profiles"])]


def source_links(ids):
    return ", ".join(f"[{key}](source_catalog.md#{key.replace('_', '-')})" for key in ids)


def build_card(profile_id, tables, published, examples):
    record = published[profile_id]
    s = tables["profile_summary"].set_index("profile_id").loc[profile_id].to_dict()
    subset = lambda name: tables[name][tables[name].profile_id.eq(profile_id)].copy()
    joint, sections, sex, states = [subset(k) for k in ["profile_sex_section", "profile_section", "profile_sex", "profile_state"]]
    specs = proposal_specs(profile_id, s, record, sections)
    subtitle = (f"{record['age_band'].replace('-', '–')} años · {record['participation_observed']*100:.2f} % de participación observada; "
        f"referencia comparable {record['matched_peer_reference']*100:.2f} % ({s['delta_pp']:+.2f} pp). "
        "Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.")
    for index, spec in enumerate(specs):
        spec.update({"proposal_id": f"{profile_id}_{index+1}", "subtitle": subtitle, "recommended": index == 0})
    explanation = (f"De {record['specified_count']:,} registros con participación especificada, {record['SV']:,} corresponden a SV: "
        f"{record['participation_observed']*100:.2f} %. La referencia de {record['matched_peer_reference']*100:.2f} % combina "
        "las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. "
        f"Su resta es {s['delta_pp']:+.2f} pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.")
    sex_note = (f"Las mujeres aportan {record['women_segment_fraction']*100:.2f} % de los segmentos V1 y "
        f"{record['women_nominal_fraction']*100:.2f} % del LN. El resto corresponde a hombres en estas fichas H/M. "
        "Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. "
        "La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.")
    composition = ("Composición nominal por tipo de sección electoral: " + "; ".join(
        f"{SECTION[t].lower()} {record[f'nominal_share_{t}']*100:.2f} %" for t in ["U", "R", "M"]) +
        ". Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. " + JOINT_NOTES[profile_id])
    top = states.sort_values(["LN", "EDOCVE"], ascending=[False, True]).head(3)
    territory = "Mayores aportaciones de LN a la ficha: " + "; ".join(
        f"{r.state_name_label} {r.share_of_profile_LN*100:.2f} %" for r in top.itertuples()) + ". "
    territory += (f"El denominador es el LN de esta ficha. En {top.iloc[0].state_name_label}, su LN representa "
        f"{top.iloc[0].share_of_state_core_LN*100:.2f} % del núcleo estatal H/M 18–100, un denominador distinto. "
        "Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.")
    rq = subset("reversal_quality").set_index("population")
    eligible = rq.loc["eligible_children"]
    reversal_note = (f"{s['eligible_flip_cells']:,}/{s['eligible_cells']:,} hijos con soporte ({s['eligible_flip_fraction']*100:.2f} %) "
        f"cambian de signo frente al padre V1, con LN={s['eligible_flip_LN']:,} "
        f"({s['eligible_flip_nominal_fraction']*100:.2f} % del LN de los hijos elegibles de la ficha). "
        f"De esos cambios, {int(eligible.flip_near_reference_cells):,} están a ≤2 pp de cero en el hijo y "
        f"{int(eligible.flip_parent_near_reference_cells):,} en el padre; las dos cuentas se superponen. "
        f"{int(eligible.flip_high_ns_cells):,} tienen NS alto y {int(eligible.flip_few_sections_cells):,} menos de cinco secciones, "
        "banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.")
    e = examples[examples.candidate_id.eq(profile_id)].iloc[0]
    example_note = (f"Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: "
        f"entidad {e.EDOCVE}, municipio {e.MPIOCVE}, {SEX[e.SEXO].lower()}, banda {e.age_band}, sección electoral {SECTION[e.TIPOSEC].lower()}. "
        f"LN={e.LN:,}, SV+NV={e.specified_count:,}; tasa={e.participation_observed*100:.2f} %, "
        f"referencia={e.reference_age_sex*100:.2f} %, Δ hijo={e.delta_age_sex*100:+.2f} pp; Δ padre={e.v1_parent_delta*100:+.2f} pp. "
        f"row_id={e.row_id}. No es un caso representativo de todos los cambios.")
    caution = (f"La mitad central de las diferencias V1 va de {record['delta_q1']*100:+.2f} a {record['delta_q3']*100:+.2f} pp; "
        f"mediana {record['delta_median']*100:+.2f} pp, DE {s['delta_sd_pp']:.2f} pp con igual peso por segmento. "
        f"{record['near_reference_fraction']*100:.2f} % de padres está a ≤2 pp de la referencia y "
        f"{record['high_ns_fraction']*100:.2f} % tiene NS/LN≥10 %. "
        f"Al separar U/R/M hay {s['undefined_cells']:,} hijos con tasa no definida (LN={s['undefined_LN']:,}); no se vuelven cero. "
        "Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre "
        "en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. "
        "U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.")
    findings = [
        {"text": specs[0]["statistical_justification"], "sources": specs[0]["sources"]},
        {"text": JOINT_NOTES[profile_id], "sources": ["joint_evidence", "section_evidence", "prior_interpretation"]},
        {"text": reversal_note, "sources": ["profile_evidence", "reversal_evidence", "reversal_quality"]},
    ]
    return {"profile_id": profile_id, "election_year": 2024, "status": "experimental_editorial_review_pending",
        "recommended_name": specs[0]["name"], "subtitle": subtitle, "description": DESCRIPTIONS[profile_id],
        "name_proposals": specs, "findings": findings, "turnout_explanation": explanation,
        "sex_analysis": sex_note, "section_analysis": composition, "territorial_observation": territory,
        "sign_reversal_analysis": reversal_note, "sign_reversal_example": example_note, "limitations": caution,
        "statistics": s, "joint_age_sex_section": joint.to_dict("records"),
        "section_statistics": sections.to_dict("records"), "sex_statistics": sex.to_dict("records"),
        "top_states": top.to_dict("records"), "sources": list(SOURCES)}


def render_deliverables(output: Path, tables, published, examples):
    reports = output / "reports"
    reports.mkdir()
    cards_dir = reports / "cards"
    cards_dir.mkdir()
    profiles = [build_card(profile_id, tables, published, examples) for profile_id in ORDER]
    rows = []
    proposals = ["# Propuestas de nombres descriptivos · 2024", "",
        "Dieciocho propuestas para las seis fichas V1 por reglas. Los nombres recomendados son provisionales; no renombran clusters V2 ni modifican fichas publicadas. "
        "Los superlativos se refieren exclusivamente a estas seis categorías. Nombre y subtítulo deben mostrarse juntos: el título por sí solo no expresa la regla completa.", ""]
    comparison = ["# Comparación editorial de las propuestas", "",
        "Cada rasgo se contrasta en la población V1 original. Se elige claridad y una diferencia comprobable, sin exigir una singularidad sociológica que los datos no contienen.", ""]
    for profile in profiles:
        proposals += [f"## {profile['profile_id']}", ""]
        for index, spec in enumerate(profile["name_proposals"]):
            proposals += [f"### {index+1}. {spec['name']}" + (" · recomendada provisionalmente" if index == 0 else ""), "",
                f"**Subtítulo:** {spec['subtitle']}", "", f"**Rasgo:** {spec['distinctive_feature']}", "",
                f"**Justificación:** {spec['statistical_justification']}", "", f"**Fuente exacta:** {source_links(spec['sources'])}; filtro de perfil `{profile['profile_id']}` y filtros sexo/tipo indicados en la justificación.", "",
                f"**Límite:** {spec['limitation']}", ""]
            rows.append({"profile_id": profile["profile_id"], "proposal": index+1, "name": spec["name"],
                "recommended": index == 0, "subtitle": spec["subtitle"], "distinctive_feature": spec["distinctive_feature"],
                "statistical_justification": spec["statistical_justification"], "sources": ", ".join(spec["sources"]), "limitation": spec["limitation"]})
        comparison += [f"## {profile['profile_id']}", "",
            f"**Recomendación:** {profile['recommended_name']}. {profile['name_proposals'][0]['distinctive_feature']} "
            "La primera propuesta comunica el rasgo más directo; las otras dos aportan lecturas de contexto o calidad que requieren más explicación.", ""]
        for n in [1, 2]:
            spec = profile["name_proposals"][n]
            comparison += [f"- **{spec['name']}:** {spec['limitation']}", ""]
        lines = [f"# {profile['recommended_name']}", "", f"`{profile['profile_id']}` · recomendación editorial provisional", "",
            profile["subtitle"], "", profile["description"], "", "## Tres hallazgos verificables", ""]
        for finding in profile["findings"]:
            # El catálogo está un nivel por encima de cada ficha.
            lines += ["- " + finding["text"] + " Fuentes: " + source_links(finding["sources"]).replace("(source_catalog", "(../source_catalog"), ""]
        lines += ["## Participación y referencia", "", profile["turnout_explanation"], "",
            "## Sexo y tipo de sección electoral: cruce conjunto", "", profile["sex_analysis"], "", profile["section_analysis"], ""]
        df = pd.DataFrame(profile["joint_age_sex_section"])
        for field in ["participation_observed", "matched_age_sex_reference", "share_of_profile_LN"]:
            df[field + "_pct"] = df[field] * 100
        lines += [table_markdown(df, ["SEXO", "TIPOSEC", "LN", "specified_count", "participation_observed_pct", "matched_age_sex_reference_pct", "delta_pp", "eligible_cells", "eligible_flip_cells"]), "",
            "SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. "
            "Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; "
            "las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.", "",
            "Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; "
            f"filtro `profile_id={profile['profile_id']}`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).", "",
            "## Territorio", "", profile["territorial_observation"], "",
            "Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.", "",
            "## Cambios de signo al desagregar", "", profile["sign_reversal_analysis"], "", profile["sign_reversal_example"], "",
            "Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, "
            "antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.", "",
            "Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).", "",
            "## Variación interna y límites", "", profile["limitations"], "",
            "No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.", ""]
        (cards_dir / f"{profile['profile_id']}.md").write_text("\n".join(lines), encoding="utf-8")
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "name_comparison.csv", index=False, encoding="utf-8")
    comparison[4:4] = [table_markdown(frame, ["profile_id", "proposal", "name", "recommended"]), ""]
    (reports / "name_proposals.md").write_text("\n".join(proposals), encoding="utf-8")
    (reports / "name_comparison.md").write_text("\n".join(comparison), encoding="utf-8")
    catalog = ["# Fuentes, campos y reglas de cálculo", "",
        "ID significa el profile_id técnico original. Las rutas de repositorio se resuelven desde su raíz; las rutas this_output desde esta entrega. "
        "Las huellas y la conciliación están en metadata/run_manifest.json y evidence/parent_reconciliation.csv.", ""]
    for key, source in SOURCES.items():
        target = "../" + source["path"] if source.get("base") == "this_output" else "../../../../../" + source["path"]
        catalog += [f"## {key.replace('_', '-')}", "", f"**Archivo:** [{source['path']}]({target}).", "",
            f"**Filtro:** {source['selector']}.", "", "**Campos:** " + ", ".join(f"`{k}`" for k in source.get("fields", [])) + ".", ""]
    catalog += ["## Fórmulas y denominadores", "",
        "D=SV+NV; tasa=SV/D si D>0, NULL en otro caso. Referencia nacional r=ΣSV/ΣD de todos los originales de banda/sexo de 2024, "
        "antes de seleccionar soporte. Referencia mezclada de ficha o cruce U/R/M=Σ(Dᵢrᵢ)/ΣDᵢ; Δ=100×(ΣSV/ΣD−referencia). "
        "En un cruce de sexo fijo r es constante. No se usa una media simple de tasas para la participación agregada.", "",
        "U/R/M es tipo de sección electoral, no residencia. Composición LN de un tipo=LN_tipo/LN_ficha. "
        "El soporte del hijo requiere LN≥100, D≥100, filas fuente≥5, banda 18–100 y H/M. "
        "No se exige cinco secciones: el número distinto de secciones se conserva como bandera separada. "
        "NS alto: NS/LN≥10 %. Filas fuente no equivalen a personas ni a secciones independientes.", "",
        "Cambios de signo: signo(SV_hijo×D_nacional−SV_nacional×D_hijo), comparado con direction del padre; "
        "los productos usan enteros Python sin desbordamiento int64. D=0 produce signo NULL; un empate exacto es cero, nunca inversión. "
        "Se conserva cada hijo presente; no se fabrican tipos ausentes ni se imputan tasas. "
        "Todos los hijos de los padres V1 concilian los siete conteos originales; los hijos elegibles se separan sólo para el diagnóstico de fiabilidad.", "",
        "No se suman section_count entre celdas para obtener secciones únicas de la ficha. No se suman municipios entre fichas. "
        "La zona ≤2 pp y las banderas no son pruebas de significación ni intervalos de confianza.", ""]
    (reports / "source_catalog.md").write_text("\n".join(catalog), encoding="utf-8")
    summary = tables["profile_summary"].copy()
    for c in ["participation_observed", "matched_age_sex_reference", "eligible_flip_fraction"]:
        summary[c + "_pct"] = summary[c] * 100
    recommendations = ["# Recomendación editorial provisional · seis fichas V1 de 2024", "",
        "Se recomienda conservar los identificadores y reglas originales y probar los siguientes títulos junto a su subtítulo. "
        "La revisión cambia la comunicación, no la pertenencia: son resúmenes por reglas de edad/signo, no seis clusters naturales, perfiles individuales o etiquetas morales.", ""]
    recommendations += ["| ID interno | Título propuesto | Rasgo comprobado | Ficha |", "| --- | --- | --- | --- |"]
    for p in profiles:
        recommendations += [f"| {p['profile_id']} | {p['recommended_name']} | {p['name_proposals'][0]['distinctive_feature']} | [Ver ficha](cards/{p['profile_id']}.md) |"]
    recommendations += ["", "## Qué diferencia y qué no diferencia", "",
        "Los títulos recomendados alternan diferencia relativa positiva, tasa absoluta mínima, presencia municipal, volumen nominal, tasa máxima y diferencia relativa negativa. "
        "Estos ejes son distintos: volumen no equivale a presencia, ni tasa absoluta a distancia respecto de referencia. "
        "Los superlativos requieren mostrar «entre las seis fichas de 2024» en ayuda o contexto. No implican que todas las edades o municipios del país tengan ese rasgo.", "",
        "La diferenciación adicional es limitada. Todos tienen mayoría nominal asociada a secciones urbanas (66.31–73.87 %), ambos sexos y variación interna. "
        "El 73.87 % urbano adulto negativo y el 73.84 % mayor positivo difieren apenas 0.03 pp: esa proximidad no justifica nombres de tipos urbanos distintos. "
        "La semejanza de composiciones de las dos fichas jóvenes tampoco permite atribuir sus tasas a ruralidad. "
        "En mayores negativos la diferencia relativa entre sexos es sólo 0.03 pp: no se propone una gran división por sexo. "
        "Las alternativas contextuales son válidas dentro de cada ficha, pero a menudo describen un subconjunto o un rasgo compartido; por eso no desplazan al título principal.", "",
        "## Evidencia conjunta y variación interna", "",
        table_markdown(summary, ["profile_id", "parent_segments", "joint_cells", "eligible_cells", "eligible_flip_cells", "eligible_flip_fraction_pct", "eligible_flip_LN"]), "",
        "Los seis padres V1 incluyen 14,190 segmentos, LN=98,203,780 y 2,402 municipios. "
        "Sus 33,709 hijos U/R/M presentes se mantienen completos, sin exigir soporte al hijo para reconstruir la ficha. "
        "El análisis de cambios con soporte usa 31,470 hijos, LN=97,999,677 y 2,392 municipios. "
        "Los 2,704 cambios de signo corresponden al 8.59 % de esos hijos y LN=5,688,327, el 5.80 % de su LN. "
        "No son municipios únicos, cambios temporales ni nuevos perfiles; pueden corresponder a diferencias próximas a cero. "
        "Cada ficha muestra cuántos cambios tienen esa cautela, NS alto o pocas secciones, con bases y advertencias separadas.", "",
        "El signo se comprueba frente a la referencia **banda/sexo**, igual en padre e hijo. "
        "La referencia nacional adicional banda/sexo/tipo de V2 se conserva en la traza, pero no sustituye la base V1 ni se usa para justificar estos nombres. "
        "Cambiar la referencia cambiaría la pregunta. Ninguna media por sexo/tipo de estas fichas invierte el signo agregado del padre; las inversiones son locales y no se deben ocultar detrás de esas medias.", "",
        "## Uso editorial propuesto", "",
        "Mostrar título, subtítulo con edad/tasa/referencia/Δ y condición experimental. Acompañar con tres hallazgos, el cruce real sexo×tipo de sección electoral y "
        "una advertencia de variación. Las descripciones principales contienen 40–70 palabras; los títulos tienen 4–9. "
        "Para tarjetas pequeñas, permitir salto de línea: los nombres no se validaron aún visualmente en React o PDF. "
        "El JSON es un contrato experimental independiente, no un reemplazo directo del JSON publicado ni una aprobación de integración.", "",
        "No se proponen estrategias, mensajes persuasivos ni campañas diferenciadas por conducta o demografía. "
        "Los cruces informan patrones agregados y no necesidades, preferencias partidistas, causas de abstención o eficacia institucional.", "",
        "## Fuentes y verificación", "",
        "[Catálogo exacto de fuentes y campos](source_catalog.md), [18 propuestas justificadas](name_proposals.md), "
        "[comparación editorial](name_comparison.md), [tabla CSV](../name_comparison.csv), [JSON experimental](../experimental_profile_names_2024.json). "
        "Se cotejan perfiles publicados, agregados originales y cruces V2; 42 conciliaciones perfil/campo dan diferencia cero. "
        "Los cálculos sólo leen agregados; no entrenan modelos ni cambian umbrales. La integridad de las fuentes y de los archivos previos protegidos "
        "se comprueba antes y después; los artefactos V2 se validan con su manifiesto original.", "",
        "Pendientes antes de adoptar: revisión del lenguaje por el equipo y personal electoral, prueba de comprensión con usuarios y de legibilidad en tarjetas/PDF, "
        "decisión explícita sobre cómo comunicar la zona cercana a la referencia y las inversiones locales, y revisión del futuro contrato de integración. "
        "Esta entrega no demuestra utilidad de intervención ni autoriza inferencias individuales; no modifica React, Atlas, estrategias o V1.", ""]
    (reports / "editorial_recommendation.md").write_text("\n".join(recommendations), encoding="utf-8")
    payload = {"schema_version": "experimental.editorial.1", "status": "editorial_review_pending", "election_year": 2024,
        "unit": "municipality_age_band_sex", "child_unit": "municipality_age_band_sex_section_type",
        "published": False, "replaces_published_V1": False, "sources": SOURCES,
        "rules": {"LN_min": 100, "specified_min": 100, "source_rows_min": 5, "age_bands": ["18-34", "35-59", "60-100"],
            "sex_codes": ["0", "1"], "high_ns_threshold": .1, "near_reference_delta_pp": 2,
            "reference": "all_original_2024_age_band_sex_before_support", "null_imputation": False,
            "aggregation": "sum_counts_then_divide; reference weighted by specified_count", "section_type_is_individual_residence": False},
        "profiles": profiles}
    return payload
