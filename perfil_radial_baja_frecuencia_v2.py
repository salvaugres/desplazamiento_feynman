"""
Perfil radial exacto del campo magnético cuasiestático H_phi(rho, z)
en un condensador de placas circulares paralelas (radio R, separación d).

Incluye dos niveles físicos de corrección de bordes (baja frecuencia, kR << 1):
  1. Biot-Savart exacto (integrales elípticas) para dos hilos semiinfinitos
     + placas con densidad de carga uniforme (corrección geométrica de espesor d/R).
  2. Ecuación integral de Love (1949) para placas conductoras reales equipotenciales
     (acumulación de carga en el borde sigma(rho) ~ 1/sqrt(R^2 - rho^2),
     corrección electrostática completa de efectos de borde).

Normalización: H0 = I / (2 * pi * R), de modo que el hilo infinito I/(2*pi*rho)
se representa simplemente como R / rho y vale 1 en el borde rho = R.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import quad
from scipy.special import ellipe, ellipk


# Parámetros adimensionales (R = 1)
R = 1.0
D_OVER_R = 0.2                # Relación espesor/radio (d = 0.2 R)
d = D_OVER_R * R
Z_MID = 0.0                   # Plano medio entre placas
Z_TOP_5D = 0.5 * d + 5.0 * d  # 5 veces el espesor d por encima de la placa superior (z = 5.5 d)

# Activar/desactivar la curva exacta de Love (placas conductoras equipotenciales)
SHOW_LOVE_EXACT = True


def solve_love_equation(kappa, n_gl=80):
    """
    Resuelve la ecuación integral de Fredholm de Love (1949) para dos discos
    conductores paralelos a potenciales +V/2 y -V/2 con kappa = d / R:

        f(x) - (1/pi) * int_{-1}^{1} [kappa / (kappa^2 + (x - t)^2)] f(t) dt = 1

    Devuelve (F_love, C_ratio), donde:
      - F_love(r): fracción exacta de corriente radial superficial I_radial(r)/I
        que fluye hacia fuera más allá del radio r (0 <= r <= R).
      - C_ratio: cociente C / C_ideal respecto al condensador ideal sin bordes.
    """
    t_gl, w_gl = np.polynomial.legendre.leggauss(n_gl)
    diff = t_gl[:, None] - t_gl[None, :]
    K_mat = (1.0 / np.pi) * (kappa / (kappa**2 + diff**2)) * w_gl[None, :]
    f_gl = np.linalg.solve(np.eye(n_gl) - K_mat, np.ones(n_gl))

    I_f = float(np.sum(w_gl * f_gl))
    C_ratio = 2.0 * kappa * I_f / np.pi
    I_f_half = 0.5 * I_f

    # Cuadratura fija para el cambio no singular x = sqrt(r^2 + (1 - r^2) s^2)
    s_gl, ws_gl = np.polynomial.legendre.leggauss(40)
    s01 = 0.5 * (s_gl + 1.0)
    ws01 = 0.5 * ws_gl

    def eval_f(x_arr):
        x_arr = np.atleast_1d(x_arr)
        K_eval = (
            (1.0 / np.pi)
            * (kappa / (kappa**2 + (x_arr[:, None] - t_gl[None, :]) ** 2))
            * w_gl[None, :]
        )
        return 1.0 + K_eval @ f_gl

    def F_love(rho):
        u = rho / R
        if u >= 1.0:
            return 0.0
        x_pts = np.sqrt(u**2 + (1.0 - u**2) * s01**2)
        return float(np.sqrt(1.0 - u**2) * np.sum(ws01 * eval_f(x_pts)) / I_f_half)

    return F_love, C_ratio


def F_uniform(rho):
    """Fracción de corriente radial I_radial(rho)/I para densidad de carga uniforme."""
    u = rho / R
    return 0.0 if u >= 1.0 else (1.0 - u**2)


def H_wire_norm(rho, z):
    """Contribución normalizada H_phi / H0 de los dos hilos semiinfinitos (|z'| >= d/2)."""
    if rho < 1e-12:
        return 0.0
    t1 = (z - 0.5 * d) / np.sqrt(rho**2 + (z - 0.5 * d) ** 2)
    t2 = (z + 0.5 * d) / np.sqrt(rho**2 + (z + 0.5 * d) ** 2)
    return (R / (2.0 * rho)) * (2.0 + t1 - t2)


def phi_elliptic_integral(rho, rhop, dz):
    """
    Integral acimutal cerrada de Biot-Savart para un anillo de corriente radial:
      int_0^{2pi} cos(phi) / (rho^2 + rhop^2 + dz^2 - 2*rho*rhop*cos(phi))^(3/2) dphi
    expresada mediante integrales elípticas completas K(m) y E(m).
    """
    if rho * rhop < 1e-18:
        return 0.0
    apb = (rho + rhop) ** 2 + dz**2
    m = 4.0 * rho * rhop / apb
    K = ellipk(m)
    E = ellipe(m)
    return (4.0 / (apb**1.5)) * (((2.0 - m) / m) * (E / (1.0 - m)) - (2.0 / m) * K)


def H_total_norm(rho, z, F_radial):
    """
    Campo magnético total normalizado H_phi(rho, z) / H0 en régimen cuasiestático.
    Por Helmholtz (rot(J_d) = 0), basta integrar las corrientes de conducción:
    hilos semiinfinitos + corrientes superficiales radiales en z' = +d/2 y -d/2.
    """
    if rho < 1e-12:
        return 0.0
    hw = H_wire_norm(rho, z)

    def plate_contribution(z_p, sign):
        dz = z - z_p
        if abs(dz) < 1e-12:
            return 0.0
        pts = [rho] if rho < R else None
        res, _ = quad(
            lambda rp: F_radial(rp) * phi_elliptic_integral(rho, rp, dz),
            0.0,
            R,
            points=pts,
            epsabs=1e-8,
            epsrel=1e-8,
        )
        return (R / (4.0 * np.pi)) * sign * dz * res

    return hw + plate_contribution(+0.5 * d, +1.0) + plate_contribution(-0.5 * d, -1.0)


def main():
    F_love, c_ratio = solve_love_equation(D_OVER_R)
    print(f'Condensador d/R = {D_OVER_R:.2f} -> C / C_ideal (Love 1949) = {c_ratio:.4f}')

    # Malla radial (más densa cerca del borde rho = R)
    rho_all = np.unique(np.concatenate([
        np.linspace(0.0, 0.85, 55),
        np.linspace(0.85, 1.20, 45),
        np.linspace(1.20, 3.00, 65),
    ]))
    rho_pos = rho_all[rho_all >= 0.40]

    H_inf = 1.0 / rho_pos
    H_ideal = np.where(rho_all <= R, rho_all / R, R / np.maximum(rho_all, 1e-9))

    H_mid_unif = np.array([H_total_norm(r, Z_MID, F_uniform) for r in rho_all])
    H_5d_unif = np.array([H_total_norm(r, Z_TOP_5D, F_uniform) for r in rho_pos])

    if SHOW_LOVE_EXACT:
        H_mid_love = np.array([H_total_norm(r, Z_MID, F_love) for r in rho_all])

    # Estilo limpio tipo Beamer / publicación
    plt.rcParams.update({
        'font.size': 11,
        'axes.linewidth': 1.1,
        'mathtext.fontset': 'cm',
    })

    fig, ax = plt.subplots(figsize=(8.6, 4.6))

    # Sombreado de la región interior (rho <= R)
    ax.axvspan(0.0, 1.0, color='#eaf2fa', zorder=0)
    ax.axvline(1.0, color='#555555', linestyle='-.', linewidth=1.0, zorder=1)
    ax.text(
        0.24, 2.02, r'Interior ($\rho \leq R$)',
        ha='center', va='center', color='#1c4e80', fontsize=10.5, weight='bold',
    )

    # Curvas
    ax.plot(
        rho_pos, H_inf,
        color='#222222', linestyle='--', linewidth=1.8,
        label=r'Hilo infinito $I/(2\pi\rho)$', zorder=4,
    )
    ax.plot(
        rho_all, H_ideal,
        color='#4a5568', linestyle='-.', linewidth=1.4,
        label=r'Ideal sin bordes ($d \ll R$)', zorder=3,
    )
    ax.plot(
        rho_pos, H_5d_unif,
        color='#1f77b4', linestyle='-', linewidth=2.4,
        label=r'$z = 5.5\,d$ ($5d$ sobre placa)', zorder=5,
    )
    ax.plot(
        rho_all, H_mid_unif,
        color='#d62728', linestyle='-', linewidth=2.4,
        label=r'$z = 0$ ($\sigma$ uniforme, $d = 0.2\,R$)', zorder=6,
    )

    if SHOW_LOVE_EXACT:
        ax.plot(
            rho_all, H_mid_love,
            color='#8e24aa', linestyle='-', linewidth=2.2,
            label=r'$z = 0$ (Love 1949, placas conductoras)', zorder=7,
        )

    ax.set_xlim(0.0, 3.0)
    ax.set_ylim(0.0, 2.2)
    ax.set_xlabel(r'Radio normalizado $\rho / R$', fontsize=12, weight='bold')
    ax.set_ylabel(r'Campo normalizado $H_\phi \,/\, (I / 2\pi R)$', fontsize=12, weight='bold')
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#aaaaaa', fontsize=9.8)

    plt.tight_layout()
    stem = Path(__file__).stem
    plt.savefig(f'{stem}.pdf', dpi=300)
    plt.savefig(f'{stem}.png', dpi=300)
    print(f'Gráficas guardadas -> {stem}.pdf y {stem}.png')
    plt.close(fig)


if __name__ == '__main__':
    main()
