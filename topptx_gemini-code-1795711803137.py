"""
Convierte el Beamer 4:3 de corriente de desplazamiento a PowerPoint (.pptx)
con las ecuaciones en LaTeX listas para convertir a MathType (Toggle TeX).

Requisitos:
    pip install python-pptx
Opcional (para extraer automaticamente el diagrama TikZ de la pag. 1 del PDF):
    pip install pymupdf
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


# --- CONFIGURACION DE ARCHIVOS ---
PDF_COMPILADO = Path("transparencias_corriente_de_desplazamiento_y_teor_a_de_circuitos.pdf")
PNG_GRAFICA = Path("perfil_radial_baja_frecuencia_v2.png")
PNG_DIAGRAMA_TIKZ = Path("diagrama_feynman_tikz.png")
OUT_PPTX = Path("corriente_desplazamiento_43.pptx")

# --- PALETA EXACTA DE TU BEAMER ---
ACCENT_BLUE = RGBColor(24, 78, 119)
SOFT_BLUE = RGBColor(234, 242, 250)
ACCENT_RED = RGBColor(192, 57, 43)
MUTED_GRAY = RGBColor(90, 100, 110)
WHITE = RGBColor(255, 255, 255)
BLACK = RGBColor(20, 20, 20)

FONT_NAME = "Noto Sans"
TOTAL_SLIDES = 9


def extraer_diagrama_tikz_desde_pdf():
    """Recorta el diagrama TikZ de la pagina 1 del PDF compilado a 300 dpi."""
    if PNG_DIAGRAMA_TIKZ.exists():
        return PNG_DIAGRAMA_TIKZ
    if not PDF_COMPILADO.exists():
        return None
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = fitz.open(PDF_COMPILADO)
    page = doc[0]
    rect = page.rect
    # Recorta la zona del diagrama (debajo del titulo y la ecuacion, encima del pie)
    clip = fitz.Rect(
        rect.width * 0.14,
        rect.height * 0.34,
        rect.width * 0.86,
        rect.height * 0.91,
    )
    pix = page.get_pixmap(clip=clip, dpi=300)
    pix.save(str(PNG_DIAGRAMA_TIKZ))
    doc.close()
    return PNG_DIAGRAMA_TIKZ


def crear_diapositiva_base(prs, titulo, numero):
    """Crea una diapositiva 4:3 con barra superior azul y pie de pagina Beamer."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # En blanco

    # Barra de titulo
    header = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(10), Inches(0.88)
    )
    header.fill.solid()
    header.fill.fore_color.rgb = ACCENT_BLUE
    header.line.fill.background()

    tf = header.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.4)
    tf.margin_right = Inches(0.4)
    p = tf.paragraphs[0]
    p.text = titulo
    p.font.name = FONT_NAME
    p.font.size = Pt(21)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Pie de pagina izquierdo
    foot_l = slide.shapes.add_textbox(Inches(0.35), Inches(7.08), Inches(7.8), Inches(0.32))
    p_l = foot_l.text_frame.paragraphs[0]
    p_l.text = "Electromagnetismo — Corriente de desplazamiento"
    p_l.font.name = FONT_NAME
    p_l.font.size = Pt(10)
    p_l.font.color.rgb = MUTED_GRAY

    # Numeracion derecha
    foot_r = slide.shapes.add_textbox(Inches(8.2), Inches(7.08), Inches(1.45), Inches(0.32))
    p_r = foot_r.text_frame.paragraphs[0]
    p_r.alignment = PP_ALIGN.RIGHT
    p_r.text = f"{numero} / {TOTAL_SLIDES}"
    p_r.font.name = FONT_NAME
    p_r.font.size = Pt(10)
    p_r.font.bold = True
    p_r.font.color.rgb = ACCENT_BLUE

    return slide


def anadir_ecuacion(slide, left, top, width, height, latex_str, size=18):
    """Inserta una caja centrada con LaTeX para convertir con MathType (Toggle TeX)."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.text = latex_str
    p.font.name = "Cambria Math"
    p.font.size = Pt(size)
    p.font.color.rgb = BLACK
    return box


def anadir_bloque_beamer(slide, left, top, width, height, titulo_bloque, cuerpo):
    """Reproduce un entorno \\begin{block}{...} de Beamer."""
    hdr_h = Inches(0.48)
    hdr = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, hdr_h)
    hdr.fill.solid()
    hdr.fill.fore_color.rgb = ACCENT_BLUE
    hdr.line.fill.background()
    tf_h = hdr.text_frame
    tf_h.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf_h.margin_left = Inches(0.18)
    p_h = tf_h.paragraphs[0]
    p_h.text = titulo_bloque
    p_h.font.name = FONT_NAME
    p_h.font.size = Pt(15)
    p_h.font.bold = True
    p_h.font.color.rgb = WHITE

    body = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top + hdr_h, width, height - hdr_h
    )
    body.fill.solid()
    body.fill.fore_color.rgb = SOFT_BLUE
    body.line.fill.background()
    tf_b = body.text_frame
    tf_b.word_wrap = True
    tf_b.margin_left = Inches(0.22)
    tf_b.margin_right = Inches(0.22)
    tf_b.margin_top = Inches(0.15)
    p_b = tf_b.paragraphs[0]
    p_b.text = cuerpo
    p_b.font.name = FONT_NAME
    p_b.font.size = Pt(15)
    p_b.font.color.rgb = BLACK
    p_b.line_spacing = 1.25


def anadir_vinetas(slide, left, top, width, height, items, encabezado=None, font_size=16):
    """
    items: lista de tuplas (negrita_opcional, texto_normal, texto_alerta_opcional, texto_final_opcional)
    """
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    first = True

    if encabezado:
        p = tf.paragraphs[0]
        p.text = encabezado
        p.font.name = FONT_NAME
        p.font.size = Pt(font_size + 1)
        p.font.bold = True
        p.font.color.rgb = ACCENT_BLUE
        p.space_after = Pt(10)
        first = False

    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(10)
        p.line_spacing = 1.2

        # Vineta azul
        r_b = p.add_run()
        r_b.text = "•  "
        r_b.font.name = FONT_NAME
        r_b.font.size = Pt(font_size)
        r_b.font.bold = True
        r_b.font.color.rgb = ACCENT_BLUE

        for segmento, estilo in item:
            r = p.add_run()
            r.text = segmento
            r.font.name = FONT_NAME
            r.font.size = Pt(font_size)
            if estilo == "bold":
                r.font.bold = True
                r.font.color.rgb = BLACK
            elif estilo == "alert":
                r.font.bold = True
                r.font.color.rgb = ACCENT_RED
            elif estilo == "url":
                r.font.size = Pt(font_size - 2)
                r.font.color.rgb = ACCENT_BLUE
            else:
                r.font.color.rgb = BLACK


def insertar_imagen_o_placeholder(slide, img_path, left, top, max_w, max_h, aviso):
    if img_path and Path(img_path).exists():
        pic = slide.shapes.add_picture(str(img_path), left, top)
        ratio = min(max_w / pic.width, max_h / pic.height)
        pic.width = int(pic.width * ratio)
        pic.height = int(pic.height * ratio)
        pic.left = int(left + (max_w - pic.width) / 2)
        pic.top = int(top + (max_h - pic.height) / 2)
    else:
        ph = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, max_w, max_h)
        ph.fill.solid()
        ph.fill.fore_color.rgb = SOFT_BLUE
        ph.line.color.rgb = MUTED_GRAY
        tf = ph.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = aviso
        p.font.name = FONT_NAME
        p.font.size = Pt(13)
        p.font.color.rgb = MUTED_GRAY


def main():
    prs = Presentation()
    # Formato 4:3 exacto (10 x 7.5 pulgadas)
    prs.slide_width = Inches(10.0)
    prs.slide_height = Inches(7.5)

    img_tikz = extraer_diagrama_tikz_desde_pdf()

    # -----------------------------------------------------------------
    # SLIDE 1: Ley de Ampere-Maxwell + Diagrama de Feynman
    # -----------------------------------------------------------------
    s1 = crear_diapositiva_base(
        prs, "1. Ley de Ampère-Maxwell: independencia de la superficie ($r > R$)", 1
    )
    anadir_ecuacion(
        s1, Inches(0.4), Inches(1.02), Inches(9.2), Inches(0.85),
        r"\[\oint_{\Gamma} \mathbf{B}\cdot d\mathbf{l} = \mu_0 \left( I_{\mathrm{cond}} + I_d \right) = \mu_0 \iint_{S} \left( \mathbf{J} + \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t} \right)\cdot d\mathbf{S}\]",
        size=16,
    )
    insertar_imagen_o_placeholder(
        s1, img_tikz, Inches(1.2), Inches(2.0), Inches(7.6), Inches(4.85),
        "Coloca el PDF compilado (con pymupdf instalado) o guarda el diagrama TikZ como diagrama_feynman_tikz.png",
    )

    # -----------------------------------------------------------------
    # SLIDE 2: Independencia de la superficie (r > R)
    # -----------------------------------------------------------------
    s2 = crear_diapositiva_base(prs, "1. Independencia de la superficie ($r > R$)", 2)
    anadir_vinetas(
        s2, Inches(0.6), Inches(1.25), Inches(8.8), Inches(1.4),
        encabezado="Superficies con la misma boca $\\Gamma$ ($r > R$):",
        items=[
            [("Plano en el cable ($S_1$): ", "bold"), ("corta el conductor.", "normal")],
        ],
    )
    anadir_ecuacion(
        s2, Inches(0.8), Inches(2.45), Inches(8.4), Inches(0.75),
        r"\[I_{\mathrm{cond}} = I, \qquad I_d = 0\]",
        size=18,
    )
    anadir_vinetas(
        s2, Inches(0.6), Inches(3.55), Inches(8.8), Inches(1.1),
        items=[
            [
                ("Globo ($S'_1$) o plano medio ($S_2$): ", "bold"),
                (r"esquiva el cable y captura todo el flujo $\Phi_E = Q/\varepsilon_0$.", "normal"),
            ],
        ],
    )
    anadir_ecuacion(
        s2, Inches(0.8), Inches(4.65), Inches(8.4), Inches(0.95),
        r"\[I_{\mathrm{cond}} = 0, \qquad I_d = \varepsilon_0 \frac{d\Phi_E}{dt} = \frac{dQ}{dt} = I\]",
        size=18,
    )

    # -----------------------------------------------------------------
    # SLIDE 3: Superficie que atraviesa la placa
    # -----------------------------------------------------------------
    s3 = crear_diapositiva_base(prs, "1. Superficie que atraviesa la placa", 3)
    anadir_vinetas(
        s3, Inches(0.6), Inches(1.25), Inches(8.8), Inches(0.8),
        items=[
            [(r"Al cruzar la placa superior en $\rho_c \in [0, R]$:", "bold")],
        ],
    )
    anadir_ecuacion(
        s3, Inches(0.6), Inches(2.05), Inches(8.8), Inches(0.95),
        r"\[I_{\mathrm{cond}}(\rho_c) + I_d(\rho_c) = I\left(1 - \frac{\rho_c^2}{R^2}\right) + I\,\frac{\rho_c^2}{R^2} = I\]",
        size=18,
    )
    anadir_bloque_beamer(
        s3, Inches(0.6), Inches(3.55), Inches(8.8), Inches(2.3),
        "Idea clave (solenoidalidad de la corriente total)",
        r"Como $\nabla \cdot \left(\mathbf{J} + \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t}\right) = 0$, "
        r"la corriente total de Maxwell es continua y el campo magnético sobre $\Gamma$ vale siempre "
        r"$B(r) = \dfrac{\mu_0 I}{2\pi r}$, sin depender de la superficie elegida.",
    )

    # -----------------------------------------------------------------
    # SLIDE 4: Modelo ideal frente al calculo numerico
    # -----------------------------------------------------------------
    s4 = crear_diapositiva_base(prs, "2. Modelo ideal frente al cálculo numérico", 4)
    insertar_imagen_o_placeholder(
        s4, PNG_GRAFICA, Inches(0.45), Inches(1.15), Inches(9.1), Inches(5.15),
        "No se encontró perfil_radial_baja_frecuencia_v2.png en la carpeta actual.",
    )
    cap = s4.shapes.add_textbox(Inches(0.5), Inches(6.42), Inches(9.0), Inches(0.45))
    p_c = cap.text_frame.paragraphs[0]
    p_c.alignment = PP_ALIGN.CENTER
    p_c.text = r"Perfil radial normalizado $H_\phi / (I / 2\pi R)$ para $d = 0,2\,R$ en régimen cuasiestático ($kR \ll 1$)."
    p_c.font.name = FONT_NAME
    p_c.font.size = Pt(12)
    p_c.font.color.rgb = MUTED_GRAY

    # -----------------------------------------------------------------
    # SLIDE 5: Cuadra el modelo ideal?
    # -----------------------------------------------------------------
    s5 = crear_diapositiva_base(prs, "2. ¿Cuadra el modelo ideal?", 5)
    anadir_vinetas(
        s5, Inches(0.6), Inches(1.35), Inches(8.8), Inches(5.1),
        encabezado="¿Cuadra el modelo ideal?",
        items=[
            [
                (r"Exterior ($\rho \gtrsim 1,5\,R$) y sobre el cable ($z = 5,5\,d$): ", "bold"),
                (r"el cálculo exacto coincide prácticamente con el hilo infinito $I/(2\pi\rho)$.", "normal"),
            ],
            [
                (r"Interior ($\rho \le R$, $z = 0$): ", "bold"),
                (r"los efectos de borde ($d = 0,2\,R$) suavizan el pico en $\rho = R$ ($0,78\,H_0$ con $\sigma$ uniforme; $0,74\,H_0$ con Love 1949), pero conservan el perfil lineal.", "normal"),
            ],
            [
                ("Conclusión: ", "bold"),
                (r"el modelo ideal ($d \ll R$) reproduce ", "normal"),
                ("bastante bien", "alert"),
                (r" la realidad y valida el argumento de Feynman con $r > R$.", "normal"),
            ],
        ],
        font_size=16,
    )

    # -----------------------------------------------------------------
    # SLIDE 6: Conexion con la Teoria de Circuitos
    # -----------------------------------------------------------------
    s6 = crear_diapositiva_base(prs, "3. Conexión con la Teoría de Circuitos", 6)
    anadir_vinetas(
        s6, Inches(0.6), Inches(1.25), Inches(8.8), Inches(1.6),
        encabezado="1. Por qué «pasa» corriente por un condensador",
        items=[
            [
                (r"Entre las placas no viajan cargas ($I_{\mathrm{cond}} = 0$), pero el flujo eléctrico variable mantiene la continuidad:", "normal"),
            ],
        ],
    )
    anadir_ecuacion(
        s6, Inches(0.6), Inches(2.9), Inches(8.8), Inches(0.95),
        r"\[I_{\mathrm{cable}} = I_{\mathrm{cond}} = I_d = \varepsilon_0 \frac{d\Phi_E}{dt}\]",
        size=18,
    )
    anadir_vinetas(
        s6, Inches(0.6), Inches(4.15), Inches(8.8), Inches(1.8),
        items=[
            [
                (r"Al cerrarse la corriente total $\mathbf{J} + \varepsilon_0 \partial_t\mathbf{E}$ sin fuentes ni sumideros, ", "normal"),
                ("la Ley de Kirchhoff de Corrientes (LKC)", "bold"),
                (" sigue cumpliéndose en cualquier nodo o corte del circuito.", "normal"),
            ],
        ],
    )

    # -----------------------------------------------------------------
    # SLIDE 7: De Maxwell a la ecuacion I = C dV/dt
    # -----------------------------------------------------------------
    s7 = crear_diapositiva_base(prs, r"3. De Maxwell a la ecuación $I = C\,dV/dt$", 7)
    anadir_vinetas(
        s7, Inches(0.6), Inches(1.25), Inches(8.8), Inches(1.4),
        encabezado=r"2. De Maxwell a la ecuación $I = C\,\dfrac{dV}{dt}$",
        items=[
            [
                (r"En el modelo ideal ($d \ll R$), $E = V/d$ y $\Phi_E = E A = \dfrac{A}{d}\,V$:", "normal"),
            ],
        ],
    )
    anadir_ecuacion(
        s7, Inches(0.6), Inches(2.75), Inches(8.8), Inches(1.15),
        r"\[I = I_d = \varepsilon_0 \frac{d}{dt}\left(\frac{A}{d}\,V\right) = \underbrace{\left(\varepsilon_0 \frac{A}{d}\right)}_{C} \frac{dV}{dt}\]",
        size=18,
    )
    anadir_vinetas(
        s7, Inches(0.6), Inches(4.25), Inches(8.8), Inches(1.8),
        items=[
            [
                (r"Con efectos de borde reales (Love 1949), la estructura $I = C\,\frac{dV}{dt}$ ", "normal"),
                ("no cambia", "bold"),
                (r": solo se corrige el valor efectivo de $C$ ($C/C_{\mathrm{ideal}} \approx 1,32$ para $d = 0,2\,R$).", "normal"),
            ],
        ],
    )

    # -----------------------------------------------------------------
    # SLIDE 8: Frontera de la Teoria de Circuitos
    # -----------------------------------------------------------------
    s8 = crear_diapositiva_base(prs, "3. Frontera de la Teoría de Circuitos", 8)
    anadir_bloque_beamer(
        s8, Inches(0.6), Inches(2.0), Inches(8.8), Inches(3.0),
        "Frontera de la Teoría de Circuitos (parámetros concentrados)",
        r"La descripción circuital $I = C\,\frac{dV}{dt}$ es exacta mientras $kR = \frac{\omega R}{c} \ll 1$ "
        r"(régimen cuasiestático). A alta frecuencia ($kR \sim 1$), la inducción de Faraday curva "
        r"$E_z(\rho) \propto J_0(k\rho)$ y $B_\phi(\rho) \propto J_1(k\rho)$: el condensador deja de ser "
        r"un elemento concentrado y se comporta como una cavidad resonante.",
    )

    # -----------------------------------------------------------------
    # SLIDE 9: Enlaces
    # -----------------------------------------------------------------
    s9 = crear_diapositiva_base(prs, "Enlaces", 9)
    anadir_vinetas(
        s9, Inches(0.7), Inches(1.8), Inches(8.6), Inches(3.8),
        items=[
            [
                ("Repositorio de GitHub:\n", "bold"),
                ("https://github.com/salvaugres/desplazamiento_feynman", "url"),
            ],
            [
                ("Conversación compartida de Gemini:\n", "bold"),
                ("https://share.gemini.google/vVk2eZp2O1Aa", "url"),
            ],
        ],
        font_size=17,
    )

    prs.save(str(OUT_PPTX))
    print(f"Presentación generada -> {OUT_PPTX}")


if __name__ == "__main__":
    main()