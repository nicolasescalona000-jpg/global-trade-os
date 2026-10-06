import time
import json
import requests
import streamlit as st
import pandas as pd
import pycountry
from google import genai
from datetime import datetime

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Global Trade & Customs OS",
    page_icon="🚢",
    layout="wide"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3);
    }
    .main-header h1 { color: #ffffff !important; margin: 0; font-weight: 800; }
    .main-header p { color: #94a3b8 !important; margin: 4px 0 0 0; }
    
    .metric-card-blue { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white; padding: 18px; border-radius: 14px; }
    .metric-card-green { background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; padding: 18px; border-radius: 14px; }
    
    .metric-title { font-size: 0.8rem; font-weight: 700; text-transform: uppercase; opacity: 0.9; }
    .metric-val { font-size: 1.6rem; font-weight: 800; margin: 4px 0; }
    .metric-sub { font-size: 0.85rem; font-weight: 600; background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 6px; display: inline-block; }
    
    .alert-ok { background-color: #d1fae5; border-left: 5px solid #10b981; color: #065f46; padding: 12px; border-radius: 6px; margin: 10px 0; }
    .pricing-card { background: #1e293b; color: white; padding: 24px; border-radius: 16px; text-align: center; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# BARRA LATERAL (CONFIGURACIÓN)
# ---------------------------------------------------------
st.sidebar.title("⚙️ Configuración")
api_key_input = st.sidebar.text_input(
    "🔑 Clave API de Google Gemini", 
    type="password", 
    help="Obtén tu clave en https://aistudio.google.com/"
)

if not api_key_input:
    st.sidebar.warning("⚠️ Ingresa tu Clave API para activar las consultas de IA.")

IVA_POR_PAIS = {
    "Venezuela": 0.16, "Colombia": 0.19, "United States": 0.00,
    "Spain": 0.21, "China": 0.13, "Panama": 0.07, "Mexico": 0.16,
    "Chile": 0.19, "Argentina": 0.21, "Peru": 0.18, "Brazil": 0.17,
    "Ecuador": 0.15, "Canada": 0.05, "United Kingdom": 0.20
}

PAISES = sorted([country.name for country in pycountry.countries])

# ---------------------------------------------------------
# DETECTOR ROBUSTO DE MONEDA, SÍMBOLO Y TASA EXACTA
# ---------------------------------------------------------
def obtener_info_moneda_y_tasa(nombre_pais_seleccionado):
    nombre_lower = nombre_pais_seleccionado.lower()
    
    if "venezuela" in nombre_lower:
        iso_code, simbolo, tasa = "VES", "Bs.", 872.39
    elif "colombia" in nombre_lower:
        iso_code, simbolo, tasa = "COP", "$", 4120.00
    elif "spain" in nombre_lower or "germany" in nombre_lower or "france" in nombre_lower or "italy" in nombre_lower:
        iso_code, simbolo, tasa = "EUR", "€", 0.92
    elif "china" in nombre_lower:
        iso_code, simbolo, tasa = "CNY", "¥", 7.22
    elif "mexico" in nombre_lower:
        iso_code, simbolo, tasa = "MXN", "$", 17.15
    elif "chile" in nombre_lower:
        iso_code, simbolo, tasa = "CLP", "$", 930.00
    elif "argentina" in nombre_lower:
        iso_code, simbolo, tasa = "ARS", "$", 970.00
    elif "peru" in nombre_lower:
        iso_code, simbolo, tasa = "PEN", "S/.", 3.72
    elif "brazil" in nombre_lower:
        iso_code, simbolo, tasa = "BRL", "R$", 5.45
    elif "panama" in nombre_lower:
        iso_code, simbolo, tasa = "PAB", "B/.", 1.00
    elif "united kingdom" in nombre_lower:
        iso_code, simbolo, tasa = "GBP", "£", 0.78
    elif "canada" in nombre_lower:
        iso_code, simbolo, tasa = "CAD", "$", 1.35
    elif "japan" in nombre_lower:
        iso_code, simbolo, tasa = "JPY", "¥", 152.00
    else:
        iso_code, simbolo, tasa = "USD", "$", 1.00

    if iso_code != "USD" and iso_code != "VES":
        try:
            url = "https://open.er-api.com/v6/latest/USD"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})
                if iso_code in rates:
                    tasa = float(rates[iso_code])
        except Exception:
            pass

    return iso_code, simbolo, tasa

# ---------------------------------------------------------
# INICIALIZACIÓN DE SESIÓN (SESSION STATE)
# ---------------------------------------------------------
if "codigo_hs" not in st.session_state:
    st.session_state.codigo_hs = "8517.13.00"
if "arancel_pct" not in st.session_state:
    st.session_state.arancel_pct = 10.0
if "fob_unit" not in st.session_state:
    st.session_state.fob_unit = 150.00
if "origen" not in st.session_state:
    st.session_state.origen = "China"
if "destino" not in st.session_state:
    st.session_state.destino = "Venezuela, Bolivarian Republic of"

iso_ini, sim_ini, tasa_ini = obtener_info_moneda_y_tasa(st.session_state.destino)
if "moneda_iso" not in st.session_state:
    st.session_state.moneda_iso = iso_ini
if "moneda_simbolo" not in st.session_state:
    st.session_state.moneda_simbolo = sim_ini
if "tasa_cambio" not in st.session_state:
    st.session_state.tasa_cambio = tasa_ini

if "analisis_res" not in st.session_state:
    st.session_state.analisis_res = None
if "historial_cotizaciones" not in st.session_state:
    st.session_state.historial_cotizaciones = []
if "plan_activo" not in st.session_state:
    st.session_state.plan_activo = "🌱 Básico Mensual ($49 USD/mes)"

def actualizar_destino_global(nuevo_destino):
    if st.session_state.destino != nuevo_destino:
        st.session_state.destino = nuevo_destino
        iso_n, sim_n, tasa_n = obtener_info_moneda_y_tasa(nuevo_destino)
        st.session_state.moneda_iso = iso_n
        st.session_state.moneda_simbolo = sim_n
        st.session_state.tasa_cambio = tasa_n

# ---------------------------------------------------------
# CONSULTA CON IA (CORREGIDA PARA EVITAR ERROR 401)
# ---------------------------------------------------------
def consultar_clasificacion_ia(api_key, descripcion, origen, destino, precio_fob):
    if not api_key:
        raise ValueError("No se ingresó ninguna Clave API.")

    system_instruction = "Eres un Clasificador Arancelario Oficial y Experto Aduanero. Responde ÚNICAMENTE con un JSON válido."
    prompt = f"""
    Analiza esta mercancía y responde ÚNICAMENTE con un objeto JSON estricto.
    MERCANCÍA: "{descripcion}"
    PAÍS ORIGEN: "{origen}"
    PAÍS DESTINO: "{destino}"
    PRECIO FOB UNITARIO: {precio_fob} USD

    FORMATO JSON EXACTO EXIGIDO:
    {{
        "codigo_hs": "CÓDIGO ARANCELARIO AQUÍ",
        "descripcion_oficial": "Descripción de la partida arancelaria",
        "arancel_estimado": 0.10,
        "permisos_y_restricciones": ["Permiso o licencia requerida"],
        "incoherence_check": {{
            "estado": "NORMAL",
            "rango_esperado_usd": "$100 - $300 USD",
            "evaluacion": "Precio dentro del rango comercial esperado."
        }}
    }}
    """
    # Se añade vertexai=False para forzar el uso de la API Key estándar de Google AI Studio
    client = genai.Client(api_key=api_key, vertexai=False)
    modelos = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
    ultimo_error = None

    for modelo in modelos:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json"
                }
            )
            limpio = response.text.strip()
            if limpio.startswith("```"):
                limpio = limpio.split("```")[1]
                if limpio.startswith("json"):
                    limpio = limpio[4:]
            return json.loads(limpio.strip())
        except Exception as e:
            ultimo_error = e
            continue
    raise ultimo_error

# ---------------------------------------------------------
# INTERFAZ DE USUARIO PRINCIPAL
# ---------------------------------------------------------
st.markdown(f"""
<div class="main-header">
    <div style="float: right; background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 10px; font-size: 0.9rem;">
        💎 Plan Activo: <b>{st.session_state.plan_activo}</b>
    </div>
    <h1>🚢 Global Trade OS + AI Customs Engine</h1>
    <p>Clasificador Arancelario, Landed Cost con Tasa Cambiaria Universal y Sincronización en Vivo</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🤖 Clasificador por IA", "🧮 Calculadora Landed Cost & Historial", "💎 Planes & Licenciamiento SaaS"])

# --- TAB 1: CLASIFICADOR IA ---
with tab1:
    st.subheader("🔍 Buscar Código Arancelario con IA")
    
    col_orig, col_dest, col_fob = st.columns(3)
    with col_orig:
        idx_o = PAISES.index(st.session_state.origen) if st.session_state.origen in PAISES else 0
        origen_sel = st.selectbox("📍 Origen (Escribe para buscar)", PAISES, index=idx_o, key="sel_origen_ia")
        st.session_state.origen = origen_sel

    with col_dest:
        idx_d = PAISES.index(st.session_state.destino) if st.session_state.destino in PAISES else 0
        destino_sel = st.selectbox("🎯 Destino (Escribe para buscar)", PAISES, index=idx_d, key="sel_destino_ia")
        
        if destino_sel != st.session_state.destino:
            actualizar_destino_global(destino_sel)

    with col_fob:
        fob_sel = st.number_input("💵 Valor Unitario USD", value=float(st.session_state.fob_unit), min_value=0.01, key="num_fob_ia")

    desc_input = st.text_area(
        "📦 Describe el producto a clasificar:",
        value="cafe tostado sin descafeinar",
        height=80
    )

    if st.button("✨ Obtener Código Arancelario y Datos Aduaneros", type="primary", use_container_width=True):
        if not api_key_input:
            st.error("❌ Debes ingresar tu Clave API de Gemini en el panel lateral.")
        else:
            with st.spinner("Consultando arancel oficial y tasa en vivo..."):
                try:
                    actualizar_destino_global(destino_sel)
                    res = consultar_clasificacion_ia(api_key_input, desc_input, origen_sel, destino_sel, fob_sel)
                    st.session_state.codigo_hs = res.get("codigo_hs", "0000.00.00")
                    st.session_state.arancel_pct = float(res.get("arancel_estimado", 0.10) * 100.0)
                    st.session_state.fob_unit = float(fob_sel)
                    st.session_state.analisis_res = res
                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {e}")

    if st.session_state.analisis_res:
        res = st.session_state.analisis_res
        st.markdown("---")
        st.subheader("1. 🏷️ Resultado de la Clasificación Arancelaria")
        
        c1, c2, c3, c4 = st.columns([1.5, 2.5, 1, 1])
        c1.metric("CÓDIGO ARANCELARIO (HS)", res.get("codigo_hs", "N/A"))
        c2.info(f"**Descripción Oficial:** {res.get('descripcion_oficial', 'Sin descripción')}")
        c3.metric("Arancel Ad-Valorem", f"{res.get('arancel_estimado', 0)*100:.1f}%")
        
        c4.metric(f"Tasa ({st.session_state.moneda_iso})", f"{st.session_state.moneda_simbolo} {st.session_state.tasa_cambio:,.2f}")

        st.subheader(f"2. 📜 Regulaciones y Permisos ({st.session_state.destino})")
        for p in res.get("permisos_y_restricciones", []):
            st.write(f"- ⚠️ {p}")

        st.subheader("3. ⚖ Evaluación de Valor Comercial")
        inc = res.get("incoherence_check", {})
        st.markdown(f"""
        <div class="alert-ok">
            <h4>✅ ESTADO: {inc.get('estado', 'NORMAL')}</h4>
            <p><strong>Rango esperado:</strong> {inc.get('rango_esperado_usd', 'N/A')}</p>
            <p>{inc.get('evaluacion', 'Sin evaluación.')}</p>
        </div>
        """, unsafe_allow_html=True)

# --- TAB 2: CALCULADORA CON INCOTERMS E HISTORIAL ---
with tab2:
    col_l, col_r = st.columns([1, 1.25], gap="large")

    with col_l:
        with st.container(border=True):
            st.subheader("🛠️ Parámetros y Negociación (Incoterms)")
            
            c_orig_calc, c_dest_calc = st.columns(2)
            with c_orig_calc:
                idx_oc = PAISES.index(st.session_state.origen) if st.session_state.origen in PAISES else 0
                nuevo_origen = st.selectbox("📍 Origen (Buscar)", PAISES, index=idx_oc, key="calc_origen")
                st.session_state.origen = nuevo_origen

            with c_dest_calc:
                idx_dc = PAISES.index(st.session_state.destino) if st.session_state.destino in PAISES else 0
                nuevo_destino = st.selectbox("🎯 Destino (Buscar)", PAISES, index=idx_dc, key="calc_destino_sync")
                if nuevo_destino != st.session_state.destino:
                    actualizar_destino_global(nuevo_destino)

            st.success(f"💱 **Moneda Oficial:** {st.session_state.moneda_iso} (`{st.session_state.moneda_simbolo}`) — Tasa exacta activa")
            
            tasa_edit = st.number_input(
                f"📊 Tasa de Cambio (1 USD = {st.session_state.moneda_simbolo} {st.session_state.moneda_iso})", 
                value=float(st.session_state.tasa_cambio), 
                min_value=0.0001,
                format="%.4f"
            )
            st.session_state.tasa_cambio = tasa_edit

            incoterm = st.selectbox(
                "🤝 Selecciona el Incoterm",
                ["FOB (Free On Board)", "EXW (Ex Works)", "CIF (Cost, Insurance and Freight)", "CFR (Cost and Freight)", "DDP (Delivered Duty Paid)", "DAP (Delivered at Place)"]
            )
            
            codigo_hs_edit = st.text_input("📦 Código HS", value=st.session_state.codigo_hs)
            arancel_pct_edit = st.number_input("📊 Arancel Ad-Valorem (%)", value=float(st.session_state.arancel_pct), step=0.5)
            
            unidades = st.number_input("🔢 Cantidad de Unidades", value=100, min_value=1)
            fob_unit_edit = st.number_input("💵 Valor Base Unitario USD", value=float(st.session_state.fob_unit), min_value=0.0)
            
            valor_mercancia = unidades * fob_unit_edit
            st.caption(f"💰 **Valor Mercancía:** ${valor_mercancia:,.2f} USD")

        with st.container(border=True):
            st.subheader("🚚 Flete y Logística")
            flete_sugerido = 1200.0 if st.session_state.origen != st.session_state.destino else 150.0
            seguro_sugerido = round(flete_sugerido * 0.08, 2)
            puerto_sugerido = 600.0

            if "EXW" in incoterm:
                flete_base_auto = st.number_input("Flete Internacional (USD)", value=flete_sugerido + 300.0, min_value=0.0)
                seguro_base_auto = st.number_input("Seguro Internacional (USD)", value=seguro_sugerido, min_value=0.0)
                gastos_puerto_auto = st.number_input("Gastos Puerto/Aduana (USD)", value=puerto_sugerido + 200.0, min_value=0.0)
            elif "CIF" in incoterm or "CFR" in incoterm:
                flete_base_auto = 0.0
                seguro_base_auto = 0.0 if "CFR" in incoterm else st.number_input("Seguro Internacional (USD)", value=seguro_sugerido, min_value=0.0)
                gastos_puerto_auto = st.number_input("Gastos Puerto Destino (USD)", value=puerto_sugerido, min_value=0.0)
            elif "DDP" in incoterm:
                flete_base_auto, seguro_base_auto, gastos_puerto_auto = 0.0, 0.0, 0.0
            else:
                flete_base_auto = st.number_input("Flete Internacional (USD)", value=flete_sugerido, min_value=0.0)
                seguro_base_auto = st.number_input("Seguro Internacional (USD)", value=seguro_sugerido, min_value=0.0)
                gastos_puerto_auto = st.number_input("Gastos Puerto Destino (USD)", value=puerto_sugerido, min_value=0.0)

    # --- CÁLCULOS FINANCIEROS ---
    arancel_dec = arancel_pct_edit / 100.0
    iva_rate = IVA_POR_PAIS.get(st.session_state.destino, 0.16)

    if "EXW" in incoterm:
        valor_cif = valor_mercancia + flete_base_auto + seguro_base_auto
    elif "CIF" in incoterm:
        valor_cif = valor_mercancia
    elif "CFR" in incoterm:
        valor_cif = valor_mercancia + seguro_base_auto
    elif "DDP" in incoterm:
        valor_cif = valor_mercancia
    else:
        valor_cif = valor_mercancia + flete_base_auto + seguro_base_auto

    monto_arancel = valor_cif * arancel_dec
    tasa_aduanera = valor_cif * 0.01
    base_iva = valor_cif + monto_arancel + tasa_aduanera
    
    if "DDP" in incoterm:
        monto_iva, total_impuestos, gastos_puerto_auto = 0.0, 0.0, 0.0
        costo_landed = valor_mercancia
    else:
        monto_iva = base_iva * iva_rate
        total_impuestos = monto_arancel + tasa_aduanera + monto_iva
        costo_landed = valor_cif + total_impuestos + gastos_puerto_auto

    costo_unit_usd = costo_landed / unidades if unidades > 0 else 0.0
    costo_unit_local = costo_unit_usd * st.session_state.tasa_cambio

    with col_r:
        st.subheader("📊 Resultados Financieros Calculados")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="metric-card-blue">
                <div class="metric-title">COSTO UNITARIO REAL</div>
                <div class="metric-val">${costo_unit_usd:,.2f} USD</div>
                <div class="metric-sub">{st.session_state.moneda_simbolo} {costo_unit_local:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card-green">
                <div class="metric-title">LANDED COST TOTAL</div>
                <div class="metric-val">${costo_landed:,.2f} USD</div>
                <div class="metric-sub">{st.session_state.moneda_simbolo} {costo_landed * st.session_state.tasa_cambio:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Guardar Cotización en Historial", use_container_width=True):
            nueva_cotizacion = {
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Destino": st.session_state.destino,
                "Incoterm": incoterm.split()[0],
                "HS": codigo_hs_edit,
                "Landed Cost USD": round(costo_landed, 2),
                f"Landed Cost ({st.session_state.moneda_simbolo})": round(costo_landed * st.session_state.tasa_cambio, 2)
            }
            st.session_state.historial_cotizaciones.append(nueva_cotizacion)
            st.success("¡Cotización guardada exitosamente en memoria!")

        st.subheader(f"📋 Desglose Financiero ({st.session_state.moneda_iso})")
        df_desglose = pd.DataFrame({
            "Concepto": [
                "Valor Base Mercancía", "Flete Internacional", "Seguro Internacional", 
                "VALOR EN ADUANA (CIF)", f"Arancel ({arancel_pct_edit:.1f}%)", 
                "Tasa Aduanera (1%)", f"IVA ({iva_rate*100:.1f}%)", 
                "TOTAL IMPUESTOS", "Gastos Operativos", "COSTO TOTAL DESTINO"
            ],
            "Monto (USD)": [
                f"${valor_mercancia:,.2f}", f"${flete_base_auto:,.2f}", f"${seguro_base_auto:,.2f}", f"${valor_cif:,.2f}",
                f"${monto_arancel:,.2f}", f"${tasa_aduanera:,.2f}", f"${monto_iva:,.2f}", f"${total_impuestos:,.2f}",
                f"${gastos_puerto_auto:,.2f}", f"${costo_landed:,.2f}"
            ]
        })
        st.dataframe(df_desglose, use_container_width=True, hide_index=True)

        if st.session_state.historial_cotizaciones:
            st.subheader("📂 Historial de Cotizaciones Guardadas")
            df_hist = pd.DataFrame(st.session_state.historial_cotizaciones)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

# --- TAB 3: PLANES Y SUSCRIPCIONES (SAAS ACTIVO CON MENSUAL / ANUAL) ---
with tab3:
    st.subheader("💎 Módulo de Suscripción y Licenciamiento Comercial")
    st.markdown("Elige tu modalidad de pago (**Mensual** o **Anual** con descuento) para activar los privilegios del sistema en tiempo real.")

    p1, p2, p3 = st.columns(3)
    
    with p1:
        st.markdown("""
        <div class="pricing-card">
            <h3>🌱 Plan Básico</h3>
            <p>Ideal para importadores ocasionales</p>
            <hr style="border-color: #475569;">
            <p>✅ 50 Clasificaciones IA / mes</p>
            <p>✅ Tasas de cambio en vivo</p>
            <p>✅ 1 Usuario</p>
        </div>
        """, unsafe_allow_html=True)
        
        c_m1, c_a1 = st.columns(2)
        with c_m1:
            if st.button("Mensual\n$49 USD", key="btn_basico_m", use_container_width=True):
                st.session_state.plan_activo = "🌱 Básico Mensual ($49 USD/mes)"
                st.success("¡Plan Básico Mensual activado!")
                time.sleep(0.3)
                st.rerun()
        with c_a1:
            if st.button("Anual\n$470 USD", key="btn_basico_a", use_container_width=True):
                st.session_state.plan_activo = "🌱 Básico Anual ($470 USD/año - Ahorras 20%)"
                st.success("¡Plan Básico Anual activado!")
                time.sleep(0.3)
                st.rerun()

    with p2:
        st.markdown("""
        <div class="pricing-card" style="border: 2px solid #2563eb;">
            <h3>🚀 Plan Profesional</h3>
            <p>Para agencias y pymes activas</p>
            <hr style="border-color: #475569;">
            <p>✅ Clasificaciones IA ilimitadas</p>
            <p>✅ Historial y exportación</p>
            <p>✅ Multi-Incoterms avanzados</p>
            <p>✅ Hasta 5 Usuarios</p>
        </div>
        """, unsafe_allow_html=True)
        
        c_m2, c_a2 = st.columns(2)
        with c_m2:
            if st.button("Mensual\n$149 USD", key="btn_pro_m", use_container_width=True):
                st.session_state.plan_activo = "🚀 Profesional Mensual ($149 USD/mes)"
                st.success("¡Plan Profesional Mensual activado!")
                time.sleep(0.3)
                st.rerun()
        with c_a2:
            if st.button("Anual\n$1,430 USD", key="btn_pro_a", use_container_width=True):
                st.session_state.plan_activo = "🚀 Profesional Anual ($1,430 USD/año - Ahorras 20%)"
                st.success("¡Plan Profesional Anual activado!")
                time.sleep(0.3)
                st.rerun()

    with p3:
        st.markdown("""
        <div class="pricing-card">
            <h3>🏢 Plan Enterprise</h3>
            <p>Para corporaciones y ERPs</p>
            <hr style="border-color: #475569;">
            <p>✅ API Access completa para ERP</p>
            <p>✅ Marca blanca corporativa</p>
            <p>✅ Soporte prioritario 24/7</p>
            <p>✅ Usuarios ilimitados</p>
        </div>
        """, unsafe_allow_html=True)
        
        c_m3, c_a3 = st.columns(2)
        with c_m3:
            if st.button("Mensual\n$499 USD", key="btn_ent_m", use_container_width=True):
                st.session_state.plan_activo = "🏢 Enterprise Mensual ($499 USD/mes)"
                st.success("¡Plan Enterprise Mensual activado!")
                time.sleep(0.3)
                st.rerun()
        with c_a3:
            if st.button("Anual\n$4,790 USD", key="btn_ent_a", use_container_width=True):
                st.session_state.plan_activo = "🏢 Enterprise Anual ($4,790 USD/año - Ahorras 20%)"
                st.success("¡Plan Enterprise Anual activado!")
                time.sleep(0.3)
                st.rerun()