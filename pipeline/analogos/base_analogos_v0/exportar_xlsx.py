"""Une las salidas de construir_base_analogos.py en un .xlsx con una hoja por tabla."""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

S = "salida/"
t = pd.read_csv(S + "analogos_tierra.csv")
pj = pd.read_csv(S + "parejas_luna_marte.csv")
pc = pd.read_csv(S + "parejas_comprobadas.csv")
s = pd.read_csv(S + "sitios_luna_marte.csv")
h = pd.read_csv(S + "huecos.csv")

COLOR = {"Alta": "C6EFCE", "Media": "FFEB9C", "Baja": "FCE4D6", "Muy baja (hipótesis)": "EDEDED",
         "Sin respaldo": "EDEDED", "Sin datos": "EDEDED", "sin parejas": "EDEDED", "sin medir": "EDEDED"}

leyenda = [
    ["Base de análogos v0 (14 nov 2026)", ""],
    ["Qué es", "Todos los sitios análogos de la Tierra que tiene el proyecto, con su nivel de confianza, y las parejas Tierra ↔ Luna/Marte comprobadas con las capas de datos."],
    ["Hojas", "Análogos Tierra (base 1) · Parejas comprobadas (base 2: nivel Alta o Media) · Todas las parejas (incluye Baja y Sin respaldo) · Sitios Luna-Marte (mejor pareja de cada uno) · Huecos (qué falta)"],
    ["", ""],
    ["CONFIANZA DE UN SITIO DE LA TIERRA", ""],
    ["puntos_evidencia (0–3)", "Bibliografía: verificada 3 (una fuente lo presenta como análogo) · pendiente 2 · candidato 1 · hipótesis 0 (lo proponen nuestros índices o M1, sin fuente)."],
    ["puntos_datos (0–4)", "Mejor pareja del sitio: Alta 3 · Media 2 · Baja 1 · ninguna 0; +1 si el índice de satélite o M1 lo sitúa en el percentil ≥ 95."],
    ["puntuacion_confianza (0–100)", "50 × evidencia/3 + 50 × datos/4. La mitad pesa la literatura y la otra mitad nuestros datos."],
    ["nivel_confianza", "Alta ≥ 75 y además una pareja Alta o Media · Media ≥ 50 · Baja ≥ 25 · Muy baja (hipótesis) < 25 · Sin datos: sin coordenadas."],
    ["", ""],
    ["CONFIANZA DE UNA PAREJA TIERRA ↔ LUNA/MARTE", ""],
    ["Capas y umbral (pasa si ≤)", "topografía 0,2 (KS de pendiente y relieve) · geología 0,4 (1 − roca compartida) · hielo 0,25 (|hielo del sitio − permafrost|; solo si el sitio tiene ≥ 20 % de hielo) · clima 0,2 · forma de cueva (profundidad/diámetro parecida)."],
    ["nivel_pareja", "Alta: pasan 3 o más capas · Media: 2 (p. ej., topografía + geología = «análogo completo») · Baja: 1 · Sin respaldo: ninguna."],
    ["similitud (0–1)", "Media de las capas evaluadas de max(0, 1 − d / (2 × umbral)): 0,5 = justo en el umbral. Sirve para ordenar."],
    ["Símbolos", "✓ pasa · ✗ no pasa · — no evaluada (sin dato o no aplica)."],
    ["Qué parejas hay", "La unión de los mejores de cada capa (top 5 de topografía, geología, hielo y clima; top 3 de cuevas y anortosita). Geología e hielo se calculan para todas las parejas; clima solo existe para su top 5."],
    ["", ""],
    ["LÍMITES", ""],
    ["Escala", "Regiones del índice y M1 son de ~50 km; los sitios de la ficha son puntos con coordenadas a veces aproximadas (ver coord_nota)."],
    ["M1 y campos de prueba", "No tienen parejas propias: no se han medido por capas. region_medida_cercana dice qué región medida tienen al lado."],
    ["Coordenadas", "sitio_lat/sitio_lon están en la Luna o en Marte (planetocéntricas, longitud este −180…180); tierra_lat/tierra_lon, en la Tierra."],
    ["Fuentes", "Ficha «ficha_analogos» (14 nov) y capas de data/06_web del backend: v1.3, luna_v0.3, m1_v0, topografia_sitios_v2, geologia_v0, hielo_v0, clima_v1, cuevas_v2, anortosita_v0. Script: construir_base_analogos.py."],
]

hojas = [
    ("Análogos Tierra", t, ["nivel_confianza", "mejor_nivel_pareja", "nivel_region_medida"]),
    ("Parejas comprobadas", pc, ["nivel_pareja"]),
    ("Sitios Luna-Marte", s, ["mejor_nivel"]),
    ("Huecos", h, []),
    ("Todas las parejas", pj, ["nivel_pareja"]),
]

wb = Workbook()
wb.remove(wb.active)
bold = Font(bold=True)
for nombre, df, cols_color in hojas:
    ws = wb.create_sheet(nombre)
    df = df.copy()
    for c in df.select_dtypes("float").columns:
        df[c] = df[c].round(4)
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
    for c in ws[1]:
        c.font = bold
    ws.freeze_panes = "C2"
    for i, col in enumerate(df.columns, start=1):
        largo = max([len(str(col))] + [len(str(x)) for x in df[col].head(200).fillna("")])
        ws.column_dimensions[get_column_letter(i)].width = min(max(8, largo + 2), 45)
        if col in cols_color:
            for r in range(2, len(df) + 2):
                v = ws.cell(r, i).value
                if v in COLOR:
                    ws.cell(r, i).fill = PatternFill("solid", fgColor=COLOR[v])

ws = wb.create_sheet("Leyenda")
for r in leyenda:
    ws.append(r)
ws.column_dimensions["A"].width = 34
ws.column_dimensions["B"].width = 120
for row in ws.iter_rows():
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    if row[0].value and (row[1].value in ("", None)):
        row[0].font = bold
ws["A1"].font = Font(bold=True, size=13)

wb.save(S + "base_analogos_v0.xlsx")
print("ok", [ (n, len(d)) for n, d, _ in hojas])
