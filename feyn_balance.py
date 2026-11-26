from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


R_PLACA = 1.15
R_BOCA = 2.35
Z_PLACA_SUP = 0.55
Z_PLACA_INF = -0.55
Z_CABLE_ALTO = 1.85
BOWL_EXP = 2.2  # Mantiene holgura con la placa en Acto 2 y hace visible el cruce en Acto 3
FPS = 25
TOTAL_DURATION = 26.0
outfile = Path(__file__).stem + '.mp4'


def smoothstep(start, end, value):
    progress = np.clip((value - start) / (end - start), 0.0, 1.0)
    return progress * progress * (3.0 - 2.0 * progress)


def create_disk(ax, z, color):
    radii = np.linspace(0.0, R_PLACA, 16)
    angles = np.linspace(0.0, 2.0 * np.pi, 48)
    radius_grid, angle_grid = np.meshgrid(radii, angles)
    x = radius_grid * np.cos(angle_grid)
    y = radius_grid * np.sin(angle_grid)
    ax.plot_surface(
        x, y, np.full_like(x, z),
        color=color, alpha=0.88, linewidth=0.15, edgecolor='#6684a8',
        shade=True,
    )


def create_cylinder(ax, radius, z_min, z_max, color):
    angles = np.linspace(0.0, 2.0 * np.pi, 40)
    heights = np.linspace(z_min, z_max, 12)
    angle_grid, height_grid = np.meshgrid(angles, heights)
    x = radius * np.cos(angle_grid)
    y = radius * np.sin(angle_grid)
    ax.plot_surface(
        x, y, height_grid,
        color=color, alpha=0.95, linewidth=0.1, edgecolor='#555555',
        shade=True,
    )


def make_surface_polygons(z_bottom, z_mouth, radii, angles):
    radius_grid, angle_grid = np.meshgrid(radii, angles, indexing='ij')
    x = R_BOCA * radius_grid * np.cos(angle_grid)
    y = R_BOCA * radius_grid * np.sin(angle_grid)
    z = z_bottom + (z_mouth - z_bottom) * (radius_grid ** BOWL_EXP)
    polygons = []
    for i in range(len(radii) - 1):
        for j in range(len(angles) - 1):
            polygons.append([
                (x[i, j], y[i, j], z[i, j]),
                (x[i + 1, j], y[i + 1, j], z[i + 1, j]),
                (x[i + 1, j + 1], y[i + 1, j + 1], z[i + 1, j + 1]),
                (x[i, j + 1], y[i, j + 1], z[i, j + 1]),
            ])
    return polygons


def compute_exact_flux_split(z_bottom, z_mouth):
    """
    Calcula la fracción exacta de corriente de desplazamiento (Id/I) y
    de conducción (Icond/I) atravesando la superficie z(rho).
    Cuando la superficie corta la placa superior en un círculo de radio rho_c < R:
      - Dentro (rho < rho_c) pasa por el hueco: Id = I * (rho_c / R)^2
      - En rho = rho_c corta la corriente radial superficial: Icond = I * (1 - (rho_c / R)^2)
      - Suma exacta: Icond + Id = I en todo instante.
    """
    if z_bottom >= Z_PLACA_SUP:
        return 1.0, 0.0, 0.0

    # Altura de la superficie justo en el borde de la placa (rho = R_PLACA)
    u_edge = R_PLACA / R_BOCA
    z_at_edge = z_bottom + (z_mouth - z_bottom) * (u_edge ** BOWL_EXP)

    if z_at_edge <= Z_PLACA_SUP:
        # Toda la placa superior queda por encima de la superficie -> 100% Id
        return 0.0, 1.0, 0.0

    # Intersección exacta z(rho_c) = Z_PLACA_SUP
    ratio = (Z_PLACA_SUP - z_bottom) / max(z_mouth - z_bottom, 1e-9)
    rho_c = R_BOCA * (np.clip(ratio, 0.0, 1.0) ** (1.0 / BOWL_EXP))
    rho_c = float(np.clip(rho_c, 0.0, R_PLACA))
    frac_d = (rho_c / R_PLACA) ** 2
    frac_cond = 1.0 - frac_d
    return frac_cond, frac_d, rho_c


def build_animation():
    fig = plt.figure(figsize=(12.6, 7.2), facecolor='#101820')
    ax = fig.add_axes([0.28, 0.06, 0.70, 0.80], projection='3d')
    ax.set_facecolor('#101820')
    ax.set_xlim(-2.75, 2.75)
    ax.set_ylim(-2.75, 2.75)
    ax.set_zlim(-2.35, 3.25)
    ax.set_box_aspect((1.0, 1.0, 1.25))
    ax.view_init(elev=25, azim=-55)
    ax.set_axis_off()

    # Subgráfica 2D para las barras dinámicas de corriente
    ax_bar = fig.add_axes([0.045, 0.43, 0.21, 0.29], facecolor='#0b1117')
    for spine in ('top', 'right'):
        ax_bar.spines[spine].set_visible(False)
    for spine in ('bottom', 'left'):
        ax_bar.spines[spine].set_color('#4d6073')
    ax_bar.tick_params(colors='white', labelsize=9.5)
    ax_bar.set_ylim(0.0, 1.22)
    ax_bar.set_yticks([0.0, 0.5, 1.0])
    ax_bar.set_yticklabels(['0', '0.5 I', 'I'])
    ax_bar.set_xticks([0, 1, 2])
    ax_bar.set_xticklabels([r'$I_{\mathrm{cond}}$', r'$I_d$', r'$I_{\mathrm{tot}}$'], fontsize=11)
    ax_bar.set_title('Balance de flujo en S', color='white', fontsize=10.5, pad=8, weight='bold')
    ax_bar.axhline(1.0, color='#ffe66d', linestyle='--', linewidth=0.9, alpha=0.45)

    bars = ax_bar.bar(
        [0, 1, 2],
        [0.0, 1.0, 1.0],
        width=0.55,
        color=['#ff9f43', '#f05b62', '#ffe66d'],
        edgecolor='white',
        linewidth=0.7,
    )
    bar_labels = [
        ax_bar.text(i, 0.05, '', ha='center', va='bottom', color='white', fontsize=9, weight='bold')
        for i in range(3)
    ]

    # Condensador y cables
    create_disk(ax, Z_PLACA_SUP + 0.03, '#3974b8')
    create_disk(ax, Z_PLACA_INF + 0.03, '#3974b8')
    create_cylinder(ax, 0.055, Z_PLACA_SUP, Z_PLACA_SUP + 2.6, '#aeb8c2')
    create_cylinder(ax, 0.055, Z_PLACA_INF - 1.8, Z_PLACA_INF, '#aeb8c2')

    ax.quiver(
        0.28, 0.0, 2.75, 0.0, 0.0, -0.70,
        color='#ff9f43', linewidth=2.0, arrow_length_ratio=0.25,
    )
    ax.quiver(
        0.28, 0.0, -1.05, 0.0, 0.0, -0.70,
        color='#ff9f43', linewidth=2.0, arrow_length_ratio=0.25,
    )

    for radius, count in ((0.0, 1), (0.55, 6), (0.95, 10)):
        for index in range(count):
            angle = 2.0 * np.pi * index / count
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            ax.quiver(
                x, y, Z_PLACA_SUP - 0.08, 0.0, 0.0,
                Z_PLACA_INF - Z_PLACA_SUP + 0.16,
                color='#f05b62', linewidth=1.2, arrow_length_ratio=0.16,
            )

    radii = np.linspace(0.001, 1.0, 19)
    angles = np.linspace(0.0, 2.0 * np.pi, 36)
    surface = Poly3DCollection(
        make_surface_polygons(0.0, 0.0, radii, angles),
        facecolors='#25b8a7',
        edgecolors='#74e0d1',
        linewidths=0.25,
        alpha=0.32,
    )
    ax.add_collection3d(surface)

    # Anillo brillante de corte sobre la placa superior durante la transición
    ring_angles = np.linspace(0.0, 2.0 * np.pi, 100)
    cut_ring, = ax.plot(
        [], [], [],
        color='#ff9f43', linewidth=3.2,
    )

    # Boca circular Gamma
    circle_angles = np.linspace(0.0, 2.0 * np.pi, 160)
    circle_x = R_BOCA * np.cos(circle_angles)
    circle_y = R_BOCA * np.sin(circle_angles)
    mouth_line, = ax.plot(
        circle_x, circle_y, np.zeros_like(circle_angles),
        color='#ffe66d', linewidth=2.8,
    )
    magnetic_arrows = []

    fig.text(
        0.62, 0.965,
        'Conservación de la corriente total al deformar S (r > R)',
        ha='center', va='top', color='white', fontsize=16.5, weight='bold',
    )
    fig.text(
        0.62, 0.91,
        r'$\oint_{\Gamma}\mathbf{B}\cdot d\mathbf{l}'
        r'=\mu_0\left(I_{\mathrm{cond}}+\epsilon_0\frac{d\Phi_E}{dt}\right)=\mu_0 I$',
        ha='center', va='top', color='white', fontsize=15.5,
    )
    panel = fig.text(
        0.025, 0.20, '',
        ha='left', va='center', color='white', fontsize=9.8,
        linespacing=1.55,
        bbox={
            'boxstyle': 'round,pad=0.6',
            'facecolor': '#080d12',
            'edgecolor': '#f05b62',
            'linewidth': 1.8,
            'alpha': 0.92,
        },
    )

    panel_colors = {1: '#f05b62', 2: '#35c9b5', 3: '#ffe66d', 4: '#ff9f43'}
    panel_state = None

    def update(frame):
        nonlocal magnetic_arrows, panel_state
        t = frame / FPS

        # Acto 1 (0 - 6.5s): boca entre placas
        # Acto 2 (6.5 - 10.5s): boca sube al cable estirando el globo
        mouth_progress = smoothstep(6.5, 10.5, t)
        z_mouth = Z_CABLE_ALTO * mouth_progress

        # Acto 3 (14.5 - 22.5s): el fondo sube cruzando lentamente la placa superior
        # Tramo lento [0.18 -> 0.56] para apreciar el relevo I_d -> I_cond
        if t < 14.5:
            z_bottom = 0.0
        elif t < 16.0:
            z_bottom = 0.18 * smoothstep(14.5, 16.0, t)
        elif t < 20.5:
            z_bottom = 0.18 + (0.57 - 0.18) * smoothstep(16.0, 20.5, t)
        else:
            z_bottom = 0.57 + (Z_CABLE_ALTO - 0.57) * smoothstep(20.5, 22.8, t)

        surface.set_verts(
            make_surface_polygons(z_bottom, z_mouth, radii, angles)
        )
        surface.set_alpha(0.32 * smoothstep(1.2, 2.8, t))

        mouth_line.set_data_3d(
            circle_x, circle_y, np.full_like(circle_angles, z_mouth)
        )

        # Fracción exacta de corriente de conducción y desplazamiento
        frac_cond, frac_d, rho_c = compute_exact_flux_split(z_bottom, z_mouth)

        if rho_c > 0.02:
            cut_ring.set_data_3d(
                rho_c * np.cos(ring_angles),
                rho_c * np.sin(ring_angles),
                np.full_like(ring_angles, Z_PLACA_SUP + 0.05),
            )
        else:
            cut_ring.set_data_3d([], [], [])

        # Actualizar barras dinámicas
        values = [frac_cond, frac_d, 1.0]
        for idx, (bar, lbl, val) in enumerate(zip(bars, bar_labels, values)):
            bar.set_height(val)
            lbl.set_position((idx, val + 0.03))
            lbl.set_text(f'{int(round(val * 100))}%')

        # Flechas de B
        for arrow in magnetic_arrows:
            arrow.remove()
        magnetic_arrows = []
        for angle in (0.0, np.pi / 2.0, np.pi, 3.0 * np.pi / 2.0):
            x = R_BOCA * np.cos(angle)
            y = R_BOCA * np.sin(angle)
            magnetic_arrows.append(ax.quiver(
                x, y, z_mouth,
                0.85 * np.sin(angle), -0.85 * np.cos(angle), 0.0,
                color='#fff08a', linewidth=1.5, arrow_length_ratio=0.25,
            ))

        # Texto del panel
        if t < 1.2:
            panel.set_text('')
        else:
            if t < 6.5:
                state = 1
                txt = (
                    '1. Boca entre placas (S2)\n'
                    r'$I_{\mathrm{cond}}=0,\quad I_d=I$' '\n'
                    r'$B(r)=\mu_0 I/(2\pi r)$'
                )
            elif t < 14.5:
                state = 2
                txt = (
                    "2. Globo rodeando placa (S'1)\n"
                    r'$I_{\mathrm{cond}}=0,\quad I_d=I$' '\n'
                    r'$B(r)=\mu_0 I/(2\pi r)$ (invariable)'
                )
            elif 0.01 < frac_cond < 0.99:
                state = 3
                txt = (
                    '3. Cruzando la placa superior\n'
                    r'$\nabla\cdot(\mathbf{J}+\epsilon_0\partial_t\mathbf{E})=0$' '\n'
                    f'$I_{{\\mathrm{{cond}}}}={frac_cond:.2f}\\,I,\\; I_d={frac_d:.2f}\\,I$\n'
                    r'$I_{\mathrm{tot}}=I \Rightarrow B(r)$ constante'
                )
            else:
                state = 4
                txt = (
                    '4. Boca en el cable (S1)\n'
                    r'$I_{\mathrm{cond}}=I,\quad I_d=0$' '\n'
                    r'$B(r)=\mu_0 I/(2\pi r)$ (mismo valor)'
                )
            panel.set_text(txt)
            if panel_state != state:
                panel.get_bbox_patch().set_edgecolor(panel_colors[state])
                panel_state = state

        rotation = smoothstep(10.8, 14.2, t)
        ax.view_init(elev=25, azim=-55 + 15.0 * rotation)
        return surface, cut_ring, mouth_line, panel, *bars, *bar_labels, *magnetic_arrows

    frame_count = int(TOTAL_DURATION * FPS) + 1
    animation = FuncAnimation(
        fig,
        update,
        frames=frame_count,
        interval=1000.0 / FPS,
        blit=False,
        repeat=False,
    )
    return fig, animation


def main():
    fig, animation = build_animation()
    if outfile.endswith('.mp4'):
        animation.save(outfile, writer=FFMpegWriter(fps=FPS, bitrate=1800), dpi=110)
    elif outfile.endswith('.gif'):
        animation.save(outfile, writer=PillowWriter(fps=FPS), dpi=80)
    else:
        plt.show()
    print(f'Animación terminada -> {outfile or "pantalla"}')
    plt.close(fig)


if __name__ == '__main__':
    main()
