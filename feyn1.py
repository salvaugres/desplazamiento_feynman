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
FPS = 25
TOTAL_DURATION = 23.6
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
        color=color, alpha=0.9, linewidth=0.15, edgecolor='#6684a8',
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
    z = z_bottom + (z_mouth - z_bottom) * radius_grid**5
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


def build_animation():
    fig = plt.figure(figsize=(12, 7.2), facecolor='#101820')
    ax = fig.add_axes([0.25, 0.08, 0.73, 0.79], projection='3d')
    ax.set_facecolor('#101820')
    ax.set_xlim(-2.75, 2.75)
    ax.set_ylim(-2.75, 2.75)
    ax.set_zlim(-2.45, 3.25)
    ax.set_box_aspect((1.0, 1.0, 1.25))
    ax.view_init(elev=25, azim=-55)
    ax.set_axis_off()

    create_disk(ax, Z_PLACA_SUP + 0.04, '#3974b8')
    create_disk(ax, Z_PLACA_INF + 0.04, '#3974b8')
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

    radii = np.linspace(0.001, 1.0, 17)
    angles = np.linspace(0.0, 2.0 * np.pi, 33)
    surface = Poly3DCollection(
        make_surface_polygons(0.0, 0.0, radii, angles),
        facecolors='#25b8a7',
        edgecolors='#74e0d1',
        linewidths=0.25,
        alpha=0.32,
    )
    ax.add_collection3d(surface)

    circle_angles = np.linspace(0.0, 2.0 * np.pi, 160)
    circle_x = R_BOCA * np.cos(circle_angles)
    circle_y = R_BOCA * np.sin(circle_angles)
    mouth_line, = ax.plot(
        circle_x, circle_y, np.zeros_like(circle_angles),
        color='#ffe66d', linewidth=2.8,
    )
    magnetic_arrows = []

    fig.text(
        0.61, 0.965,
        'Ley de Ampere-Maxwell en un condensador (r > R)',
        ha='center', va='top', color='white', fontsize=17, weight='bold',
    )
    fig.text(
        0.61, 0.91,
        r'$\oint_{\Gamma}\mathbf{B}\cdot d\mathbf{l}'
        r'=\mu_0\left(I_{\mathrm{cond}}+\epsilon_0\frac{d\Phi_E}{dt}\right)$',
        ha='center', va='top', color='white', fontsize=16,
    )
    panel = fig.text(
        0.025, 0.20, '',
        ha='left', va='center', color='white', fontsize=10.5,
        linespacing=1.55,
        bbox={
            'boxstyle': 'round,pad=0.65',
            'facecolor': '#080d12',
            'edgecolor': '#f05b62',
            'linewidth': 1.8,
            'alpha': 0.92,
        },
    )

    panel_text = {
        1: (
            '1. Boca entre placas (S2)\n'
            r'$I_{\mathrm{cond}}=0$' '\n'
            r'$I_d=\epsilon_0\,d\Phi_E/dt=I$' '\n'
            r'$B(r)=\mu_0 I/(2\pi r)$'
        ),
        2: (
            "2. Globo rodeando placa (S'1)\n"
            r'$I_{\mathrm{cond}}=0$ (esquiva la placa)' '\n'
            r'$I_d=\epsilon_0\,d\Phi_E/dt=I$' '\n'
            r'$B(r)=\mu_0 I/(2\pi r)$ (igual)'
        ),
        3: (
            '3. Boca en el cable (S1)\n'
            r'$I_{\mathrm{cond}}=I$ (atraviesa el cable)' '\n'
            r'$I_d=0$' '\n'
            r'$B(r)=\mu_0 I/(2\pi r)$ (mismo valor)'
        ),
    }
    panel_colors = {1: '#f05b62', 2: '#35c9b5', 3: '#ff9f43'}
    panel_state = None

    def update(frame):
        nonlocal magnetic_arrows, panel_state
        time = frame / FPS
        mouth_progress = smoothstep(8.1, 12.1, time)
        bottom_progress = smoothstep(16.1, 20.1, time)
        z_mouth = Z_CABLE_ALTO * mouth_progress
        z_bottom = Z_CABLE_ALTO * bottom_progress

        surface.set_verts(
            make_surface_polygons(z_bottom, z_mouth, radii, angles)
        )
        surface.set_alpha(0.32 * smoothstep(2.0, 3.8, time))
        mouth_line.set_data_3d(
            circle_x, circle_y, np.full_like(circle_angles, z_mouth)
        )

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

        if time < 8.1:
            current_panel = 1
        elif time < 16.1:
            current_panel = 2
        else:
            current_panel = 3
        if time < 2.0:
            panel.set_text('')
        else:
            panel.set_text(panel_text[current_panel])
            if panel_state != current_panel:
                panel.get_bbox_patch().set_edgecolor(panel_colors[current_panel])
                panel_state = current_panel

        rotation = smoothstep(12.1, 15.6, time)
        ax.view_init(elev=25, azim=-55 + 12.0 * rotation)
        return surface, mouth_line, panel, *magnetic_arrows

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
