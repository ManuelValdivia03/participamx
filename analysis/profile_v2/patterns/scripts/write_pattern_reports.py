"""Informes y fichas de relaciones observadas, posteriores al cálculo de evidencia."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_patterns import BANDS, HOME, PRIOR, clean, write_json


def table(frame, columns=None, labels=None, digits=2):
    columns = columns or frame.columns.tolist()
    defaults = {"age_band":"Edad", "SEXO":"Sexo", "TIPOSEC":"Tipo de sección", "LN":"LN", "specified_count":"SV+NV",
        "participation_pct":"Participación (%)", "reference_pct":"Referencia nacional (%)", "delta_vs_age_sex_pp":"Diferencia nacional (pp)",
        "eligible_municipalities":"Municipios elegibles", "eligible_nominal_fraction":"Fracción LN elegible", "municipalities":"Municipios",
        "states":"Entidades", "equal_municipality_pp":"Media municipal (pp)", "nominal_pp":"Media con LN (pp)",
        "pooled_counts_pp":"Desde tasas agregadas (pp)", "municipality_same_sign_fraction":"Fracción municipal con mismo signo",
        "split":"Reparto", "scenario":"Escenario", "estimand":"Estimando", "estimate_pp":"Contraste (pp)",
        "simultaneous_low_pp":"Banda diagnóstica inferior (pp)", "simultaneous_high_pp":"Banda diagnóstica superior (pp)",
        "bootstrap_same_sign_fraction":"Fracción de réplicas con mismo signo", "eligible_segments":"Celdas elegibles", "reversal_segments":"Cambios de signo",
        "reversal_segment_fraction":"Fracción de celdas con cambio", "reversal_municipalities":"Municipios con cambios", "reversal_LN":"LN de cambios",
        "reversal_D":"SV+NV de cambios", "alternative":"Alternativa", "definition":"Definición", "differentiation":"Diferenciación",
        "coverage":"Cobertura", "stability":"Estabilidad", "transparency":"Transparencia", "four_dimensions":"Cuatro dimensiones", "limitation":"Limitación"}
    labels = {**defaults, **(labels or {})}
    def cell(x):
        if x is None or pd.isna(x):
            return "No disponible"
        if isinstance(x, (bool, np.bool_)):
            return "Sí" if x else "No"
        if isinstance(x, (float, np.floating)):
            return f"{x:.{digits}f}"
        return str(x).replace("|", "\\|")
    return "\n".join(["| " + " | ".join(labels.get(k, k) for k in columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"] +
        ["| " + " | ".join(cell(r[k]) for k in columns) + " |" for r in frame.to_dict("records")])


def name_proposals(row):
    band, typ = row.age_band, row.section_contrast[0]
    if band == "18-34" and typ == "R" and row.equal_municipality_pp > 0:
        names = ["Brecha joven ampliada en secciones rurales", "Contraste joven de sexo entre secciones", "Diferencias juveniles entre secciones rurales y urbanas"]
        reasons = ["Expresa el ensanchamiento de la brecha mujeres−hombres, no una categoría de jóvenes con participación alta o baja.",
                   "Hace visible la comparación conjunta, aunque no indica en qué tipo se amplía la brecha.",
                   "Explicita los dos contextos, pero necesita el subtítulo para identificar que se compara una brecha por sexo."]
    else:
        section = "rurales" if typ == "R" else "mixtas"
        movement = "ampliada" if row.equal_municipality_pp > 0 else "reducida"
        names = [f"Brecha por sexo {movement} en secciones {section}", "Contrastes de participación entre sexos y secciones", f"Participación comparada entre secciones {section} y urbanas"]
        reasons = ["Resume la dirección del contraste medido en la banda del subtítulo.", "Requiere el subtítulo para especificar banda y dirección.", "Describe contextos, pero es menos preciso respecto al contraste entre sexos."]
    return [{"name": name, "recommended": n == 0, "justification": reason,
        "evidence": {"contrast_id": row.contrast_id, "equal_municipality_pp": row.equal_municipality_pp,
                     "nominal_pp": row.nominal_pp, "municipalities": row.municipalities},
        "sources": ["interactions/contrast_summary.csv", "validation/split_results.csv", "validation/simultaneous_envelopes.csv"],
        "limitation": "Patrón de comparación entre cuatro celdas agregadas, no tipo de personas ni causa de participación."}
        for n, (name, reason) in enumerate(zip(names, reasons))]


def figures(output, national, screened, contrasts, reversals):
    chart = output / "charts"
    chart.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(HOME / ".cache/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"U": "#6d28d9", "R": "#08916c", "M": "#de8315"}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for ax, band in zip(axes, BANDS):
        for typ in ["U", "R", "M"]:
            g = national[national.age_band.eq(band) & national.TIPOSEC.eq(typ)].sort_values("SEXO")
            ax.plot([0, 1], g.participation_observed * 100, marker="o", color=colors[typ], label={"U":"Urbana","R":"Rural","M":"Mixta"}[typ])
        ax.set(title=band + " años", xticks=[0,1], xticklabels=["Hombres", "Mujeres"], ylim=(25,85))
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Participación observada (%)")
    axes[-1].legend(title="Tipo de sección electoral")
    fig.suptitle("Cruce nacional completo · tasas desde ΣSV / Σ(SV+NV), antes de soporte")
    fig.tight_layout(); fig.savefig(chart / "national_interactions.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10,5))
    positions = np.arange(len(screened))
    for n, (field, label) in enumerate([("equal_municipality_pp", "Municipios iguales"), ("nominal_pp", "Peso LN"), ("pooled_counts_pp", "Tasas agregadas")]):
        ax.scatter(screened[field], positions + (n-1)*.18, label=label, s=50)
    ax.axvline(0, color="gray", lw=1)
    ax.axvspan(-2,2,color="gray",alpha=.08,label="Zona práctica ±2 pp")
    readable = [r.age_band+" · "+("Rural−Urbana" if r.section_contrast=="R-U" else "Mixta−Urbana") for r in screened.itertuples()]
    ax.set(yticks=positions, yticklabels=readable,
           xlabel="Cambio de brecha mujeres−hombres entre T y U (pp)")
    ax.legend(loc="best"); ax.grid(axis="x",alpha=.2)
    fig.tight_layout();fig.savefig(chart / "matched_interactions.png",dpi=160);plt.close(fig)
    fig, axes = plt.subplots(2,3,figsize=(12,6),sharex=True)
    for ax, r in zip(axes.ravel(), screened.itertuples()):
        values=contrasts.loc[contrasts.contrast_id.eq(r.contrast_id),"interaction_pp"]
        ax.hist(values,bins=np.linspace(-30,30,61),color=colors[r.section_contrast[0]],alpha=.75)
        ax.axvline(0,color="black",lw=.7);ax.set_title(r.age_band+" · "+r.section_contrast)
        ax.set_xlabel("Contraste municipal (pp)");ax.set_ylabel("Municipios")
        outside=int((values.abs()>30).sum())
        ax.text(.98,.95,f"Fuera ±30 pp: {outside}",transform=ax.transAxes,ha="right",va="top",fontsize=8)
    fig.suptitle("Heterogeneidad dentro de municipios emparejados; los extremos se conservan en datos")
    fig.tight_layout();fig.savefig(chart/"municipal_heterogeneity.png",dpi=160);plt.close(fig)
    data=pd.read_csv(output/"sign_reversals/by_joint.csv",dtype={"SEXO":str})
    fig, ax=plt.subplots(figsize=(11,4))
    labels=data.age_band+" / "+data.SEXO.map({"0":"H", "1":"Mujeres"})+" / "+data.TIPOSEC
    ax.bar(labels,data.reversal_segment_fraction*100,color=[colors[t] for t in data.TIPOSEC])
    ax.set_ylabel("% de celdas elegibles que invierten signo");ax.tick_params(axis="x",rotation=75)
    fig.tight_layout();fig.savefig(chart/"sign_reversals_by_joint_cell.png",dpi=160);plt.close(fig)


def write_reports(output, tables, contrasts, summaries, screened, bands, reversals, union):
    reports=output/"reports";reports.mkdir(exist_ok=True)
    cards_dir=output/"candidates/cards";cards_dir.mkdir(parents=True,exist_ok=True)
    primary_components=pd.read_csv(output/"interactions/primary_components.csv",dtype={"SEXO":str})
    splits=pd.read_csv(output/"validation/split_results.csv")
    quality=pd.read_csv(output/"validation/quality_sensitivity.csv")
    age_changes=pd.read_csv(output/"interactions/age_changes_common_municipalities.csv")
    labels={"contrast_id":"Contraste", "municipalities":"Municipios", "states":"Entidades", "equal_municipality_pp":"Media municipal (pp)",
        "nominal_pp":"Media con LN (pp)", "pooled_counts_pp":"Desde tasas agregadas (pp)", "passes_screen":"Supera controles", "failed_criteria":"Controles no superados"}
    source_text=("Fuentes: `analysis/profile_v2/results/reference/all_observations.parquet`, `data/processed/participamx_multiyear/elections/2024/tables/segments.parquet` "
        "y `municipalities.parquet`; [protocolo fijado antes del cálculo](../../reports/protocol.md), [revisión crítica previa](../../reports/v2_critical_review.md). "
        "Se preservan 38,805 filas, los 7,335 pendientes y todas las categorías en [referencia](../reference/all_observations.parquet). "
        "Las claves se mantienen como texto y no forman distancias.")
    national=tables["age_sex_section"].copy()
    national["participation_pct"]=national.participation_observed*100
    standardized=tables["age_standardized_sex_section"]
    gap_rows=[]
    for typ in ["U", "R", "M"]:
        g=standardized[standardized.TIPOSEC.eq(typ)].set_index("SEXO")
        gap_rows.append({"TIPOSEC":typ,"crude_sex_gap_pp":100*(g.loc["1","crude_rate"]-g.loc["0","crude_rate"]),
                         "age_standardized_sex_gap_pp":100*(g.loc["1","age_standardized_rate"]-g.loc["0","age_standardized_rate"])})
    gap_frame=pd.DataFrame(gap_rows)
    threshold_rows=[]
    for threshold in [1.0,2.0,3.0]:
        for row in screened.itertuples():
            sign=np.sign(row.equal_municipality_pp)
            sp=splits[splits.contrast_id.eq(row.contrast_id)]
            fixed=all([row.pass_coverage,row.pass_not_one_territory,row.pass_territorial_consistency,
                       row.pass_simultaneous_envelope,row.pass_quality_sensitivity])
            practical=abs(row.equal_municipality_pp)>=threshold and row.nominal_pp*sign>=threshold and row.pooled_counts_pp*sign>0
            confirmation=(sp.equal_municipality_pp*sign>=threshold).all() and (sp.nominal_pp*sign>=threshold).all()
            threshold_rows.append({"threshold_pp":threshold,"contrast_id":row.contrast_id,"passes_at_threshold":bool(fixed and practical and confirmation)})
    threshold_frame=pd.DataFrame(threshold_rows)
    threshold_frame.to_csv(output/"candidates/practical_threshold_sensitivity.csv",index=False)
    threshold_counts=threshold_frame.groupby("threshold_pp").passes_at_threshold.sum().reset_index(name="patterns_passing")
    interaction_lines=["# Edad, sexo, tipo de sección electoral y participación · 2024", "",source_text,"",
        "## Conteos originales y referencias comparables", "",
        "Las tasas nacionales se forman desde todos los conteos antes de soporte; las siguientes 18 combinaciones no son perfiles aprendidos. "
        "La elegibilidad se aplica después y puede cambiar la mezcla territorial. NS se separa de NV, sin imputar; SEXO=2 y 101+ quedan complementarios.","",
        table(national,["age_band","SEXO","TIPOSEC","LN","specified_count","participation_pct","eligible_municipalities","eligible_nominal_fraction"]),"",
        "SEXO 0=Hombres, 1=Mujeres. U/R/M identifica tipo de sección electoral; no residencia individual. "
        "La cobertura nominal de la última columna es proporción, no porcentaje. [Conteos y cobertura completos](../interactions/age_sex_section.csv).", "",
        "![Interacciones nacionales](../charts/national_interactions.png)","",
        "## Comparaciones dentro del mismo municipio", "",
        "Se comparan municipios con las dos o cuatro celdas elegibles necesarias. No se rellenan ausencias con cero. "
        "Media municipal es el promedio justificado de contrastes, para dar igual influencia a cada territorio emparejado. "
        "Peso LN pondera ese mismo contraste por el nominal de sus componentes. Tasas agregadas primero suma conteos por componente y después contrasta. "
        "El último estimando conserva composición de volúmenes distinta entre componentes y puede alejarse del primero: no son tres estimaciones intercambiables de una tasa nacional.", "",
        table(summaries[summaries.family.eq("sex_gap")],["contrast_id","municipalities","equal_municipality_pp","nominal_pp","pooled_counts_pp"],labels),"",
        "Las filas `sex_` miden mujeres−hombres de la misma banda/tipo/municipio. "
        "Las diferencias por sexo cambian con edad; un agregado de todas las edades mezcla esas curvas. "
        "La [estandarización por edad](../interactions/age_standardized_sex_section.csv) usa los mismos pesos nacionales D por banda "
        "en todos los cruces sexo/tipo; es ajuste descriptivo, no causal.","",
        table(gap_frame,labels={"crude_sex_gap_pp":"Brecha mujeres−hombres agregada (pp)", "age_standardized_sex_gap_pp":"Brecha mujeres−hombres con edad estandarizada (pp)"}),"",
        "Al fijar la misma composición por edad, la brecha agregada por sexo sigue variando entre tipos de sección. "
        "Eso no iguala los municipios: por ese motivo se complementa con comparaciones emparejadas, no se interpreta como efecto contextual aislado.","",
        table(summaries[summaries.family.eq("section_gap")],["contrast_id","municipalities","equal_municipality_pp","nominal_pp","pooled_counts_pp"],labels),"",
        "Las filas `section_` miden R−U o M−U de la misma banda/sexo/municipio; no comparan municipios rurales contra municipios urbanos.","",
        "## Seis interacciones predefinidas", "",
        "I=(Mujeres_T−Hombres_T)−(Mujeres_U−Hombres_U), T=R/M. Cada municipio aporta sus cuatro componentes. "
        "I positivo significa una brecha por sexo más amplia en T; no significa que todos sus componentes tengan participación alta. "
        "No es un análisis causal de diferencias en diferencias.","",
        table(screened,["contrast_id","municipalities","equal_municipality_pp","nominal_pp","pooled_counts_pp","municipality_same_sign_fraction"],labels),"",
        "La última columna es la fracción municipal con el signo de la media, no un porcentaje de personas. "
        "El contraste joven R−U es apreciable dentro de municipios; otras interacciones nacionales se atenúan mucho al igualar territorios. "
        "No se da por demostrado un patrón de ≥2 pp sólo porque un gran agregado lo produzca.","",
        "![Contrastes y pesos](../charts/matched_interactions.png)","",
        "## Cambio de las brechas entre edades", "",
        "Se vuelve a emparejar por municipio entre dos edades, evitando restar medias de territorios diferentes. "
        "Estas comparaciones son secundarias descriptivas; no se usan para ampliar retrospectivamente el número de patrones aceptados.","",
        table(age_changes,["family","section_contrast","younger","older","municipalities","equal_municipality_difference_pp","nominal_difference_pp","same_sign_fraction"]),"",
        "[Valores municipales de todos los contrastes](../interactions/municipal_contrasts.parquet), "
        "[distribuciones y soporte](../interactions/contrast_summary.csv), [desglose por entidad](../validation/state_consistency.csv). "
        "Las medias pequeñas con estabilidad de signo siguen siendo pequeñas en utilidad práctica; no se publican p-valores de personas.","",
        "![Heterogeneidad municipal](../charts/municipal_heterogeneity.png)","",
        "## Remuestreo y multiplicidad", "",
        "Mil bootstrap sortean 2,477 municipios con reemplazo; cada clave comparte multiplicidad en todos los contrastes y conserva juntas sus celdas. "
        "La banda diagnóstica usa el percentil 95 del máximo absoluto de (estimando_remuestra−estimando_original)/DE_bootstrap, "
        "sobre seis interacciones × tres estimandos. Luego se construye estimando_original ± crítico×DE. "
        "Se conservan [multiplicidades y resultados](../resampling/municipal_bootstrap.npz), [cobertura](../resampling/bootstrap_coverage.csv) "
        "y [bandas simultáneas](../validation/simultaneous_envelopes.csv). "
        "No son intervalos de confianza de votantes ni una garantía formal de error familiar: la base reportada no es una muestra probabilística de personas. "
        "No se declara significación causal; se combina esta comprobación con magnitud práctica, reparto 60/40 de municipios y sensibilidades. "
        "Los municipios sin bloques completos se sortean y cuentan, aunque no aportan contraste.","",
        "Referencia técnica primaria: [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) "
        "describe remuestreo con reemplazo y uso de índices emparejados. La banda máxima conjunta aquí especificada es un diagnóstico propio explícito; "
        "no se atribuye a la API de SciPy ni se presenta como BCa. La prueba sintética contrasta el remuestreo emparejado con esa biblioteca.","",
        "La banda de NS por extremos utiliza SV/LN y (SV+NS)/LN por componente. "
        "Su combinación extrema se guarda en `contrast_summary.csv`: es sensibilidad algebraica, no imputación ni probabilidad. "
        "La confirmación dentro de los especificados no asegura que el contraste mantenga signo bajo todas las asignaciones posibles de NS."]
    (reports/"interaction_analysis.md").write_text("\n".join(interaction_lines)+"\n",encoding="utf-8")
    e,f=reversals["eligible"],reversals["reversals"]
    joint=pd.read_csv(output/"sign_reversals/by_joint.csv",dtype={"SEXO":str})
    sens=pd.read_csv(output/"sign_reversals/sensitivity.csv")
    state=pd.read_csv(output/"sign_reversals/by_state.csv").sort_values("reversal_LN",ascending=False)
    flip_lines=["# Investigación de los 2,704 cambios de signo · 2024","",source_text,"",
        "## Población y denominadores", "",
        f"Se verifican exactamente 2,704/31,470 celdas elegibles (8.59 %), LN={f['LN']:,}/{e['LN']:,} "
        f"({f['LN']/e['LN']*100:.2f} %) y D={f['specified_count']:,}/{e['specified_count']:,} "
        f"({f['specified_count']/e['specified_count']*100:.2f} % del especificado). "
        f"Hay {f['municipalities']:,} municipios con al menos un cambio: "
        f"{reversals['reversal_unique_municipalities_fraction_eligible']*100:.2f} % de los 2,392 elegibles y "
        f"{reversals['reversal_unique_municipalities_fraction_original']*100:.2f} % de los 2,477 originales. "
        "Ni filas ni municipios equivalen a personas; los conjuntos territoriales se superponen entre cruces.","",
        "Cada hijo y padre usa la misma referencia nacional banda/sexo de todos los conteos originales. "
        "El signo se calcula por productos cruzados enteros, no por porcentajes redondeados; un denominador nulo no recibe signo. "
        "No se llama cambio al efecto de sustituir esa referencia por otra U/R/M.","",
        "## Distribución conjunta", "",
        table(joint,["age_band","SEXO","TIPOSEC","eligible_segments","reversal_segments","reversal_segment_fraction","reversal_municipalities","reversal_LN","reversal_D"]),"",
        "Las fracciones se refieren a cada cruce elegible, no al total de 2,704. "
        "U/R/M por volumen y por número de filas puede dar órdenes distintos. "
        "También se guardan resúmenes [por edad](../sign_reversals/by_age.csv), [sexo](../sign_reversals/by_sex.csv), "
        "[tipo](../sign_reversals/by_section.csv), [V1](../sign_reversals/by_v1_profile.csv) y [municipio](../sign_reversals/by_municipality.csv).", "",
        "![Frecuencia por cruce](../charts/sign_reversals_by_joint_cell.png)","",
        "## Territorios y concentración", "",
        table(state.head(10),["EDOCVE","state_name_label","reversal_segments","reversal_segment_fraction","reversal_municipalities","reversal_LN"]),"",
        "Orden por LN de los cambios; no por su frecuencia estatal ni causalidad. "
        f"Los diez municipios con mayor LN de cambios concentran {reversals['top_ten_municipality_LN_fraction']*100:.2f} % de ese volumen. "
        "La tabla municipal conserva todas las claves elegibles, incluidas las que no presentan inversión.","",
        "## Intensidad y soporte", "",
        f"Mediana de |Δ hijo|={reversals['child_abs_delta_median_pp']:.2f} pp; |Δ padre|={reversals['parent_abs_delta_median_pp']:.2f} pp. "
        f"{reversals['child_near_2pp']:,} hijos y {reversals['parent_near_2pp']:,} padres están a ≤2 pp; esas cuentas se superponen. "
        f"Sólo {reversals['both_beyond_2pp']:,} cambios tienen ambos extremos a >2 pp y {reversals['both_beyond_5pp']:,} a >5 pp. "
        f"El D mediano del hijo que invierte es {reversals['median_D_reversals']:.0f}, frente a {reversals['median_D_other']:.0f} en los demás elegibles. "
        "Los denominadores importan, pero esa comparación no demuestra que los cambios sean exclusivamente ruido.","",
        table(sens,["scenario","eligible_segments","eligible_municipalities","eligible_LN","reversal_segments","reversal_segment_fraction","original_reversals_surviving","surviving_fraction_of_2704"]),"",
        "La supervivencia mantiene como base los 2,704 iniciales; la frecuencia de inversión usa la población de cada escenario. "
        "No confundir ambas. A soporte 50 se pueden incorporar nuevos hijos, pero sólo se consideran inversiones respecto de padres con ficha V1 original; "
        "no se reconstruye una V1 distinta para mejorar cobertura. NS<10 % y cinco secciones son sensibilidades, no cambios de las fuentes.","",
        f"{reversals['robust_fixed_reference']:,} cambios mantendrían el signo del hijo bajo los extremos de NS local frente a referencia observada fija; "
        f"{reversals['robust_both_ns_bounds']:,} bajo los extremos locales y nacionales. "
        "Esto no valida automáticamente su diferencia sustantiva: puede ser pequeña y tener NS=0. Son límites algebraicos, no probabilidades.","",
        "## Qué significa la inversión", "",
        "El delta del padre es ΣD_hijo×delta_hijo/ΣD_hijo. "
        f"Residuo máximo de esa identidad: {reversals['weighted_delta_identity_max_residual']:.3g}. "
        f"El hijo inversor tiene una mediana de {reversals['median_parent_D_share']*100:.2f} % del D del padre. "
        "En todos los cambios verificados, el resto de tipos del mismo padre sostiene el signo del agregado. "
        "Es heterogeneidad entre partes de una media ponderada, compatible con concentración y composición; "
        "no demuestra por sí sola una inversión de asociación entre dos variables al condicionar una tercera, por lo que no se etiqueta como paradoja de Simpson.","",
        "La señal es útil para revisar subsegmentos y evitar nombres homogéneos. Su frecuencia por cruce no basta para convertirla en cuatro a seis clases. "
        "[Traza completa](../sign_reversals/all_2704.parquet), [descomposición padre/resto](../sign_reversals/decomposition.parquet), "
        "[cruce de magnitudes](../sign_reversals/magnitude_cross.csv) y [resumen reproducible](../sign_reversals/summary.json)."]
    (reports/"sign_reversal_review.md").write_text("\n".join(flip_lines)+"\n",encoding="utf-8")
    profiles=[]; diagnostic=[]; naming=[]
    for row in screened.itertuples():
        component=primary_components[primary_components.contrast_id.eq(row.contrast_id)].copy()
        pair=contrasts[contrasts.contrast_id.eq(row.contrast_id)]
        sp=splits[splits.contrast_id.eq(row.contrast_id)]
        se=quality[quality.contrast_id.eq(row.contrast_id)]
        ba=bands[bands.contrast_id.eq(row.contrast_id)]
        valid=bool(row.passes_screen)
        options=name_proposals(row) if valid else []
        title=options[0]["name"] if valid else f"Contraste diagnóstico {row.age_band} · {row.section_contrast}"
        subtitle=(f"{row.age_band.replace('-', '–')} años · comparación mujeres−hombres en secciones "
                  f"{'rurales' if row.section_contrast[0]=='R' else 'mixtas'} y urbanas dentro del mismo municipio.")
        status="candidate_supported_within_protocol" if valid else "not_supported_as_candidate_under_protocol"
        reference_lookup=tables["age_sex"].set_index(["age_band","SEXO"]).participation_observed
        component["reference_age_sex"]= [reference_lookup.loc[(r.age_band,r.SEXO)] for r in component.itertuples()]
        component["delta_vs_age_sex_pp"]=(component.participation_observed-component.reference_age_sex)*100
        state_rows=pd.read_csv(output/"validation/state_consistency.csv",dtype={"EDOCVE":str})
        st=state_rows[state_rows.contrast_id.eq(row.contrast_id)]
        top=st.sort_values("LN",ascending=False).head(3)
        summary=(f"En {row.municipalities:,} municipios con cuatro celdas de soporte, el contraste es "
                 f"{row.equal_municipality_pp:+.2f} pp con igual peso municipal y {row.nominal_pp:+.2f} pp con peso LN. "
                 f"{row.municipality_same_sign_fraction*100:.2f} % de municipios mantiene el signo de la media. "
                 "La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.")
        findings=[f"Contraste municipal {row.equal_municipality_pp:+.2f} pp; con LN {row.nominal_pp:+.2f}; desde tasas agregadas {row.pooled_counts_pp:+.2f}.",
            f"La mitad central municipal va de {row.contrast_q1_pp:+.2f} a {row.contrast_q3_pp:+.2f} pp; {row.municipality_same_sign_fraction*100:.2f} % comparte signo.",
            f"Incluye {row.municipalities:,} municipios y {row.states} entidades, LN={row.LN:,} ({row.annual_LN_fraction*100:.2f} % anual), con D={row.specified_count:,}."]
        data={"pattern_id":row.contrast_id,"status":status,"unit":"matched_municipality_age_band_two_sexes_two_section_types",
            "definition":"overlapping_representative_comparison_pattern_not_partition","age_band":row.age_band,"sex_codes":["0","1"],
            "section_types":[row.section_contrast[0],"U"],"provisional_name":title,"subtitle":subtitle,"description":summary,
            "name_proposals":options,"findings":findings,"statistics":row._asdict(),"components":component.to_dict("records"),
            "confirmation":sp.to_dict("records"),"sensitivity":se.to_dict("records"),"simultaneous_envelopes":ba.to_dict("records"),
            "territory":top.to_dict("records"),"contribution_beyond_v1":"Compara directamente brechas entre sexos y tipos dentro del mismo municipio; no hereda edad/signo V1 ni etiqueta niveles alto/bajo.",
            "limitations":["Selección de municipios con cuatro celdas completas; no representa todos los municipios.",
                "Heterogeneidad local, NS, soporte y composición; no causalidad ni clases naturales.",
                "Bandas amplias y H/M; SEXO=2 y 101+ permanecen complementarios, sin imputación.",
                "Patrones superpuestos; la cobertura se calcula por unión única de row_id.",
                "Referencia de la interacción: brecha por sexo en U de los mismos municipios. La referencia nacional banda/sexo es contexto adicional, no el cero de esta interacción."],
            "sources":["interactions/municipal_contrasts.parquet","interactions/primary_components.csv","candidates/screening.csv",
                "validation/simultaneous_envelopes.csv","validation/state_consistency.csv"]}
        (profiles if valid else diagnostic).append(data)
        cp=component.copy()
        cp["participation_pct"]=cp.participation_observed*100;cp["reference_pct"]=cp.reference_age_sex*100
        text=[f"# {title}","",f"**Estado:** {status} · ID `{row.contrast_id}`", "",subtitle,"",summary,"",
            "## Tres hallazgos", ""]+["- "+x for x in findings]+["",
            "## Tasas y referencias de sus cuatro componentes","",
            table(cp,["SEXO","TIPOSEC","municipalities","LN","specified_count","participation_pct","reference_pct","delta_vs_age_sex_pp"]),"",
            "Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. "
            "El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. "
            "Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.", "",
            "## Confirmación municipal independiente del reparto inicial", "",
            table(sp,["split","municipalities","LN","equal_municipality_pp","nominal_pp","pooled_counts_pp"],labels),"",
            "El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. "
            "La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.","",
            "## Calidad y estabilidad", "",table(se,["scenario","municipalities","LN","equal_municipality_pp","nominal_pp"],labels),"",
            table(ba,["estimand","estimate_pp","simultaneous_low_pp","simultaneous_high_pp","bootstrap_same_sign_fraction"]),"",
            "Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. "
            f"Con NS extremo, la media municipal del contraste puede estar entre {row.ns_extreme_municipal_low_pp:+.2f} "
            f"y {row.ns_extreme_municipal_high_pp:+.2f} pp. Es sensibilidad algebraica, no una imputación.","",
            "## Evidencia territorial", "",table(top,["EDOCVE","municipalities","LN","equal_municipality_pp","municipality_same_sign_fraction"],labels),"",
            "Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. "
            f"La media coincide en signo en {row.state_same_sign_fraction*100:.2f} % de las entidades con cinco o más municipios comparables. "
            f"El mayor municipio aporta {row.top_municipality_LN_fraction*100:.2f} % del LN del bloque; los diez primeros {row.top_ten_municipality_LN_fraction*100:.2f} %.","",
            "## Qué aporta frente a V1", "",data["contribution_beyond_v1"],"",
            "## Decisión y límites", "", "Supera los controles del protocolo como patrón descriptivo candidato; no se convierte en perfil definitivo." if valid else
            f"No se promueve como perfil multivariable: no supera `{row.failed_criteria}`. Se conserva para revisión; no se le asigna un nombre atractivo para ocultar esos límites.","",
            *["- "+x for x in data["limitations"]],"",
            "Fuentes exactas: [contrastes municipales](../../interactions/municipal_contrasts.parquet), "
            "[componentes](../../interactions/primary_components.csv), [filtros de aceptación](../screening.csv), "
            "[sensibilidades](../../validation/quality_sensitivity.csv). Filtrar siempre el contrast_id de esta ficha."," "]
        (cards_dir/f"{row.contrast_id}.md").write_text("\n".join(text)+"\n",encoding="utf-8")
        if valid:
            naming += [f"## {row.contrast_id}","",subtitle,""]
            for opt in options:
                naming += [f"### {opt['name']}"+(" · recomendado" if opt["recommended"] else ""),"",opt["justification"],"",
                    f"Evidencia: {row.equal_municipality_pp:+.2f} pp municipal, {row.nominal_pp:+.2f} pp con LN, "
                    f"{row.municipalities:,} municipios; consultar tablas por `{row.contrast_id}`.","",opt["limitation"],""]
    n=len(profiles)
    payload={"schema_version":"experimental.patterns.2.1","status":"research_review_pending","election_year":2024,"published":False,
        "definition":"overlapping_representative_patterns_not_partition","profiles":profiles,"diagnostic_not_validated":diagnostic,
        "coverage":union,"sources":{"original_cells":"analysis/profile_v2/results/reference/all_observations.parquet",
            "parents":"data/processed/participamx_multiyear/elections/2024/tables/segments.parquet", "protocol":"analysis/profile_v2/patterns/reports/protocol.md"},
        "limitations":["No son tipos individuales ni grupos para personalizar campañas.","La cantidad resultante no se ajusta a cuatro o seis por narrativa.",
            "No asigna automáticamente estrategias institucionales.","No sustituye V1 ni modifica React o Atlas."]}
    write_json(output/"candidates/experimental_patterns.json",payload)
    pattern_lines=["# Evaluación de patrones candidatos", "",f"**{n} de seis interacciones supera los controles predefinidos.** "
        "No se modifica el protocolo para obtener cuatro a seis perfiles. La ausencia de un contraste de ≥2 pp no demuestra identidad electoral: "
        "limita la fuerza práctica de ese patrón en este diseño.","",table(screened,["contrast_id","municipalities","equal_municipality_pp","nominal_pp","passes_screen","failed_criteria"],labels),"",
        "Los detalles de todos los criterios están en [screening.csv](../candidates/screening.csv). "
        "Las seis fichas diagnósticas conservan las pruebas, incluidas las que no pueden promoverse. "
        "Los nombres sólo se proponen para las que pasan; las otras no se presentan como cinco perfiles descubiertos.","",
        "## Sensibilidad al umbral de magnitud", "",
        table(threshold_counts,labels={"threshold_pp":"Umbral práctico (pp)","patterns_passing":"Patrones que superarían controles"}),"",
        "Este diagnóstico secundario se añade después de la evaluación principal: varía únicamente la magnitud exigida en la población completa y los dos repartos municipales, "
        "manteniendo los demás controles. No sustituye el umbral principal de 2 pp ni convierte las variantes en nuevos perfiles. "
        "[Detalle de las 18 comprobaciones](../candidates/practical_threshold_sensitivity.csv). El resultado depende del protocolo; "
        "no es una demostración de que ninguna otra representación o familia de relaciones pueda contener cuatro a seis patrones.","",
        "## Población cubierta y superposición", "",
        f"La unión única de patrones aceptados contiene {union['union']['segments']:,} celdas, {union['union']['municipalities']:,} municipios "
        f"y LN={union['union']['LN']:,}: {union['nominal_union_fraction_annual']*100:.2f} % anual y "
        f"{union['nominal_union_fraction_eligible']*100:.2f} % del LN elegible. "
        f"Quedan fuera {union['eligible_outside_union']['segments']:,} celdas elegibles con LN={union['eligible_outside_union']['LN']:,}. "
        f"Hay {union['overlapping_segments']:,} celdas en más de un patrón aceptado. "
        "No se suman coberturas de fichas: se unen row_id. El marco admite superposiciones porque una celda urbana puede servir como comparación en R−U y M−U. "
        "Por ello C es un conjunto de patrones representativos, no una partición alternativa exhaustiva.","",
        "[Membresías de las seis pruebas](../candidates/all_six_memberships.parquet), [unión única](../candidates/union_coverage.json) y "
        "[referencia íntegra con número de membresías](../reference/all_observations.parquet). "
        "Cero membresías no significa tasa cero ni ausencia de personas.",""]
    for row in screened.itertuples():
        pattern_lines += [f"- [{row.contrast_id}](../candidates/cards/{row.contrast_id}.md): "+("candidato" if row.passes_screen else "diagnóstico no promovido")+".",""]
    (reports/"candidate_patterns.md").write_text("\n".join(pattern_lines),encoding="utf-8")
    (reports/"name_proposals.md").write_text("# Nombres posteriores a la evidencia\n\n"+
        f"Se proponen tres opciones para cada uno de los {n} patrones que supera el protocolo; no se bautizan los resultados rechazados. "
        "No son sustitutos de las seis fichas V1.\n\n"+"\n".join(naming),encoding="utf-8")
    comparisons=pd.DataFrame([
        {"alternative":"A · V1 enriquecida","definition":"Partición por reglas edad/signo sobre padres V1 con soporte","differentiation":"Edad y posición relativa explícitas; interacción sólo como contexto",
         "coverage":"14,190 padres; 2,402 municipios; 99.87 % LN anual","stability":"Regla reproducible; 13.20 % de padres a ≤2 pp; 2,704 hijos invierten signo",
         "transparency":"Alta: regla y referencia visibles","four_dimensions":"Sí como descripción; no en definición conjunta","limitation":"No seis clases naturales; variación oculta si se omiten cruces"},
        {"alternative":"B · Clusters V2 K4/5/6","definition":"Particiones de 31,470 hijos elegibles; geometrías distintas","differentiation":"Tasa relativa/sexo dominan; contribución U/R/M débil",
         "coverage":"2,392 municipios; 99.66 % LN anual","stability":"Buena en geometría fija; K5 sensible a ponderación municipal",
         "transparency":"Menor: bloques, escalas y K convencionales","four_dimensions":"Entradas conjuntas, sin garantizar interacciones propias","limitation":"Índices internos y estabilidad no validan tipos humanos"},
        {"alternative":"C · Patrones V2.1","definition":"Subconjuntos comparativos superpuestos, no partición","differentiation":f"{n}/6 interacciones cumple magnitud y controles",
         "coverage":f"Unión: {union['union']['municipalities']} municipios; {union['nominal_union_fraction_annual']*100:.2f} % LN anual",
         "stability":"Confirmación territorial, bootstrap conjunto y sensibilidades de calidad","transparency":"Alta: cuatro componentes y diferencia de brechas",
         "four_dimensions":"Sí, en la relación medida; no suma etiquetas a V1","limitation":"No cubre todo ni justifica cuatro a seis perfiles; selección de municipios completos"}])
    comparisons.to_csv(output/"comparisons/alternatives.csv",index=False)
    (reports/"alternative_comparison.md").write_text("# Comparación A, B y C\n\n"+table(comparisons)+
        "\n\nA es más defendible como catálogo transparente con cobertura amplia, si se presenta como reglas y se enriquece con heterogeneidad. "
        "C aporta relaciones conjuntas verificadas para un panel complementario de investigación, no un reemplazo exhaustivo. "
        "B no resuelve por sí solo el objetivo de cuatro a seis perfiles multivariables estables. No se elige C por ser más reciente.\n",encoding="utf-8")
    v2=pd.read_csv(output/"comparisons/v2_model_metrics.csv")
    representative=v2[v2.representative.eq(True)]
    v2lines=["# Contraste numérico de la revisión crítica V2","",
        "Se reutilizan modelos y fichas existentes; cero ajustes nuevos. Las fracciones siguientes son contribuciones a la separación entre centroides en la geometría elegida, no importancia causal.","",
        table(representative,["config","k","participation_separation_share","age_separation_share","sex_separation_share","section_separation_share","silhouette"],digits=4),"",
        "Comparar Silhouette entre geometrías no selecciona una representación universal. Las categorías fueron entradas al ajuste. "
        "Que sexo separe dos clases centrales no valida una interacción contextual. "
        "Fuentes copiadas sin modificar: model_metrics.csv, seed_stability.csv, municipal_stability.csv y sensitivity_metrics.csv, con sus huellas originales verificadas.","",
        "[Síntesis crítica previa](../../reports/v2_critical_review.md), [geometría V2](../../../reports/methodology.md) y "
        "[revisión editorial previa](../../../editorial/results/reports/editorial_recommendation.md)."]
    (reports/"v2_review_metrics.md").write_text("\n".join(v2lines),encoding="utf-8")
    final=["# Recomendación metodológica V2.1 · 2024","",
        f"**Esta investigación no respalda sustituir V1 por cuatro a seis perfiles conjuntos. {n} de seis interacciones predefinidas "
        "supera todos los controles; las otras se conservan como diagnósticos.** "
        "Es evidencia de relaciones multivariables, no de nuevas clases naturales ni de una partición exhaustiva de la ciudadanía.","",
        table(screened,["contrast_id","equal_municipality_pp","nominal_pp","municipalities","passes_screen","failed_criteria"],labels),"",
        "## Qué se aprendió", "",
        "El cruce real sí aporta relaciones que la regla edad/signo V1 no define y que K-Means no destacó: "
        "la brecha por sexo cambia entre tipos de sección y edades. En jóvenes, la comparación rural−urbana de esa brecha persiste dentro de municipios comparables. "
        "Sin embargo, muchas diferencias nacionales disminuyen o cambian de intensidad al igualar la influencia municipal: "
        "contexto, composición y ponderación deben permanecer visibles. Una diferencia pequeña no se vuelve un perfil propio por un gran denominador.","",
        f"Los cambios de signo no desaparecen por exigir soporte, pero una parte es cercana a cero: "
        f"{reversals['both_beyond_2pp']:,}/2,704 tienen hijo y padre a >2 pp; "
        f"{reversals['both_beyond_5pp']:,} a >5 pp. "
        "Revelan heterogeneidad local, sin validar por sí solos cuatro a seis tipos ni demostrar una paradoja específica.","",
        "## Decisión propuesta", "",
        "**Mantener A, V1 enriquecida, como catálogo de reglas; añadir C como evidencia contextual complementaria.** "
        "No adoptar los clusters B como sustitución: la investigación previa mostró dependencia de geometría y peso. "
        "C mejora la lectura conjunta mediante contrastes interpretables, pero su cobertura selectiva y el número de relaciones respaldadas no permiten venderlo como seis perfiles. "
        "No se inventan cortes o nombres adicionales para completar una cuota de tarjetas. "
        f"La unión C sólo cubre {union['nominal_union_fraction_annual']*100:.2f} % del LN anual en {union['union']['municipalities']:,} municipios; "
        "no ofrece la cobertura de A ni B. El diagnóstico de magnitud de 1/2/3 pp está separado en candidatos. "
        "Se rechaza la sustitución con la evidencia probada, no se demuestra la inexistencia de cualquier otra tipología posible.","",
        "## Entregables y límites", "",
        "[Síntesis crítica previa](../../reports/v2_critical_review.md), [protocolo previo](../../reports/protocol.md), "
        "[revisión numérica V2](v2_review_metrics.md), [análisis de interacciones](interaction_analysis.md), "
        "[2,704 inversiones](sign_reversal_review.md), [candidatos y cobertura](candidate_patterns.md), "
        "[alternativas A/B/C](alternative_comparison.md), [nombres](name_proposals.md) y "
        "[JSON experimental](../candidates/experimental_patterns.json). Las seis fichas diagnósticas enlazadas en candidatos distinguen aceptación y rechazo.","",
        "Se conservan todas las observaciones, conteos, NULL y pendientes. SEXO=2 mantiene 67 celdas y LN=105, "
        "con soporte insuficiente para comparaciones H/M; su ausencia histórica no equivale a cero personas. "
        "101+ queda complementario con LN=13,197. La investigación se limita a 2024; no transfiere etiquetas entre años. "
        "No hay residencia individual identificada por U/R/M, causalidad, predicción partidista, estrategia asignada o personalización de campañas.","",
        "Pendientes antes de cualquier adopción: revisión electoral externa, replicación en otra elección con categorías/cobertura comparables, "
        "revisión de sesgo de cuadernillos y NS, robustez a granularidad etaria y validación de utilidad pública. "
        "Una investigación adicional puede examinar representación territorial de curvas, pero requiere auditar cobertura de cada coordenada; "
        "no se propone entrenar directamente edades exactas escasas ni afinar pesos para fabricar cuatro a seis perfiles.","",
        "Se verifica integridad antes/después, fuentes V2/editorial y conciliación de conteos. "
        "Los resultados no modifican React, Atlas, V1, estrategias, datos ni resultados anteriores. No se crean commits, push, merges o PR."]
    (reports/"final_recommendation.md").write_text("\n".join(final)+"\n",encoding="utf-8")
    figures(output,tables["age_sex_section"],screened,contrasts,reversals)
